# Oligo Counting Snakemake Pipeline

A best-practice Snakemake pipeline for counting oligonucleotides in paired-end FASTQ files.

## Directory Structure

```
count_oligo/
├── workflow/
│   ├── Snakefile              # Main workflow file
│   ├── rules/
│   │   ├── count.smk          # Rule for counting oligos
│   │   └── merge.smk          # Rule for merging counts
│   ├── scripts/
│   │   ├── oligo_counter.py   # Oligo counting script
│   │   ├── count_wrapper.py   # Wrapper for Snakemake
│   │   └── merge_oligo_counts.py  # Merging script
│   └── envs/
│       └── oligo_counter.yaml # Conda environment specification
├── config/
│   ├── config.yaml            # Pipeline configuration
│   └── cluster.yaml           # Cluster configuration (SLURM)
├── indata/                    # Input data directory (not tracked by git)
│   ├── oligo_sequences.txt    # Oligo sequences to count
│   └── sample_dirs/           # Sample directories with FASTQ files
├── logs/                      # Log files (auto-generated)
└── results/                   # Output files (auto-generated)
```

## Configuration

### Input Data Organization

All input data should be placed in the `indata/` directory:

```
indata/
├── oligo_sequences.txt          # File with oligo sequences to count
├── sample1/                     # Directory for sample 1
│   ├── *_R1.fastq.gz           # Read 1
│   └── *_R2.fastq.gz           # Read 2
└── sample2/                     # Directory for sample 2
    ├── *_R1.fastq.gz
    └── *_R2.fastq.gz
```

**Note**: The `indata/` directory is excluded from git (contains large FASTQ files).

### Pipeline Configuration

Edit `config/config.yaml` to specify:

1. **Oligo sequences file**: Path to file containing oligo sequences (in `indata/`)
2. **Samples**: For each sample, provide paths to R1 and R2 FASTQ files (in `indata/`)
3. **Processing parameters**: Threads, batch size, and progress bar display
4. **Output settings**: Output directory and merge prefix

Example configuration:

```yaml
oligo_file: "indata/oligo_sequences.txt"
output_dir: "results"

samples:
  sample1:
    R1: "indata/sample1/sample1_R1.fastq.gz"
    R2: "indata/sample1/sample1_R2.fastq.gz"
  sample2:
    R1: "indata/sample2/sample2_R1.fastq.gz"
    R2: "indata/sample2/sample2_R2.fastq.gz"

threads: 16
batch_size: 10000
show_progress_bar: false  # Set to true for troubleshooting
merge_prefix: "oligo_counts"
```

**Note on `show_progress_bar`:**
- Set to `false` (default) for cleaner log files in production
- Set to `true` when troubleshooting to see detailed progress bars

## Usage

### Run the pipeline

```bash
# Dry run to check the workflow
snakemake --snakefile workflow/Snakefile --configfile config/config.yaml --use-conda -n

# Run with all available cores
snakemake --snakefile workflow/Snakefile --configfile config/config.yaml --use-conda --cores all

# Run with specific number of cores
snakemake --snakefile workflow/Snakefile --configfile config/config.yaml --use-conda --cores 8
```


## Output Files

The pipeline generates:

1. **Individual count files**: `results/{sample}/{sample}.counts.csv`
   - Counts for each sample separately

2. **Merged counts**: `results/oligo_counts_merged_all_samples.csv`
   - All samples merged into a single file

3. **Summary report**: `results/oligo_counts_merge_summary.txt`
   - Statistics about the merge

4. **Log files**: `logs/{sample}.count.log` and `logs/merge.log`
   - Detailed processing logs

## Requirements

- Snakemake >= 6.0
- Conda/Mamba (for automatic environment management)

The pipeline will automatically install required dependencies:
- Python 3.9
- pandas
- biopython
- tqdm

## Notes

- The pipeline uses conda environments for reproducibility
- Each sample is processed in parallel
- Logs are stored in the `logs/` directory
- All parameters from `config.txt` and `folders.txt` are now in `config/config.yaml`
- Input data (FASTQ files and oligo sequences) should be placed in `indata/`
- The `indata/` directory is excluded from git to avoid tracking large files
