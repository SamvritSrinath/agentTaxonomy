import os
import re
from fastapi import HTTPException

ALLOWED_KINDS = {"FASTA", "FASTQ", "BAM", "VCF"}

EXTENSION_KIND = {
    ".fa": "FASTA",
    ".fasta": "FASTA",
    ".fna": "FASTA",
    ".fq": "FASTQ",
    ".fastq": "FASTQ",
    ".bam": "BAM",
    ".vcf": "VCF",
    ".vcf.gz": "VCF",
}


SAFE_FILENAME = re.compile(r"^[A-Za-z0-9._+-]+$")


def safe_filename(filename: str) -> str:
    base = os.path.basename(filename)

    if base != filename or not SAFE_FILENAME.match(base):
        raise HTTPException(status_code=400, detail="unsafe filename")

    return base


def detect_kind(filename: str) -> str:
    lowered = filename.lower()

    for ext, kind in EXTENSION_KIND.items():
        if lowered.endswith(ext):
            return kind

    raise HTTPException(status_code=400, detail="unsupported genomic file type")


def validate_declared_kind(filename: str, declared: str | None) -> str:
    detected = detect_kind(filename)

    if declared and declared.upper() != detected:
        raise HTTPException(status_code=400, detail="declared kind does not match extension")

    return detected
