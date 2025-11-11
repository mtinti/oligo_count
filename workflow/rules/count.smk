# Rule: count_oligos
# Counts oligonucleotides in paired FASTQ files for each sample
# ============================================================================

rule count_oligos:
    input:
        R1 = lambda wildcards: config["samples"][wildcards.sample]["R1"],
        R2 = lambda wildcards: config["samples"][wildcards.sample]["R2"],
        oligos = config["oligo_file"]
    output:
        counts = os.path.join(config["output_dir"], "{sample}", "{sample}.counts.csv")
    params:
        sample_name = "{sample}",
        batch_size = config["batch_size"],
        show_progress_bar = config["show_progress_bar"],
        output_dir = lambda wildcards: os.path.join(config["output_dir"], wildcards.sample)
    threads: config["threads"]
    conda:
        "../envs/oligo_counter.yaml"
    log:
        os.path.join("logs", "{sample}.count.log")
    script:
        "../scripts/count_wrapper.py"
