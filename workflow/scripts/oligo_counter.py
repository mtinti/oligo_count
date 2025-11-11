#!/usr/bin/env python
# coding: utf-8

"""
Parallel Oligo Counter - Command Line Tool
Count oligonucleotide sequences in paired FASTQ files.

Usage:
    python oligo_counter.py -o oligos.txt -d /path/to/folder [options]
"""

import gzip
import pandas as pd
import time
import queue
import threading
import multiprocessing
from concurrent.futures import ThreadPoolExecutor
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn, MofNCompleteColumn
from Bio.SeqIO.QualityIO import FastqGeneralIterator
from collections import Counter
import os
import argparse
import sys
import re

def reverse_complement(seq):
    """Return the reverse complement of a DNA sequence."""
    complement = {
        'A': 'T', 'T': 'A', 'G': 'C', 'C': 'G'
    }
    rev_comp = ''
    for base in reversed(seq):
        rev_comp += complement.get(base, base)
    return rev_comp

class ParallelOligoCounter:
    def __init__(self, oligos, search_strategy=None, batch_size=10000, num_consumers=None, show_progress_bar=False):
        """
        Initialize the parallel oligo counter.

        Args:
            oligos (list): List of oligo sequences to search for
            search_strategy (callable, optional): Function for searching oligos
                Should have signature: (oligo, rc_oligo, combined_seq) -> int (1 if found, 0 if not)
                If None, will use the default search strategy
            batch_size (int): Number of read pairs to process in each batch
            num_consumers (int): Number of consumer processes to use (defaults to CPU count)
            show_progress_bar (bool): Whether to display progress bars (default: False)
        """
        self.oligos = oligos
        self.batch_size = batch_size
        self.num_consumers = num_consumers or multiprocessing.cpu_count()
        self.show_progress_bar = show_progress_bar
        
        # Pre-compute reverse complements for all oligos
        self.rc_oligos = {oligo: reverse_complement(oligo) for oligo in oligos}
        
        # Set search strategy
        self.search_strategy = search_strategy if search_strategy is not None else self.default_search_strategy
        
        # Shared counter for results
        self.counter = Counter()
        self.counter_lock = threading.Lock()
        
        # Queue for communication between producer and consumers
        self.queue = queue.Queue(maxsize=self.num_consumers * 2)
        
        # Progress tracking
        self.batches_queued = 0
        self.batches_processed = 0
        self.batches_lock = threading.Lock()

        # Rich progress tracking
        self.progress = None
        self.queuing_task = None
        self.processing_task = None

        # Sentinel value to signal end of processing
        self.SENTINEL = None
    
    @staticmethod
    def default_search_strategy(oligo, rc_oligo, combined_seq):
        """
        Default strategy for searching oligos in a sequence.
        
        Args:
            oligo (str): Oligo sequence to search for
            rc_oligo (str): Reverse complement of the oligo
            combined_seq (str): Combined read pair sequence to search in
            
        Returns:
            int: 1 if found, 0 if not
        """
        # Check forward sequence first
        if oligo in combined_seq:
            return 1
        
        # Check reverse complement if forward not found
        if rc_oligo in combined_seq:
            return 1
        
        return 0
        
    def producer(self, fastq1_path, fastq2_path):
        """Producer function that reads FASTQ files and adds read pairs to the queue"""
        try:
            with gzip.open(fastq1_path, "rt") as f1, gzip.open(fastq2_path, "rt") as f2:
                file_1 = FastqGeneralIterator(f1)
                file_2 = FastqGeneralIterator(f2)
                
                batch = []
                for (title1, seq1, qual1), (title2, seq2, qual2) in zip(file_1, file_2):
                    batch.append((seq1, seq2))
                    
                    # When batch is full, put it in the queue
                    if len(batch) >= self.batch_size:
                        self.queue.put(batch)
                        # Update the batches queued counter and progress bar
                        with self.batches_lock:
                            self.batches_queued += 1
                            if self.progress and self.queuing_task is not None:
                                self.progress.update(self.queuing_task, advance=1)
                        batch = []

                # Put remaining items in the queue
                if batch:
                    self.queue.put(batch)
                    # Update the batches queued counter and progress bar
                    with self.batches_lock:
                        self.batches_queued += 1
                        if self.progress and self.queuing_task is not None:
                            self.progress.update(self.queuing_task, advance=1)
                    
        except Exception as e:
            print(f"Producer error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # Put sentinel values for each consumer
            for _ in range(self.num_consumers):
                self.queue.put(self.SENTINEL)
    
    def consumer(self, consumer_id):
        """Consumer function that processes read pairs from the queue"""
        while True:
            # Get a batch from the queue
            batch = self.queue.get()
            
            # Check for sentinel
            if batch is self.SENTINEL:
                break
                
            # Process batch
            local_counter = Counter()
            for seq1, seq2 in batch:
                # Combine both reads for searching
                combined_seq = seq1 + '|' + seq2
                
                # Check each oligo using the search strategy with pre-computed reverse complements
                for oligo in self.oligos:
                    rc_oligo = self.rc_oligos[oligo]
                    found = self.search_strategy(oligo, rc_oligo, combined_seq)
                    if found:
                        local_counter[oligo] += 1
            
            # Update global counter with local results
            with self.counter_lock:
                self.counter.update(local_counter)
                
            # Update processed batch count and progress bar
            with self.batches_lock:
                self.batches_processed += 1
                if self.progress and self.processing_task is not None:
                    self.progress.update(self.processing_task, advance=1)
    
    def count_oligos_in_fastq_pairs(self, fastq1_path, fastq2_path, prefix="", output_file=None):
        """
        Count occurrences of each oligo and its reverse complement in paired FASTQ files.
        
        Args:
            fastq1_path (str): Path to R1 FASTQ file (can be gzipped)
            fastq2_path (str): Path to R2 FASTQ file (can be gzipped)
            prefix (str, optional): Prefix to add to the 'Count' column name
            output_file (str, optional): Path to save the DataFrame (CSV format)
            
        Returns:
            pandas.DataFrame: DataFrame with oligos as index and counts as a column
        """
        start_time = time.time()
        
        # Reset counter and progress tracking
        self.counter.clear()
        self.batches_queued = 0
        self.batches_processed = 0
        
        # Create progress bars with initial values
        sample_label = f"[{prefix}]" if prefix else ""
        print(f"\n{sample_label} Processing: {os.path.basename(fastq1_path)} & {os.path.basename(fastq2_path)}")

        # Setup progress tracking if enabled
        if self.show_progress_bar:
            # Create Rich Progress with custom columns
            self.progress = Progress(
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                MofNCompleteColumn(),
                TextColumn("•"),
                TimeElapsedColumn(),
            )
            progress_context = self.progress
        else:
            # No progress bars - use a dummy context manager
            import contextlib
            self.progress = None
            progress_context = contextlib.nullcontext()

        with progress_context:
            # Add tasks for queuing and processing if progress bars enabled
            if self.show_progress_bar:
                self.queuing_task = self.progress.add_task(
                    f"{sample_label} Batches queued", total=None
                )
                self.processing_task = self.progress.add_task(
                    f"{sample_label} Batches processed", total=None
                )

            # Create and start producer thread
            producer_thread = threading.Thread(
                target=self.producer,
                args=(fastq1_path, fastq2_path)
            )
            producer_thread.daemon = True
            producer_thread.start()

            # Create and start consumer threads
            consumer_threads = []
            for i in range(self.num_consumers):
                t = threading.Thread(target=self.consumer, args=(i,))
                t.daemon = True
                t.start()
                consumer_threads.append(t)

            # Monitor progress until completion
            while (producer_thread.is_alive() or any(t.is_alive() for t in consumer_threads) or
                   self.batches_processed < self.batches_queued):

                # Update progress bar totals if enabled
                if self.show_progress_bar:
                    with self.batches_lock:
                        # Update queuing progress bar total
                        if self.batches_queued > 0:
                            self.progress.update(self.queuing_task, total=self.batches_queued)

                        # Update processing progress bar total
                        if self.batches_queued > 0:
                            self.progress.update(self.processing_task, total=self.batches_queued)

                time.sleep(0.1)

            # Wait for all threads to complete
            producer_thread.join()
            for t in consumer_threads:
                t.join()

        # Clean up progress tracking
        self.progress = None
        self.queuing_task = None
        self.processing_task = None
        
        # Create DataFrame from the counter
        result = {}
        for oligo in self.oligos:
            result[oligo] = self.counter[oligo]
        
        # Create column name with prefix
        column_name = f"{prefix}_Count" if prefix else "Count"
        
        # Convert results to a DataFrame
        df = pd.DataFrame(list(result.items()), columns=['Oligo', column_name])
        df = df.set_index('Oligo')
        
        end_time = time.time()
        print(f"{sample_label} Processing completed in {end_time - start_time:.2f} seconds")
        print(f"{sample_label} Total batches processed: {self.batches_processed}")
        
        # Save to file if output_file is specified
        if output_file:
            df.to_csv(output_file)
            print(f"{sample_label} Results saved to {output_file}")
        
        return df

def load_oligos(oligo_file):
    """
    Load oligos from a file. Supports both CSV/TSV files with a 'Sequence' column
    or simple text files with one sequence per line.
    
    Args:
        oligo_file (str): Path to the oligo file
        
    Returns:
        list: List of oligo sequences in uppercase
    """
    try:
        # Try to read as CSV/TSV with a 'Sequence' column
        if oligo_file.endswith('.csv'):
            df = pd.read_csv(oligo_file)
        elif oligo_file.endswith('.tsv') or oligo_file.endswith('.txt'):
            # Try tab-separated first
            try:
                df = pd.read_csv(oligo_file, sep='\t')
            except:
                # If that fails, try comma-separated
                try:
                    df = pd.read_csv(oligo_file)
                except:
                    # If both fail, read as simple text file
                    df = None
        else:
            df = None
        
        if df is not None and 'Sequence' in df.columns:
            oligos = list(df['Sequence'])
        else:
            # Read as simple text file with one sequence per line
            with open(oligo_file, 'r') as f:
                oligos = [line.strip() for line in f if line.strip()]
        
        # Convert to uppercase
        oligos = [seq.upper() for seq in oligos]
        return oligos
        
    except Exception as e:
        print(f"Error loading oligo file: {e}")
        sys.exit(1)

def find_fastq_pairs(target_dir):
    """
    Find paired FASTQ files in the target directory.
    
    Args:
        target_dir (str): Path to the directory containing FASTQ files
        
    Returns:
        list: List of tuples (R1_path, R2_path, sample_name)
    """
    # Compile regex patterns for matching file names
    pattern1 = re.compile(r'(.*)_R1(\.fastq\.gz|\.fq\.gz|\.fastq|\.fq)$')
    pattern2 = re.compile(r'(.*)_R2(\.fastq\.gz|\.fq\.gz|\.fastq|\.fq)$')
    
    # Dictionary to store fastq pairs
    fastq_pairs = {}
    
    # Get all files in the directory
    for filename in os.listdir(target_dir):
        filepath = os.path.join(target_dir, filename)
        
        # Skip if not a file
        if not os.path.isfile(filepath):
            continue
            
        match1 = pattern1.match(filename)
        match2 = pattern2.match(filename)
        
        if match1:
            base_name = match1.group(1)
            if base_name not in fastq_pairs:
                fastq_pairs[base_name] = {}
            fastq_pairs[base_name]['R1'] = filepath
        elif match2:
            base_name = match2.group(1)
            if base_name not in fastq_pairs:
                fastq_pairs[base_name] = {}
            fastq_pairs[base_name]['R2'] = filepath
    
    # Create list of complete pairs
    pairs = []
    for base_name, files in fastq_pairs.items():
        if 'R1' in files and 'R2' in files:
            pairs.append((files['R1'], files['R2'], base_name))
        else:
            if 'R1' in files and 'R2' not in files:
                print(f"Warning: Found R1 but missing R2 for {base_name}")
            elif 'R2' in files and 'R1' not in files:
                print(f"Warning: Found R2 but missing R1 for {base_name}")
    
    return sorted(pairs, key=lambda x: x[2])

def main():
    parser = argparse.ArgumentParser(
        description='Count oligonucleotide sequences in paired FASTQ files.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage
  python %(prog)s -o oligos.txt -d /path/to/fastq/folder
  
  # Specify output directory and number of threads
  python %(prog)s -o oligos.txt -d /path/to/fastq/folder -out results/ -t 8
  
  # Process with larger batch size for better performance on large files
  python %(prog)s -o oligos.txt -d /path/to/fastq/folder -b 50000
        """
    )
    
    # Required arguments
    parser.add_argument('-o', '--oligos', required=True,
                        help='Path to oligo file (CSV/TSV with "Sequence" column or text file with one sequence per line)')
    parser.add_argument('-d', '--directory', required=True,
                        help='Target directory containing R1 and R2 FASTQ files')
    
    # Optional arguments
    parser.add_argument('-out', '--output', default='.',
                        help='Output directory for results (default: current directory)')
    parser.add_argument('-t', '--threads', type=int, default=None,
                        help='Number of consumer threads (default: number of CPU cores)')
    parser.add_argument('-b', '--batch-size', type=int, default=10000,
                        help='Number of read pairs per batch (default: 10000)')
    parser.add_argument('-p', '--prefix', default='',
                        help='Prefix for output files (default: none)')
    parser.add_argument('--merge', action='store_true',
                        help='Merge all results into a single CSV file')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Print verbose output')
    
    args = parser.parse_args()
    
    # Validate inputs
    if not os.path.exists(args.oligos):
        print(f"Error: Oligo file '{args.oligos}' not found")
        sys.exit(1)
    
    if not os.path.exists(args.directory):
        print(f"Error: Target directory '{args.directory}' not found")
        sys.exit(1)
    
    if not os.path.isdir(args.directory):
        print(f"Error: '{args.directory}' is not a directory")
        sys.exit(1)
    
    # Create output directory if it doesn't exist
    if not os.path.exists(args.output):
        os.makedirs(args.output)
    
    # Load oligos
    print(f"Loading oligos from {args.oligos}...")
    oligos = load_oligos(args.oligos)
    print(f"Loaded {len(oligos)} oligo sequences")
    
    if args.verbose:
        print(f"First 5 oligos: {oligos[:5]}")
    
    # Find FASTQ pairs
    print(f"\nSearching for FASTQ pairs in {args.directory}...")
    pairs = find_fastq_pairs(args.directory)
    
    if not pairs:
        print("Error: No paired FASTQ files found in the target directory")
        print("Expected file naming pattern: *_R1.fastq.gz and *_R2.fastq.gz")
        sys.exit(1)
    
    print(f"Found {len(pairs)} paired FASTQ files")
    
    # Process each pair
    all_results = []
    
    for i, (r1_path, r2_path, sample_name) in enumerate(pairs, 1):
        print(f"\n{'='*60}")
        print(f"Processing pair {i}/{len(pairs)}: {sample_name}")
        print(f"{'='*60}")
        
        # Create output filename
        output_prefix = f"{args.prefix}_{sample_name}" if args.prefix else sample_name
        output_file = os.path.join(args.output, f"{output_prefix}.counts.csv")
        
        # Create counter and process files
        counter = ParallelOligoCounter(
            oligos=oligos,
            batch_size=args.batch_size,
            num_consumers=args.threads
        )
        
        result_df = counter.count_oligos_in_fastq_pairs(
            fastq1_path=r1_path,
            fastq2_path=r2_path,
            prefix=sample_name,
            output_file=output_file
        )
        
        all_results.append(result_df)
    
    # Merge results if requested
    if args.merge and all_results:
        print(f"\n{'='*60}")
        print("Merging all results...")
        print(f"{'='*60}")
        
        # Concatenate all DataFrames
        merged_df = pd.concat(all_results, axis=1)
        
        # Create merged output filename
        merged_prefix = f"{args.prefix}_merged" if args.prefix else "merged"
        merged_file = os.path.join(args.output, f"{merged_prefix}.counts.csv")
        
        # Save merged results
        merged_df.to_csv(merged_file)
        print(f"Merged results saved to {merged_file}")
        
        # Print summary statistics
        print("\nSummary statistics:")
        print(f"Total samples: {len(all_results)}")
        print(f"Total oligos: {len(merged_df)}")
        print(f"\nTotal counts per sample:")
        for col in merged_df.columns:
            total = merged_df[col].sum()
            print(f"  {col}: {total:,}")
    
    print(f"\n{'='*60}")
    print("All processing complete!")
    print(f"Results saved to: {os.path.abspath(args.output)}")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()