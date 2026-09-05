"""Requirement 1c: ETag and 304 Not Modified."""

import os

NEW_ROW = "chr1\t999999\trs777777\tG\tA\t50.0\tPASS\tAC=1\tGT:DP\t0/1:9\n"


def test_a_get_returns_a_quoted_etag(api_client):
    etag = api_client.get("/variants", {"limit": 2})["ETag"]
    assert etag.startswith('"') and etag.endswith('"')


def test_a_matching_if_none_match_returns_304_with_no_body(api_client):
    etag = api_client.get("/variants", {"limit": 2})["ETag"]
    response = api_client.get("/variants", {"limit": 2}, HTTP_IF_NONE_MATCH=etag)
    assert response.status_code == 304
    assert response.content == b""


def test_a_non_matching_if_none_match_returns_the_full_response(api_client):
    response = api_client.get("/variants", {"limit": 2}, HTTP_IF_NONE_MATCH='"nonsense"')
    assert response.status_code == 200


def test_the_etag_ignores_query_parameter_order(api_client):
    first = api_client.get("/variants?limit=2&offset=0")["ETag"]
    second = api_client.get("/variants?offset=0&limit=2")["ETag"]
    assert first == second


def test_different_pages_have_different_etags(api_client):
    first = api_client.get("/variants", {"limit": 2, "offset": 0})["ETag"]
    second = api_client.get("/variants", {"limit": 2, "offset": 2})["ETag"]
    assert first != second


def test_json_and_xml_have_different_etags(api_client):
    """The same URL produces two different bodies, so it needs two fingerprints."""
    as_json = api_client.get("/variants", {"limit": 2}, HTTP_ACCEPT="application/json")["ETag"]
    as_xml = api_client.get("/variants", {"limit": 2}, HTTP_ACCEPT="application/xml")["ETag"]
    assert as_json != as_xml


def test_a_304_reads_nothing_from_the_vcf(api_client, vcf_path):
    """The brief forbids file access on a cache hit. Deleting the file proves it."""
    etag = api_client.get("/variants", {"limit": 2})["ETag"]
    vcf_path.unlink()

    response = api_client.get("/variants", {"limit": 2}, HTTP_IF_NONE_MATCH=etag)
    assert response.status_code == 304


def test_the_etag_serves_a_stale_304_after_the_file_changes(api_client, vcf_path):
    """Known consequence of following the brief literally.

    The ETag is derived from request parameters only, so it cannot notice that the
    VCF changed. The client is told "nothing has changed" and keeps a stale page.
    """
    etag = api_client.get("/variants", {"limit": 2})["ETag"]
    with vcf_path.open("a") as handle:
        handle.write(NEW_ROW)

    response = api_client.get("/variants", {"limit": 2}, HTTP_IF_NONE_MATCH=etag)
    assert response.status_code == 304


def test_including_the_file_mtime_defeats_the_stale_304(api_client, vcf_path, settings):
    """With ETAG_INCLUDE_FILE_MTIME on, a write changes the fingerprint."""
    settings.ETAG_INCLUDE_FILE_MTIME = True

    etag = api_client.get("/variants", {"limit": 2})["ETag"]
    with vcf_path.open("a") as handle:
        handle.write(NEW_ROW)
    os.utime(vcf_path, ns=(0, os.stat(vcf_path).st_mtime_ns + 1_000_000))

    response = api_client.get("/variants", {"limit": 2}, HTTP_IF_NONE_MATCH=etag)
    assert response.status_code == 200
