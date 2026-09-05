"""Turn VCF text lines into Variant objects."""

from collections.abc import Iterator
from pathlib import Path

from vcf_core.errors import MalformedVcfError
from vcf_core.models import Variant

MISSING = "."
MIN_COLUMNS = 5
COLUMN_HEADER_PREFIX = "#CHROM"
COMMENT_PREFIX = "#"


def read_column_names(path: Path) -> list[str]:
    """Return the column names from the #CHROM header line."""
    with path.open() as handle:
        for line in handle:
            if line.startswith(COLUMN_HEADER_PREFIX):
                return line.rstrip("\n").split("\t")
    raise MalformedVcfError(f"no #CHROM header line found in {path}")


def iter_variants(path: Path) -> Iterator[Variant]:
    """Yield one Variant per data row, reading the file lazily."""
    seen_header = False
    with path.open() as handle:
        for line in handle:
            if line.startswith(COLUMN_HEADER_PREFIX):
                seen_header = True
                continue
            if line.startswith(COMMENT_PREFIX) or not line.strip():
                continue
            if not seen_header:
                raise MalformedVcfError(f"data row before the #CHROM header in {path}")
            yield parse_line(line)



def parse_line(line: str) -> Variant:
    """Parse one VCF data line into a Variant.

    The line is kept verbatim in source_line so that columns beyond the five
    the API exposes survive a read-write round trip.
    """
    source_line = line.rstrip("\n")
    fields = source_line.split("\t")

    if len(fields) < MIN_COLUMNS:
        raise MalformedVcfError(
            f"expected at least {MIN_COLUMNS} tab-separated columns, got {len(fields)}"
        )

    chrom, pos, variant_id, ref, alt = fields[:MIN_COLUMNS]

    try:
        position = int(pos)
    except ValueError as exc:
        raise MalformedVcfError(f"POS is not an integer: {pos!r}") from exc

    return Variant(
        chrom=chrom,
        pos=position,
        id=None if variant_id == MISSING else variant_id,
        ref=ref,
        alt=alt,
        source_line=source_line,
    )
