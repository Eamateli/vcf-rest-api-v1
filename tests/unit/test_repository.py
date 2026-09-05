"""Unit tests for vcf_core.repository."""

from pathlib import Path

import pytest

from vcf_core.repository import VcfRepository


@pytest.fixture
def repository(vcf_path: Path) -> VcfRepository:
    """A repository pointed at this test's own throwaway VCF."""
    return VcfRepository(vcf_path)


def test_list_variants_returns_the_first_page(repository):
    page = repository.list_variants(offset=0, limit=2)
    assert [variant.pos for variant in page.items] == [12783, 13656]
    assert page.has_next is True
    assert page.next_offset == 2
    assert page.previous_offset is None


def test_list_variants_knows_when_it_reaches_the_last_page(repository):
    page = repository.list_variants(offset=4, limit=2)
    assert len(page.items) == 2
    assert page.has_next is False
    assert page.next_offset is None
    assert page.previous_offset == 2


def test_list_variants_past_the_end_is_empty(repository):
    page = repository.list_variants(offset=100, limit=20)
    assert page.items == []
    assert page.has_next is False


def test_list_variants_returns_every_row_when_the_limit_is_large(repository):
    assert len(repository.list_variants(limit=1000).items) == 6


def test_find_by_id_returns_every_matching_row(repository):
    matches = repository.find_by_id("rs4000001")
    assert len(matches) == 2
    assert [variant.chrom for variant in matches] == ["chr2", "chr3"]


def test_find_by_id_returns_a_single_match_as_a_list(repository):
    assert len(repository.find_by_id("rs62635284")) == 1


def test_find_by_id_returns_nothing_for_an_unknown_id(repository):
    assert repository.find_by_id("rs999999999") == []


def test_find_by_id_returns_nothing_for_a_dot(repository):
    """'.' marks a row with no ID, so no row is named '.'. This is the 404 case."""
    assert repository.find_by_id(".") == []


def test_column_count_comes_from_the_header(repository):
    assert repository.column_count() == 10


def test_indels_are_read_without_modification(repository):
    variant = repository.find_by_id("rs1263393206")[0]
    assert (variant.ref, variant.alt) == ("CAG", "C")


def test_scaffold_chromosomes_are_read(repository):
    chroms = [variant.chrom for variant in repository.list_variants(limit=1000).items]
    assert "chrUn_gl000225" in chroms


def test_columns_beyond_the_first_five_survive_a_read(repository):
    variant = repository.list_variants(limit=1).items[0]
    fields = variant.source_line.split("\t")
    assert len(fields) == 10
    assert fields[7] == "AC=2"


def test_source_lines_reproduce_every_data_row_exactly(repository, vcf_path):
    """Reading must not alter a single character of any row."""
    original = [
        line for line in vcf_path.read_text().splitlines() if not line.startswith("#")
    ]
    variants = repository.list_variants(limit=1000).items
    assert [variant.source_line for variant in variants] == original
