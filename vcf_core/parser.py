"""Turn VCF text lines into Variant objects."""

from vcf_core.errors import MalformedVcfError
from vcf_core.models import Variant

MISSING = "."
MIN_COLUMNS = 5


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
