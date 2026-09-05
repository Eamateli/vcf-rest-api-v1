"""Validation rules for data arriving over the API.

Applied on write only. Reads stay permissive: the supplied VCF contains
scaffold chromosomes and multi-base alleles that these rules would reject.
"""

import re

from vcf_core.errors import ValidationError

CHROM_PATTERN = re.compile(r"chr([1-9]|1\d|2[0-2]|X|Y|M)")
ID_PATTERN = re.compile(r"rs\d+")
CONTROL_CHARACTERS = re.compile(r"[\x00-\x1f\x7f]")
ALLELES = frozenset({"A", "C", "G", "T", "."})


def validate_variant(chrom: str, pos: int, variant_id: str, ref: str, alt: str) -> None:
    """Raise ValidationError naming every field that fails."""
    problems: list[str] = []

    # Structural safety first: a tab or newline in any field would let a caller
    # write extra rows or break the file's column layout.
    for name, value in (("CHROM", chrom), ("ID", variant_id), ("REF", ref), ("ALT", alt)):
        if CONTROL_CHARACTERS.search(value):
            problems.append(f"{name} contains a tab, newline or control character")

    if not CHROM_PATTERN.fullmatch(chrom):
        problems.append(f"CHROM must be chr1-chr22, chrX, chrY or chrM, got {chrom!r}")

    # bool is a subclass of int in Python, so True would otherwise pass as a position.
    if isinstance(pos, bool) or not isinstance(pos, int) or pos < 1:
        problems.append(f"POS must be a positive integer, got {pos!r}")

    if not ID_PATTERN.fullmatch(variant_id):
        problems.append(f"ID must be rs followed by digits, got {variant_id!r}")

    for name, value in (("REF", ref), ("ALT", alt)):
        if value not in ALLELES:
            problems.append(f"{name} must be one of A, C, G, T or '.', got {value!r}")

    if problems:
        raise ValidationError("; ".join(problems))
