"""Read access to a VCF file: the only place that knows where the data lives."""

from collections.abc import Iterator
from pathlib import Path

from vcf_core import audit
from vcf_core.models import Variant
from vcf_core.pagination import DEFAULT_LIMIT, Page, paginate
from vcf_core.parser import (
    MISSING,
    iter_data_lines,
    iter_variants,
    line_id,
    parse_line,
    read_column_names,
)
from vcf_core.storage import append_line, file_lock, replace_lines
from vcf_core.validation import validate_variant


class VcfRepository:
    """Reads variants from one VCF file."""

    def __init__(self, path: Path, audit_path: Path | None = None) -> None:
        self.path = path
        self.audit_path = audit_path

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
        
    def append(self, chrom: str, pos: int, variant_id: str, ref: str, alt: str) -> Variant:
        """Validate and append one row, padded out to this file's column count."""
        validate_variant(chrom, pos, variant_id, ref, alt)

        with file_lock(self.path):
            column_count = len(read_column_names(self.path))
            fields = [chrom, str(pos), variant_id, ref, alt]
            fields += [MISSING] * max(0, column_count - len(fields))
            line = "\t".join(fields)
            append_line(self.path, line)
            self._record("POST", variant_id, before=None,
                         after=_payload(chrom, pos, variant_id, ref, alt))

        return parse_line(line)
   

    def update(
        self, variant_id: str, chrom: str, pos: int, new_id: str, ref: str, alt: str
    ) -> int:
        """Replace every row matching variant_id. Returns how many rows changed."""
        validate_variant(chrom, pos, new_id, ref, alt)

        with file_lock(self.path):
            before = self._matching_lines(variant_id)
            if not before:
                return 0

            column_count = len(read_column_names(self.path))
            fields = [chrom, str(pos), new_id, ref, alt]
            fields += [MISSING] * max(0, column_count - len(fields))
            replace_lines(self.path, self._replacing(variant_id, "\t".join(fields)))
            self._record("PUT", variant_id, before=before,
                         after=_payload(chrom, pos, new_id, ref, alt))

        return len(before)

    def delete(self, variant_id: str) -> int:
        """Remove every row matching variant_id. Returns how many were removed."""
        with file_lock(self.path):
            before = self._matching_lines(variant_id)
            if not before:
                return 0

            replace_lines(self.path, self._without(variant_id))
            self._record("DELETE", variant_id, before=before, after=None)

        return len(before)

    def _matching_lines(self, variant_id: str) -> list[str]:
        """The raw text of every row carrying this ID, verbatim."""
        with self.path.open() as handle:
            stripped = (line.rstrip("\n") for line in handle)
            return [line for line in stripped if line_id(line) == variant_id]

    def _record(
        self,
        method: str,
        variant_id: str,
        *,
        before: list[str] | None,
        after: dict[str, object] | None,
    ) -> None:
        """Write one audit entry, inside the caller's lock. No-op without a path."""
        if self.audit_path is not None:
            audit.record(
                self.audit_path,
                method=method,
                variant_id=variant_id,
                before=before,
                after=after,
            )

    def _replacing(self, variant_id: str, replacement: str) -> Iterator[str]:
        """Every line of the file, with matching rows swapped for the replacement."""
        with self.path.open() as handle:
            for line in handle:
                stripped = line.rstrip("\n")
                yield replacement if line_id(stripped) == variant_id else stripped

    def _without(self, variant_id: str) -> Iterator[str]:
        """Every line of the file except rows carrying this ID."""
        with self.path.open() as handle:
            for line in handle:
                stripped = line.rstrip("\n")
                if line_id(stripped) != variant_id:
                    yield stripped


def _payload(chrom: str, pos: int, variant_id: str, ref: str, alt: str) -> dict[str, object]:
    """The five API fields, keyed as the audit log records them."""
    return {"CHROM": chrom, "POS": pos, "ID": variant_id, "REF": ref, "ALT": alt}
