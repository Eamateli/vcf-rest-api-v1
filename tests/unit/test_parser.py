"""Unit tests for vcf_core.parser."""

import pytest

from vcf_core.errors import MalformedVcfError
from vcf_core.parser import iter_variants, line_id, parse_line, read_column_names

SAMPLE_ROW = "chr1\t12783\trs62635284\tG\tA\t99.03\tFAIL\tAC=2\tGT:DP\t1/1:4"


def test_parse_line_extracts_the_five_api_fields():
    variant = parse_line(SAMPLE_ROW)
    assert variant.chrom == "chr1"
    assert variant.pos == 12783
    assert variant.id == "rs62635284"
    assert variant.ref == "G"
    assert variant.alt == "A"


def test_parse_line_converts_a_dot_id_to_none():
    variant = parse_line("chr1\t62186\t.\tG\tT\t62.74\tFAIL\t.\t.\t.")
    assert variant.id is None


def test_parse_line_keeps_the_source_line_verbatim():
    variant = parse_line(SAMPLE_ROW + "\n")
    assert variant.source_line == SAMPLE_ROW


def test_parse_line_keeps_multi_base_alleles_for_indels():
    variant = parse_line("chr1\t13656\trs1263393206\tCAG\tC\t196.73\tPASS\t.\t.\t.")
    assert variant.ref == "CAG"
    assert variant.alt == "C"


def test_parse_line_accepts_scaffold_chromosomes():
    variant = parse_line("chrUn_gl000225\t1200\t.\tA\tT\t66.33\tFAIL\t.\t.\t.")
    assert variant.chrom == "chrUn_gl000225"


def test_parse_line_raises_when_there_are_fewer_than_five_columns():
    with pytest.raises(MalformedVcfError):
        parse_line("chr1\t12783\trs1")


def test_parse_line_raises_when_pos_is_not_an_integer():
    with pytest.raises(MalformedVcfError):
        parse_line("chr1\tnot_a_number\trs1\tG\tA")

def test_iter_variants_yields_one_variant_per_data_row(vcf_path):
    assert len(list(iter_variants(vcf_path))) == 6


def test_iter_variants_skips_meta_and_header_lines(vcf_path):
    chroms = [variant.chrom for variant in iter_variants(vcf_path)]
    assert "#CHROM" not in chroms
    assert "##fileformat=VCFv4.2" not in chroms


def test_read_column_names_returns_every_column_in_the_header(vcf_path):
    assert len(read_column_names(vcf_path)) == 10


def test_read_column_names_keeps_a_sample_name_containing_spaces(vcf_path):
    assert read_column_names(vcf_path)[-1] == "SAMPLE01 single 20180302"


def test_read_column_names_raises_when_the_header_is_missing(tmp_path):
    path = tmp_path / "noheader.vcf"
    path.write_text("##fileformat=VCFv4.2\n")
    with pytest.raises(MalformedVcfError):
        read_column_names(path)


def test_iter_variants_raises_when_a_data_row_precedes_the_header(tmp_path):
    path = tmp_path / "noheader.vcf"
    path.write_text("##fileformat=VCFv4.2\nchr1\t100\trs1\tG\tA\n")
    with pytest.raises(MalformedVcfError):
        list(iter_variants(path))


def test_line_id_ignores_a_truncated_row():
    """A row with too few columns has no ID to read."""
    assert line_id("chr1\t100") is None


def test_line_id_reports_none_for_a_dot():
    assert line_id("chr1\t100\t.\tG\tA") is None


def test_line_id_reads_the_third_column():
    assert line_id("chr1\t100\trs1\tG\tA") == "rs1"


def test_line_id_ignores_meta_and_header_lines():
    assert line_id("##fileformat=VCFv4.2") is None
    assert line_id("#CHROM\tPOS\tID\tREF\tALT") is None
