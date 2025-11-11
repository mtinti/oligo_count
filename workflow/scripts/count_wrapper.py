#!/usr/bin/env python
"""
Wrapper script for counting oligos in Snakemake pipeline
"""

import sys
import os

# Add scripts directory to path
scripts_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, scripts_dir)

from oligo_counter import ParallelOligoCounter, load_oligos

# Get parameters from snakemake object
R1 = snakemake.input.R1
R2 = snakemake.input.R2
oligos_file = snakemake.input.oligos
output_file = snakemake.output.counts
sample_name = snakemake.params.sample_name
batch_size = snakemake.params.batch_size
show_progress_bar = snakemake.params.show_progress_bar
threads = snakemake.threads

# Load oligos
oligos = load_oligos(oligos_file)
print(f"[{sample_name}] Loaded {len(oligos)} oligo sequences", flush=True)

# Create counter
counter = ParallelOligoCounter(
    oligos=oligos,
    batch_size=batch_size,
    num_consumers=threads,
    show_progress_bar=show_progress_bar
)

# Count oligos
print(f"[{sample_name}] Starting processing with {threads} threads", flush=True)
result_df = counter.count_oligos_in_fastq_pairs(
    fastq1_path=R1,
    fastq2_path=R2,
    prefix=sample_name,
    output_file=output_file
)

print(f"[{sample_name}] Completed successfully", flush=True)
