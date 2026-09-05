"""Functional tests for GET /variants, through the full HTTP stack."""

import pytest


def test_get_returns_every_row_when_the_page_is_large_enough(api_client):
    response = api_client.get("/variants")
    assert response.status_code == 200
    assert len(response.data["results"]) == 6


def test_limit_controls_the_page_size(api_client):
    response = api_client.get("/variants", {"limit": 2})
    assert len(response.data["results"]) == 2


def test_the_first_page_has_a_next_link_and_no_previous(api_client):
    response = api_client.get("/variants", {"limit": 2})
    assert response.data["previous"] is None
    assert "offset=2" in response.data["next"]


def test_the_last_page_has_a_previous_link_and_no_next(api_client):
    response = api_client.get("/variants", {"offset": 4, "limit": 2})
    assert response.data["next"] is None
    assert "offset=2" in response.data["previous"]


def test_variants_use_the_vcf_column_names(api_client):
    variant = api_client.get("/variants", {"limit": 1}).data["results"][0]
    assert set(variant) == {"CHROM", "POS", "ID", "REF", "ALT"}


def test_a_row_without_an_id_serialises_as_null(api_client):
    results = api_client.get("/variants").data["results"]
    assert any(variant["ID"] is None for variant in results)


def test_indels_survive_the_round_trip_to_json(api_client):
    variant = api_client.get("/variants", {"id": "rs1263393206"}).data[0]
    assert (variant["REF"], variant["ALT"]) == ("CAG", "C")


def test_id_returns_every_matching_row(api_client):
    response = api_client.get("/variants", {"id": "rs4000001"})
    assert response.status_code == 200
    assert len(response.data) == 2


def test_id_returns_404_when_nothing_matches(api_client):
    assert api_client.get("/variants", {"id": "rs999999999"}).status_code == 404


def test_a_dot_id_returns_404(api_client):
    """'.' marks a row with no ID, so no row is named '.'."""
    assert api_client.get("/variants", {"id": "."}).status_code == 404


def test_an_empty_id_returns_404_rather_than_the_first_page(api_client):
    """?id= is a lookup for nothing, not an absent parameter."""
    assert api_client.get("/variants", {"id": ""}).status_code == 404


@pytest.mark.parametrize(
    "params", [{"limit": "abc"}, {"offset": "x"}, {"offset": -1}, {"limit": 0}]
)
def test_invalid_pagination_parameters_return_400(api_client, params):
    assert api_client.get("/variants", params).status_code == 400
