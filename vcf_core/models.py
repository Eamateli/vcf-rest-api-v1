"""The Variant: one data row from a VCF file."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Variant:
    """One VCF data row, exposing the five fields the API serves."""

    chrom: str
    pos: int
    id: str | None
    ref: str
    alt: str
    source_line: str
