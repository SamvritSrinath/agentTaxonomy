import re
from typing import BinaryIO, Literal

VALID_NT_RE = re.compile(r"^[ACGTUNRYSWKMBDHV\-.]+$", re.IGNORECASE)


class SequenceValidationError(ValueError):
    pass


def _iter_lines(file_obj: BinaryIO):
    file_obj.seek(0)
    for raw in file_obj:
        if isinstance(raw, bytes):
            try:
                line = raw.decode("ascii")
            except UnicodeDecodeError as exc:
                raise SequenceValidationError("Sequence file must be ASCII text") from exc
        else:
            line = raw
        yield line.rstrip("\r\n")


def _first_nonempty_line(file_obj: BinaryIO) -> str | None:
    for line in _iter_lines(file_obj):
        if line.strip():
            return line.strip()
    return None


def _validate_fasta(file_obj: BinaryIO) -> dict:
    records = 0
    bases = 0
    gc = 0
    seen_header = False
    record_has_sequence = False

    for line in _iter_lines(file_obj):
        line = line.strip()
        if not line:
            continue

        if line.startswith(">"):
            if seen_header and not record_has_sequence:
                raise SequenceValidationError("FASTA record has no sequence")
            seen_header = True
            record_has_sequence = False
            records += 1
            continue

        if not seen_header:
            raise SequenceValidationError("FASTA must start with a header line beginning with '>'")

        seq = line.upper()
        if not VALID_NT_RE.match(seq):
            raise SequenceValidationError("FASTA contains invalid nucleotide symbols")

        record_has_sequence = True
        bases += len(seq)
        gc += seq.count("G") + seq.count("C")

    if not seen_header:
        raise SequenceValidationError("Empty FASTA file")
    if not record_has_sequence:
        raise SequenceValidationError("Last FASTA record has no sequence")

    gc_content = f"{(gc / bases * 100):.2f}%" if bases else "0.00%"
    return {
        "format": "fasta",
        "read_count": records,
        "base_count": bases,
        "gc_content": gc_content,
    }


def _next_nonempty(iterator):
    for line in iterator:
        if line.strip():
            return line.strip()
    return None


def _validate_fastq(file_obj: BinaryIO) -> dict:
    iterator = _iter_lines(file_obj)
    records = 0
    bases = 0
    gc = 0

    while True:
        header = _next_nonempty(iterator)
        if header is None:
            break

        try:
            seq = next(iterator).strip()
            plus = next(iterator).strip()
            qual = next(iterator).rstrip("\r\n")
        except StopIteration as exc:
            raise SequenceValidationError("Incomplete FASTQ record") from exc

        if not header.startswith("@"):
            raise SequenceValidationError("FASTQ header must start with '@'")
        if not plus.startswith("+"):
            raise SequenceValidationError("FASTQ separator must start with '+'")
        if not seq:
            raise SequenceValidationError("FASTQ sequence cannot be empty")
        if not VALID_NT_RE.match(seq):
            raise SequenceValidationError("FASTQ contains invalid nucleotide symbols")
        if len(seq) != len(qual):
            raise SequenceValidationError("FASTQ quality length must match sequence length")
        if any(ord(ch) < 33 or ord(ch) > 126 for ch in qual):
            raise SequenceValidationError("FASTQ quality scores must be printable ASCII")

        seq = seq.upper()
        records += 1
        bases += len(seq)
        gc += seq.count("G") + seq.count("C")

    if records == 0:
        raise SequenceValidationError("Empty FASTQ file")

    gc_content = f"{(gc / bases * 100):.2f}%" if bases else "0.00%"
    return {
        "format": "fastq",
        "read_count": records,
        "base_count": bases,
        "gc_content": gc_content,
    }


def validate_upload(
    file_obj: BinaryIO,
    declared_format: Literal["fasta", "fastq"] | str | None = None,
) -> dict:
    first = _first_nonempty_line(file_obj)
    if first is None:
        raise SequenceValidationError("Empty sequence file")

    detected = "fasta" if first.startswith(">") else "fastq" if first.startswith("@") else None
    if detected is None:
        raise SequenceValidationError("Could not detect FASTA or FASTQ format")

    if declared_format:
        declared = declared_format.lower()
        if declared not in {"fasta", "fastq"}:
            raise SequenceValidationError("Declared format must be fasta or fastq")
        if declared != detected:
            raise SequenceValidationError(f"Declared format {declared} does not match detected {detected}")

    file_obj.seek(0)
    if detected == "fasta":
        result = _validate_fasta(file_obj)
    else:
        result = _validate_fastq(file_obj)

    file_obj.seek(0)
    return result
