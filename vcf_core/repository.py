"""Read access to a VCF file: the only place that knows where the data lives."""

from pathlib import Path

from vcf_core.models import Variant
from vcf_core.pagination import DEFAULT_LIMIT, Page, paginate
from vcf_core.parser import iter_data_lines, iter_variants, parse_line, read_column_names


class VcfRepository:
    """Reads variants from one VCF file."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def list_variants(self, offset: int = 0, limit: int = DEFAULT_LIMIT) -> Page[Variant]:
        """Return one page, parsing only the rows that appear on it."""
        lines = paginate(iter_data_lines(self.path), offset=offset, limit=limit)
        return Page(
            items=[parse_line(line) for line in lines.items],
            offset=lines.offset,
            limit=lines.limit,
            has_next=lines.has_next,
        )

    def find_by_id(self, variant_id: str) -> list[Variant]:
        """Every variant with this ID. Empty list when nothing matches."""
        return [variant for variant in iter_variants(self.path) if variant.id == variant_id]

    def column_count(self) -> int:
        """How many columns this file's #CHROM header declares."""
        return len(read_column_names(self.path))
