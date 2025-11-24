# Running on Dundee Cluster

This guide provides step-by-step instructions for running the oligo counting pipeline on the Dundee compute cluster.

## Setup and Execution

```bash
# 1. Connect to the cluster
ssh compute.dundee.ac.uk

# 2. Start a screen session (protects against connection loss)
screen -S snakemake_job

# If connection drops, reconnect with:
# ssh compute.dundee.ac.uk
# screen -r snakemake_job

# 3. Request an interactive session with 16 cores
qrsh -pe smp 16

# 4. Navigate to your lab folder
cd /cluster/majf_lab/mtinti  # Replace with your lab folder path

# 5. Clone the repository (this step is done only once)
git clone https://github.com/mtinti/oligo_count.git

# 6. Create and activate conda environment (this step is done only once)
conda create -n snakemake snakemake
# 6b. (This step is every time)
conda activate snakemake

# 7. Navigate to the repository
cd count_oligo
# 7b. git pull (this step is every time)

# 8. Prepare your input data
# 8a. Copy your oligonucleotide sequences file to indata/
cp /path/to/your/oligo_sequences.txt indata/

# 8b. Copy or link your FASTQ files to indata/
# Create sample directories and copy paired-end FASTQ files
mkdir -p indata/SampleName1 indata/SampleName2
cp /path/to/Sample1_R1.fastq.gz indata/SampleName1/
cp /path/to/Sample1_R2.fastq.gz indata/SampleName1/
cp /path/to/Sample2_R1.fastq.gz indata/SampleName2/
cp /path/to/Sample2_R2.fastq.gz indata/SampleName2/

# 9. Configure the pipeline
vim config/config.yaml  # Edit sample paths and parameters
# For this step, either use vim directly
# or open it from your shared folder (use a Mac or Linux machine; Windows users use notepad++)

# 10. Run the pipeline
snakemake --snakefile workflow/Snakefile --use-conda --cores 16
```

## Expected outputs

- `results/{sample}/{sample}.counts.csv` - Per-sample oligo counts
- `results/oligo_counts_merged_all_samples.csv` - Combined counts across all samples
- `results/oligo_counts_merge_summary.txt` - Summary statistics
- `logs/{sample}.count.log` - Per-sample processing logs
- `logs/merge.log` - Merge operation log

## Configuration File (config/config.yaml)

Key settings to edit:

```yaml
# Path to your oligonucleotide sequences file
oligo_file: "indata/oligo_sequences.txt"

# Output directory for results
output_dir: "results"

# Sample definitions - update with your sample names and FASTQ paths
samples:
  SampleName1:
    R1: "indata/SampleName1/sample1_R1.fastq.gz"
    R2: "indata/SampleName1/sample1_R2.fastq.gz"
  SampleName2:
    R1: "indata/SampleName2/sample2_R1.fastq.gz"
    R2: "indata/SampleName2/sample2_R2.fastq.gz"

# Processing parameters
threads: 16          # Threads per sample (adjust based on qrsh allocation)
batch_size: 10000    # Read pairs per batch
```

## Quick Vim Guide for Editing Config

When you run `vim config/config.yaml`, follow these steps:

1. **Press `i`** - Enter INSERT mode (you'll see `-- INSERT --` at the bottom)

2. **Navigate and edit:**
   - Use arrow keys to move the cursor to the line you want to change
   - Delete the placeholder text (use Backspace or Delete)
   - Copy-paste (or type) the correct values

3. **Press `Esc`** - Exit INSERT mode (back to NORMAL mode)

4. **Save and quit:**
   - Type `:wq` and press Enter
   - This saves your changes and exits vim

**If you make a mistake and want to quit without saving:**
- Press `Esc`, then type `:q!` and press Enter

## Important Notes

### Screen Session Management

Using `screen` protects your work if your SSH connection drops. Key commands:

**Inside a screen session:**
- `Ctrl+A, D` - Detach from screen (keeps it running in background)
- `Ctrl+A, K` - Kill the current screen session

**From the login node:**
```bash
screen -ls                      # List all your screen sessions
screen -r snakemake_job         # Reconnect to your named session
screen -X -S snakemake_job quit # Kill a specific session
```

### Core Allocation

Set `--cores` to be less than or equal to:
- The number of cores requested via `qrsh` (e.g., 16 in the example above)
- **Maximum recommended: 56 cores**

The `threads` parameter in config.yaml controls parallelism within each sample. The `--cores` flag controls how many samples can run in parallel.

### Input Data Requirements

- **Oligo file**: Text file with one oligonucleotide sequence per line, or CSV/TSV with "Sequence" column
- **FASTQ files**: Paired-end reads (R1 and R2) in gzipped format (.fastq.gz or .fq.gz)

## Configuration

Make sure to edit `config/config.yaml` with your sample paths before running the pipeline. See the main [README.md](README.md) for detailed configuration options.
