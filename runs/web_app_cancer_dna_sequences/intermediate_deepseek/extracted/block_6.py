import re
from typing import Tuple, Optional

def validate_fasta(content: str) -> Tuple[bool, Optional[str]]:
    """Check basic FASTA format: >header followed by lines of [ATGCNatgcn]"""
    lines = content.splitlines()
    if not lines:
        return False, "Empty file"
    if not lines[0].startswith('>'):
        return False, "First line must start with '>'"
    # check that every sequence line contains valid nucleotides
    for i, line in enumerate(lines[1:], start=2):
        if line.startswith('>'):
            # next record – fine, but we only validate first record for quick check
            break
        if not re.fullmatch(r'[ATGCNatgcn\s]+', line):
            return False, f"Invalid nucleotide at line {i}"
    return True, None

def validate_fastq(content: str) -> Tuple[bool, Optional[str]]:
    """Basic FASTQ: @header, sequence, +, quality (same length)"""
    lines = content.splitlines()
    if len(lines) < 4:
        return False, "Too few lines"
    if not lines[0].startswith('@'):
        return False, "First line must start with '@'"
    if not lines[2].startswith('+'):
        return False, "Third line must start with '+'"
    seq = lines[1]
    qual = lines[3]
    if len(seq) != len(qual):
        return False, "Sequence and quality length mismatch"
    if not re.fullmatch(r'[ATGCNatgcn]+', seq):
        return False, "Sequence contains invalid characters"
    return True, None

def detect_file_type(filename: str) -> Optional[str]:
    ext = filename.lower()
    if ext.endswith('.fasta') or ext.endswith('.fa') or ext.endswith('.fna'):
        return 'fasta'
    if ext.endswith('.fastq') or ext.endswith('.fq'):
        return 'fastq'
    return None
