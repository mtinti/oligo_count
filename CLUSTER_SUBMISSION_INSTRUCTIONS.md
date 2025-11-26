# Cluster Submission Instructions

## Overview

The `submit_snakemake_cluster.sh` script copies your entire project (including input data) to TMPDIR (fast local disk), runs the Snakemake workflow there, then copies results back to your submission directory.

## Prerequisites

**Important**: Before submitting, ensure you have:
1. Activated your conda environment with snakemake installed
2. Configured your `config/config.yaml` file with sample paths
3. Placed your input data in the `indata/` directory:
   - Oligonucleotide sequences file
   - Paired-end FASTQ files for each sample

The script uses the `-V` flag to export your current environment variables to the compute node.

## Before Submitting

### 1. Adjust Resource Requirements

Edit `submit_snakemake_cluster.sh` and modify these SGE directives based on your workflow needs:

```bash
#$ -adds l_hard local_free 200G    # Adjust local disk space needed
#$ -mods l_hard m_mem_free 20G     # Adjust memory per core
#$ -pe smp 40                       # Adjust number of cores
#$ -N snakemake_oligo               # Change job name if desired
#$ -o snakemake_oligo_errors_$JOB_ID  # Change error log filename
```

**Important**:
- Set `local_free` based on input FASTQ size PLUS results size (default: 200G)
- Set `m_mem_free` based on memory requirements (default: 20G )
- Set `smp` to desired number of parallel cores (default: 40)
- Update the `CORES` variable in the script to match `-pe smp`

### 2. Update CORES Variable

In the script, update this variable to match your `-pe smp` value:

```bash
CORES=40                   # Should match -pe smp value
```

### 3. Verify Input Data Location

Ensure your input data is in the correct location:

```
count_oligo/
├── indata/
│   ├── oligo_sequences.txt      # Your oligo sequences
│   ├── SampleName1/
│   │   ├── sample1_R1.fastq.gz
│   │   └── sample1_R2.fastq.gz
│   └── SampleName2/
│       ├── sample2_R1.fastq.gz
│       └── sample2_R2.fastq.gz
└── config/
    └── config.yaml              # Updated with correct paths
```

## Submitting the Job

### Basic Submission

From the workflow directory, with your conda environment activated:

```bash
# Ensure conda environment is activated
conda activate snakemake

# Submit the job
qsub submit_snakemake_cluster.sh
```

### Check Job Status

```bash
qstat                      # View all your jobs
qstat -j <job_id>         # View detailed info for specific job
```

### Monitor Progress

```bash
# Watch the error/output log (filename shown when job is submitted)
tail -f snakemake_oligo_errors_<JOB_ID>
```

## How It Works

1. **Environment Export**: The `-V` flag exports your current conda environment to the compute node

2. **Project Copy**: Copies entire project to `$TMPDIR` (excluding .git, .snakemake, results, logs)
   - **Note**: The `indata/` directory with FASTQ files IS copied to TMPDIR for fast I/O

3. **Run from TMPDIR**: Changes to TMPDIR copy and runs Snakemake there
   - All processing happens on fast local disk
   - All intermediate files stay in TMPDIR

4. **Copy Results Back**: After completion, copies:
   - `results/` directory to your submission directory
   - `logs/` directory to your submission directory

5. **User Visibility**: Final results appear in your submission directory's `results/` folder

## Advantages of This Approach

- **No conda activation needed** - Uses your existing environment via `-V` flag
- **Fast I/O** - All operations happen on local TMPDIR disk (critical for FASTQ processing)
- **Simple** - No need for path overrides
- **Clean** - Temporary files stay in TMPDIR and are auto-cleaned

## Troubleshooting

### Job Fails Before Copy

If the job fails during Snakemake execution, files remain in TMPDIR and are lost. Check logs to identify the issue.

### Insufficient TMPDIR Space

If input FASTQ files + results exceed `local_free` allocation:
- Increase `#$ -adds l_hard local_free` value
- Monitor with `df -h $TMPDIR` during job execution
- **Tip**: Compressed FASTQ files (.fastq.gz) are much smaller than uncompressed

### Memory Issues

If job is killed due to memory:
- Increase `#$ -mods l_hard m_mem_free` value
- Reduce `#$ -pe smp` cores and `CORES` variable
- Reduce `batch_size` in config.yaml (fewer read pairs held in memory)

### Conda Environment Not Found

If you get errors about missing commands (snakemake):
- Make sure you activated your conda environment BEFORE running qsub
- The `-V` flag only exports the environment that exists when you submit
- Verify: `conda activate snakemake` then `qsub submit_snakemake_cluster.sh`

### rsync Command Not Found

If rsync is not available on the cluster:
- Replace `rsync -av` with `cp -r` in the submission script
- Open the script and change lines with `rsync` to use `cp` instead

### FASTQ Files Not Found

If the pipeline reports missing FASTQ files:
- Check that paths in `config/config.yaml` are relative to the project root
- Verify FASTQ files exist in `indata/` before submitting
- Ensure sample names in config match directory names

## Advanced Usage

### Adding Additional Snakemake Options

Edit the snakemake command in the script to add any flags you need:

```bash
snakemake \
    --snakefile workflow/Snakefile \
    --cores ${CORES} \
    --rerun-incomplete \
    --printshellcmds \
    --use-conda \
    --conda-prefix /path/to/conda/envs
```

### Running a Dry-Run First

Before submitting to the cluster, test your configuration locally:

```bash
snakemake --snakefile workflow/Snakefile --use-conda -n
```

This will show what the pipeline would do without actually running it.

### Estimating Disk Space Requirements

To estimate how much `local_free` space you need:

```bash
# Check input data size
du -sh indata/

# Add ~20% overhead for results and temporary files
```
