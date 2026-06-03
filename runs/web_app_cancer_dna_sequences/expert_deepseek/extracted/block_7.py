ALLOWED = {
    "fasta": [".fa", ".fasta"],
    "fastq": [".fq", ".fastq"],
    "bam":   [".bam"],
    "vcf":   [".vcf", ".vcf.gz"],
}

def validate_genomic_file(mime_type, filename):
    # Check extension
    ext = filename.rsplit(".", 1)[-1].lower()
    formats = {
        "application/x-gzip": ".gz",
        "application/gzip": ".gz",
        "text/plain": ".txt",
        "application/octet-stream": "",
    }
    # Simple extension‑based validation; expand for production
    return any(filename.endswith(ext) for exts in ALLOWED.values() for ext in exts)
