"""Unit tests for vcf_core.validation."""

import pytest

from vcf_core.errors import ValidationError
from vcf_core.validation import validate_variant

VALID = {"chrom": "chr1", "pos": 1000, "variant_id": "rs123", "ref": "G", "alt": "A"}


def valid_except(**overrides):
    """A valid payload with one field replaced, so each test changes one thing."""
    return {**VALID, **overrides}


def test_a_valid_variant_passes():
    validate_variant(**VALID)


@pytest.mark.parametrize("chrom", ["chr1", "chr9", "chr10", "chr22", "chrX", "chrY", "chrM"])
def test_chrom_accepts_every_value_the_brief_allows(chrom):
    validate_variant(**valid_except(chrom=chrom))


@pytest.mark.parametrize("chrom", ["chr0", "chr23", "chr", "1", "CHR1", "chrx", "chrUn_gl000225"])
def test_chrom_rejects_values_outside_the_brief(chrom):
    with pytest.raises(ValidationError):
        validate_variant(**valid_except(chrom=chrom))


@pytest.mark.parametrize("pos", [1, 249239808])
def test_pos_accepts_positive_integers(pos):
    validate_variant(**valid_except(pos=pos))


@pytest.mark.parametrize("pos", [0, -1, "1000", 12.5, True, None])
def test_pos_rejects_anything_that_is_not_a_positive_integer(pos):
    with pytest.raises(ValidationError):
        validate_variant(**valid_except(pos=pos))


@pytest.mark.parametrize("variant_id", ["rs1", "rs62635284"])
def test_id_accepts_rs_followed_by_digits(variant_id):
    validate_variant(**valid_except(variant_id=variant_id))


@pytest.mark.parametrize("variant_id", [".", "rs", "RS123", "rs12a", "123"])
def test_id_rejects_anything_else(variant_id):
    with pytest.raises(ValidationError):
        validate_variant(**valid_except(variant_id=variant_id))


@pytest.mark.parametrize("allele", ["A", "C", "G", "T", "."])
def test_ref_and_alt_accept_single_bases_and_the_missing_marker(allele):
    validate_variant(**valid_except(ref=allele, alt=allele))


@pytest.mark.parametrize("allele", ["CAG", "a", "N", "", "AT"])
def test_ref_rejects_anything_else(allele):
    with pytest.raises(ValidationError):
        validate_variant(**valid_except(ref=allele))


def test_alt_containing_a_tab_and_a_newline_is_rejected():
    with pytest.raises(ValidationError, match="control character"):
        validate_variant(**valid_except(alt="A\tX\tY\nchr9\t999\trs666\tT\tC"))


@pytest.mark.parametrize("field", ["chrom", "variant_id", "ref", "alt"])
def test_every_string_field_rejects_a_tab(field):
    with pytest.raises(ValidationError, match="control character"):
        validate_variant(**valid_except(**{field: "A\tB"}))


def test_every_failure_is_reported_together():
    with pytest.raises(ValidationError) as caught:
        validate_variant(chrom="chr99", pos=-1, variant_id="nope", ref="X", alt="Y")
    message = str(caught.value)
    for field in ("CHROM", "POS", "ID", "REF", "ALT"):
        assert field in message
