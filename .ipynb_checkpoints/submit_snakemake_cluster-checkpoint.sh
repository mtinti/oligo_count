#!/bin/bash
#$ -adds l_hard local_free 200G
#$ -mods l_hard m_mem_free 20G
#$ -adds l_hard avx 1
#$ -cwd
#$ -V
#$ -j y
#$ -N snakemake_oligo
#$ -o snakemake_oligo_errors_$JOB_ID
#$ -pe smp 40

# Exit on error and undefined variables
set -e
set -u

##############################################################################
# CONFIGURATION - UPDATE THESE VARIABLES AS NEEDED
##############################################################################

# Number of cores for Snakemake to use (should match -pe smp above)
CORES=40

# Conda prefix for Snakemake environments (where conda envs will be stored)
# If empty, Snakemake will use default location (.snakemake/conda)
# Example: SNAKEMAKE_CONDA_PREFIX="${HOME}/.snakemake/conda"
SNAKEMAKE_CONDA_PREFIX=""

##############################################################################
# CONDA INITIALIZATION
##############################################################################

echo "Initializing conda..."

# Initialize conda for bash shell
# This allows Snakemake to create new conda environments for rules
if [ -f "${HOME}/miniconda3/etc/profile.d/conda.sh" ]; then
    source "${HOME}/miniconda3/etc/profile.d/conda.sh"
elif [ -f "${HOME}/anaconda3/etc/profile.d/conda.sh" ]; then
    source "${HOME}/anaconda3/etc/profile.d/conda.sh"
elif [ -f "/opt/conda/etc/profile.d/conda.sh" ]; then
    source "/opt/conda/etc/profile.d/conda.sh"
else
    echo "WARNING: Could not find conda installation"
    echo "Conda environments may not work properly"
fi

echo "Conda initialized"

##############################################################################
# SETUP - Copy project to TMPDIR and run from there
##############################################################################

echo "Job started at: $(date)"
echo "Job ID: $JOB_ID"
echo "Running on node: $(hostname)"
echo "TMPDIR: ${TMPDIR}"

# Save the original submission directory
SUBMIT_DIR=$(pwd)
echo "Submission directory: ${SUBMIT_DIR}"

# Create project directory in TMPDIR
PROJECT_NAME=$(basename "${SUBMIT_DIR}")
TMPDIR_PROJECT="${TMPDIR}/${PROJECT_NAME}"

echo "Copying project to TMPDIR..."
echo "Source: ${SUBMIT_DIR}"
echo "Destination: ${TMPDIR_PROJECT}"

# Copy entire project to TMPDIR (excluding hidden files like .git, .snakemake)
# Note: indata/ IS included because FASTQ files need fast local I/O
mkdir -p "${TMPDIR_PROJECT}"
rsync -av \
    --exclude='.git' \
    --exclude='.snakemake' \
    --exclude='results' \
    --exclude='logs' \
    --exclude='*.pyc' \
    --exclude='__pycache__' \
    "${SUBMIT_DIR}/" "${TMPDIR_PROJECT}/"

echo "Project copied successfully"

# Check disk usage after copy
echo "Disk usage in TMPDIR:"
df -h "${TMPDIR}"
echo "Project size in TMPDIR:"
du -sh "${TMPDIR_PROJECT}"
du -sh "${TMPDIR_PROJECT}/indata" 2>/dev/null || echo "No indata directory found"

# Change to TMPDIR project directory
cd "${TMPDIR_PROJECT}"
echo "Working directory: $(pwd)"

##############################################################################
# RUN SNAKEMAKE FROM TMPDIR
##############################################################################

echo "Starting Snakemake workflow at: $(date)"

# Build snakemake command with optional conda prefix
SNAKEMAKE_CMD="snakemake --snakefile workflow/Snakefile --configfile config/config.yaml --cores ${CORES} --use-conda --rerun-incomplete --printshellcmds"

if [ -n "${SNAKEMAKE_CONDA_PREFIX}" ]; then
    echo "Using conda prefix: ${SNAKEMAKE_CONDA_PREFIX}"
    SNAKEMAKE_CMD="${SNAKEMAKE_CMD} --conda-prefix ${SNAKEMAKE_CONDA_PREFIX}"
fi

# Run Snakemake from TMPDIR (results will be created here)
echo "Running: ${SNAKEMAKE_CMD}"
${SNAKEMAKE_CMD}

echo "Snakemake workflow completed at: $(date)"

##############################################################################
# COPY RESULTS BACK TO SUBMISSION DIRECTORY
##############################################################################

echo "Copying results from TMPDIR to submission directory..."
echo "Source: ${TMPDIR_PROJECT}/results"
echo "Destination: ${SUBMIT_DIR}/results"

# Create results directory in submission directory if it doesn't exist
mkdir -p "${SUBMIT_DIR}/results"

# Copy results directory back to submission directory
if [ -d "${TMPDIR_PROJECT}/results" ]; then
    rsync -av "${TMPDIR_PROJECT}/results/" "${SUBMIT_DIR}/results/"
    echo "Results copied successfully"
else
    echo "WARNING: No results directory found in TMPDIR project"
fi

# Also copy back logs
echo "Copying logs back to submission directory..."
mkdir -p "${SUBMIT_DIR}/logs"
if [ -d "${TMPDIR_PROJECT}/logs" ]; then
    rsync -av "${TMPDIR_PROJECT}/logs/" "${SUBMIT_DIR}/logs/"
    echo "Logs copied successfully"
fi

echo "File copy completed at: $(date)"

# List final files
echo "Files in final results directory:"
ls -lh "${SUBMIT_DIR}/results" || echo "Results directory is empty or doesn't exist"

echo ""
echo "Merged output files:"
ls -lh "${SUBMIT_DIR}/results/"*merged* 2>/dev/null || echo "No merged files found"
ls -lh "${SUBMIT_DIR}/results/"*summary* 2>/dev/null || echo "No summary files found"

# Return to submission directory
cd "${SUBMIT_DIR}"

echo "Job completed successfully at: $(date)"
