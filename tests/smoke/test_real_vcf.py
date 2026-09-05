"""Smoke tests against the real supplied VCF.

Skipped automatically when the file is absent, which is the normal case: it is
100 MB and deliberately not committed. These exist so the synthetic fixture can be
checked against the real thing before submission, rather than trusted.

Run with:  pytest tests/smoke -v
"""

import shutil
import time
from pathlib import Path

import pytest

from vcf_core.parser import iter_variants, read_column_names
from vcf_core.repository import VcfRepository

REAL_VCF = Path("data/Python_eng_assignment.vcf")

pytestmark = pytest.mark.skipif(
    not REAL_VCF.exists(), reason="the supplied VCF is not present (it is never committed)"
)


@pytest.fixture(scope="module")
def real_copy(tmp_path_factory) -> Path:
    """A copy, so a failing write test can never damage the original."""
    destination = tmp_path_factory.mktemp("real") / REAL_VCF.name
    shutil.copy(REAL_VCF, destination)
    return destination


def test_the_header_declares_ten_columns():
    columns = read_column_names(REAL_VCF)
    assert len(columns) == 10
    assert columns[0] == "#CHROM"
    assert " " in columns[-1], "the sample column name contains spaces; never split on whitespace"


def test_every_row_parses_without_error():
    """No row is silently skipped, and none raises."""
    count = sum(1 for _ in iter_variants(REAL_VCF))
    assert count > 200_000


def test_the_file_contains_the_edge_cases_the_fixture_mirrors():
    missing_ids = 0
    multi_base = 0
    scaffolds = set()

    for variant in iter_variants(REAL_VCF):
        if variant.id is None:
            missing_ids += 1
        if len(variant.ref) > 1 or len(variant.alt) > 1:
            multi_base += 1
        if not variant.chrom.removeprefix("chr").isalnum():
            scaffolds.add(variant.chrom)

    assert missing_ids > 30_000, "rows with '.' for ID"
    assert multi_base > 10_000, "indels"
    assert scaffolds, "unplaced scaffold chromosomes"


def test_the_first_page_is_fast_and_deep_pages_are_not():
    """Documents the O(n) shape on the real file rather than on a 50-row fixture."""
    repository = VcfRepository(REAL_VCF)

    start = time.perf_counter()
    first = repository.list_variants(offset=0, limit=20)
    first_page_seconds = time.perf_counter() - start

    start = time.perf_counter()
    deep = repository.list_variants(offset=200_000, limit=20)
    deep_page_seconds = time.perf_counter() - start

    assert len(first.items) == 20
    assert len(deep.items) == 20
    assert first_page_seconds < 0.05, "the first page must not read the whole file"
    assert deep_page_seconds > first_page_seconds


def test_a_duplicate_rs_id_returns_more_than_one_row():
    matches = VcfRepository(REAL_VCF).find_by_id("rs10207725")
    assert len(matches) > 1


def test_a_dot_id_matches_nothing():
    assert VcfRepository(REAL_VCF).find_by_id(".") == []


def test_reading_and_writing_back_the_real_file_is_byte_identical(real_copy):
    """The highest-value assertion, run against 100 MB rather than 50 rows."""
    from vcf_core.storage import replace_lines

    original = real_copy.read_bytes()
    replace_lines(real_copy, real_copy.read_text().splitlines())
    assert real_copy.read_bytes() == original


def test_appending_to_the_real_file_keeps_its_column_count(real_copy):
    repository = VcfRepository(real_copy)
    repository.append("chr1", 999_999, "rs99999999", "G", "A")

    with real_copy.open() as handle:
        widths = {line.count("\t") for line in handle if not line.startswith("#")}
    assert widths == {9}
