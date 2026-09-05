"""Round-trip fidelity: reading and rewriting must not alter a single byte.

The supplied VCF has ten columns and the API exposes five. A parser that rebuilt
lines from the parsed fields would silently delete QUAL, FILTER, INFO, FORMAT and
the sample genotype from every row it touched.
"""

from vcf_core.repository import VcfRepository
from vcf_core.storage import replace_lines


def data_rows(path):
    return [line for line in path.read_text().splitlines() if not line.startswith("#")]


def test_reading_and_writing_back_leaves_the_file_byte_identical(vcf_path):
    """The highest-value assertion in the suite."""
    original = vcf_path.read_bytes()
    replace_lines(vcf_path, vcf_path.read_text().splitlines())
    assert vcf_path.read_bytes() == original


def test_every_source_line_matches_the_file_exactly(vcf_path):
    repository = VcfRepository(vcf_path)
    variants = repository.list_variants(limit=1000).items
    assert [variant.source_line for variant in variants] == data_rows(vcf_path)


def test_an_update_leaves_every_other_row_untouched(vcf_path):
    before = data_rows(vcf_path)
    repository = VcfRepository(vcf_path)
    repository.update("rs4000001", "chr1", 1, "rs4000001", "G", "A")

    after = data_rows(vcf_path)
    untouched_before = [row for row in before if "rs4000001" not in row]
    untouched_after = [row for row in after if "rs4000001" not in row]
    assert untouched_after == untouched_before


def test_a_delete_leaves_every_other_row_untouched(vcf_path):
    before = data_rows(vcf_path)
    VcfRepository(vcf_path).delete("rs4000001")
    assert data_rows(vcf_path) == [row for row in before if "rs4000001" not in row]


def test_writes_preserve_the_meta_lines_and_header(vcf_path):
    header_before = [line for line in vcf_path.read_text().splitlines() if line.startswith("#")]
    repository = VcfRepository(vcf_path)
    repository.append("chr1", 1, "rs1", "G", "A")
    repository.update("rs4000001", "chr2", 2, "rs4000001", "T", "C")
    repository.delete("rs4000002")

    header_after = [line for line in vcf_path.read_text().splitlines() if line.startswith("#")]
    assert header_after == header_before


def test_columns_beyond_the_first_five_survive_an_unrelated_write(vcf_path):
    """Row 1 has INFO and FORMAT data the API never sees. It must come back intact."""
    original = data_rows(vcf_path)[0]
    VcfRepository(vcf_path).append("chr1", 1, "rs1", "G", "A")
    assert data_rows(vcf_path)[0] == original
