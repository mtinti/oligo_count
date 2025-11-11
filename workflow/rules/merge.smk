# Rule: merge_counts
# Merges all individual count files into a single consolidated file
# ============================================================================

rule merge_counts:
    input:
        counts = expand(os.path.join(config["output_dir"], "{sample}", "{sample}.counts.csv"),
                       sample=SAMPLES)
    output:
        merged = os.path.join(config["output_dir"], f"{config['merge_prefix']}_merged_all_samples.csv"),
        summary = os.path.join(config["output_dir"], f"{config['merge_prefix']}_merge_summary.txt")
    params:
        results_dir = config["output_dir"],
        output_prefix = os.path.join(config["output_dir"], config["merge_prefix"])
    conda:
        "../envs/oligo_counter.yaml"
    log:
        "logs/merge.log"
    shell:
        """
        python workflow/scripts/merge_oligo_counts.py \\
            -r {params.results_dir} \\
            -o {params.output_prefix} \\
            -v > {log} 2>&1
        """
