"""File-format injection: a field must never be able to write its own row.

The brief marks validation optional. This check is not: the VCF is tab-separated
and newline-delimited, so a tab or newline inside a field would let a caller append
arbitrary rows or destroy the file's column structure.
"""

import pytest

VALID = {"CHROM": "chr1", "POS": 1000, "ID": "rs123", "REF": "G", "ALT": "A"}
ATTACK = "A\tX\tY\nchr9\t999\trs666\tT\tC"


def data_rows(path):
    return [line for line in path.read_text().splitlines() if not line.startswith("#")]


def test_an_alt_carrying_a_tab_and_newline_is_rejected(writer_client, vcf_path):
    before = vcf_path.read_text()
    row_count = len(data_rows(vcf_path))

    response = writer_client.post("/variants", {**VALID, "ALT": ATTACK}, format="json")

    assert response.status_code == 400
    assert vcf_path.read_text() == before
    assert len(data_rows(vcf_path)) == row_count


def test_the_rejection_names_the_control_character_not_just_the_allele_rule(writer_client):
    """Both rules reject this value. The safety one must be among the reasons."""
    response = writer_client.post("/variants", {**VALID, "ALT": ATTACK}, format="json")
    assert "control character" in str(response.data)


@pytest.mark.parametrize("field", ["CHROM", "ID", "REF", "ALT"])
@pytest.mark.parametrize("payload", ["A\tB", "A\nB", "A\rB", "A\x00B"])
def test_no_string_field_accepts_a_control_character(writer_client, vcf_path, field, payload):
    before = vcf_path.read_text()
    response = writer_client.post("/variants", {**VALID, field: payload}, format="json")
    assert response.status_code == 400
    assert vcf_path.read_text() == before


def test_a_put_cannot_inject_a_row_either(writer_client, vcf_path):
    before = vcf_path.read_text()
    response = writer_client.put(
        "/variants?id=rs4000001", {**VALID, "ALT": ATTACK}, format="json"
    )
    assert response.status_code == 400
    assert vcf_path.read_text() == before
