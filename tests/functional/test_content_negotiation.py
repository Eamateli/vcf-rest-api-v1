"""Requirement 1b: the Accept header decides the response format."""

import pytest


def test_no_accept_header_falls_back_to_json(api_client):
    response = api_client.get("/variants", {"limit": 1})
    assert response.status_code == 200
    assert response["Content-Type"].startswith("application/json")


def test_a_wildcard_accept_header_falls_back_to_json(api_client):
    response = api_client.get("/variants", {"limit": 1}, HTTP_ACCEPT="*/*")
    assert response.status_code == 200
    assert response["Content-Type"].startswith("application/json")


def test_explicit_json_returns_json(api_client):
    response = api_client.get("/variants", {"limit": 1}, HTTP_ACCEPT="application/json")
    assert response["Content-Type"].startswith("application/json")


def test_explicit_xml_returns_xml(api_client):
    response = api_client.get("/variants", {"limit": 1}, HTTP_ACCEPT="application/xml")
    assert response.status_code == 200
    assert response["Content-Type"].startswith("application/xml")
    assert response.content.startswith(b"<?xml")


@pytest.mark.parametrize("accept", ["text/csv", "text/html", "application/yaml", "text/plain"])
def test_an_unsupported_accept_header_returns_406(api_client, accept):
    assert api_client.get("/variants", {"limit": 1}, HTTP_ACCEPT=accept).status_code == 406


def test_a_406_still_returns_a_readable_body(api_client):
    """The renderer that just failed negotiation must not be used for the error."""
    response = api_client.get("/variants", {"limit": 1}, HTTP_ACCEPT="text/csv")
    assert response.status_code == 406
    assert b"detail" in response.content


def test_errors_are_rendered_in_the_negotiated_format(api_client):
    response = api_client.get("/variants", {"id": "rs999999999"}, HTTP_ACCEPT="application/xml")
    assert response.status_code == 404
    assert response.content.startswith(b"<?xml")


def test_xml_escapes_ampersands_in_urls(api_client):
    """Next links contain &, which must be escaped or the XML is malformed."""
    response = api_client.get("/variants", {"limit": 1}, HTTP_ACCEPT="application/xml")
    assert b"&amp;" in response.content


def test_quality_values_do_not_override_renderer_order(api_client):
    """Known behaviour: DRF picks by renderer order, not by q-value."""
    response = api_client.get(
        "/variants",
        {"limit": 1},
        HTTP_ACCEPT="application/xml;q=0.9,application/json;q=0.8",
    )
    assert response["Content-Type"].startswith("application/json")
