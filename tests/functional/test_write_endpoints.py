"""Requirements 2, 3 and 4: POST, PUT and DELETE through the full HTTP stack."""

import pytest

VALID = {"CHROM": "chr1", "POS": 1000, "ID": "rs123", "REF": "G", "ALT": "A"}


def data_rows(path):
    return [line for line in path.read_text().splitlines() if not line.startswith("#")]


# --- POST -------------------------------------------------------------------


def test_post_returns_201_and_the_stored_variant(writer_client, vcf_path):
    response = writer_client.post("/variants", VALID, format="json")
    assert response.status_code == 201
    assert response.data == VALID


def test_post_appends_exactly_one_row(writer_client, vcf_path):
    before = len(data_rows(vcf_path))
    writer_client.post("/variants", VALID, format="json")
    assert len(data_rows(vcf_path)) == before + 1


def test_post_pads_the_new_row_to_the_files_column_count(writer_client, vcf_path):
    writer_client.post("/variants", VALID, format="json")
    assert data_rows(vcf_path)[-1] == "chr1\t1000\trs123\tG\tA\t.\t.\t.\t.\t."


def test_post_returns_403_when_the_secret_is_missing(api_client, vcf_path):
    before = vcf_path.read_text()
    assert api_client.post("/variants", VALID, format="json").status_code == 403
    assert vcf_path.read_text() == before


def test_post_returns_403_when_the_secret_is_wrong(api_client, vcf_path):
    api_client.credentials(HTTP_AUTHORIZATION="wrong")
    assert api_client.post("/variants", VALID, format="json").status_code == 403


@pytest.mark.parametrize(
    "override",
    [
        {"CHROM": "chr99"},
        {"CHROM": "chrUn_gl000225"},
        {"POS": -1},
        {"POS": True},
        {"ID": "nope"},
        {"ID": "."},
        {"REF": "CAG"},
        {"ALT": "N"},
    ],
)
def test_post_returns_400_for_values_the_brief_forbids(writer_client, vcf_path, override):
    before = vcf_path.read_text()
    response = writer_client.post("/variants", {**VALID, **override}, format="json")
    assert response.status_code == 400
    assert vcf_path.read_text() == before


@pytest.mark.parametrize("missing", ["CHROM", "POS", "ID", "REF", "ALT"])
def test_post_returns_400_when_a_field_is_absent(writer_client, missing):
    body = {key: value for key, value in VALID.items() if key != missing}
    assert writer_client.post("/variants", body, format="json").status_code == 400


# --- PUT --------------------------------------------------------------------


def test_put_returns_200_and_the_number_of_rows_changed(writer_client):
    response = writer_client.put(
        "/variants?id=rs4000001",
        {**VALID, "ID": "rs4000001"},
        format="json",
    )
    assert response.status_code == 200
    assert response.data == {"updated": 2}


def test_put_rewrites_every_matching_row(writer_client, vcf_path):
    writer_client.put("/variants?id=rs4000001", {**VALID, "ID": "rs4000001"}, format="json")
    changed = [row for row in data_rows(vcf_path) if "rs4000001" in row]
    assert changed == ["chr1\t1000\trs4000001\tG\tA\t.\t.\t.\t.\t."] * 2


def test_put_returns_404_when_nothing_matches(writer_client, vcf_path):
    before = vcf_path.read_text()
    response = writer_client.put("/variants?id=rs999999999", VALID, format="json")
    assert response.status_code == 404
    assert vcf_path.read_text() == before


def test_put_returns_404_for_a_dot_id(writer_client):
    assert writer_client.put("/variants?id=.", VALID, format="json").status_code == 404


def test_put_returns_400_when_the_id_parameter_is_absent(writer_client):
    assert writer_client.put("/variants", VALID, format="json").status_code == 400


def test_put_returns_403_without_the_secret(api_client, vcf_path):
    before = vcf_path.read_text()
    assert api_client.put("/variants?id=rs4000001", VALID, format="json").status_code == 403
    assert vcf_path.read_text() == before


# --- DELETE -----------------------------------------------------------------


def test_delete_returns_204_with_no_body(writer_client):
    response = writer_client.delete("/variants?id=rs4000001")
    assert response.status_code == 204
    assert response.content == b""


def test_delete_removes_every_matching_row(writer_client, vcf_path):
    before = len(data_rows(vcf_path))
    writer_client.delete("/variants?id=rs4000001")
    rows = data_rows(vcf_path)
    assert len(rows) == before - 2
    assert not any("rs4000001" in row for row in rows)


def test_delete_returns_404_when_nothing_matches(writer_client, vcf_path):
    before = vcf_path.read_text()
    assert writer_client.delete("/variants?id=rs999999999").status_code == 404
    assert vcf_path.read_text() == before


def test_delete_returns_404_for_a_dot_id(writer_client, vcf_path):
    """35,895 rows have '.' for ID in the real file. None of them are named '.'."""
    before = vcf_path.read_text()
    assert writer_client.delete("/variants?id=.").status_code == 404
    assert vcf_path.read_text() == before


def test_delete_returns_400_when_the_id_parameter_is_absent(writer_client):
    assert writer_client.delete("/variants").status_code == 400


def test_delete_returns_403_without_the_secret(api_client, vcf_path):
    before = vcf_path.read_text()
    assert api_client.delete("/variants?id=rs4000001").status_code == 403
    assert vcf_path.read_text() == before


# --- structure survives every write ----------------------------------------


@pytest.mark.parametrize("method", ["post", "put", "delete"])
def test_writes_keep_the_file_a_valid_vcf(writer_client, vcf_path, method):
    if method == "post":
        writer_client.post("/variants", VALID, format="json")
    elif method == "put":
        writer_client.put("/variants?id=rs4000001", {**VALID, "ID": "rs4000001"}, format="json")
    else:
        writer_client.delete("/variants?id=rs4000001")

    text = vcf_path.read_text()
    assert "##fileformat=VCFv4.2" in text
    assert any(line.startswith("#CHROM") for line in text.splitlines())
    assert {row.count("\t") for row in data_rows(vcf_path)} == {9}


def test_writes_are_refused_entirely_when_no_secret_is_configured(api_client, settings, vcf_path):
    """An unset secret must deny every write, never match an empty header."""
    settings.VCF_API_SECRET = ""
    api_client.credentials(HTTP_AUTHORIZATION="")
    before = vcf_path.read_text()

    assert api_client.post("/variants", VALID, format="json").status_code == 403
    assert vcf_path.read_text() == before
