"""Shared fixtures. Every test builds its own VCF; none touch data/sample.vcf."""

from pathlib import Path

import pytest
from rest_framework.test import APIClient

META = "##fileformat=VCFv4.2"
HEADER = "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tSAMPLE01 single 20180302"
ROWS = [
    "chr1\t12783\trs62635284\tG\tA\t99.03\tFAIL\tAC=2\tGT:DP\t1/1:4",
    "chr1\t13656\trs1263393206\tCAG\tC\t196.73\tPASS\tAC=1\tGT:DP\t0/1:12",
    "chr1\t62186\t.\tG\tT\t62.74\tFAIL\tAC=2\tGT:DP\t1/1:2",
    "chr2\t41522\trs4000001\tA\tG\t410.55\tPASS\tAC=1\tGT:DP\t0/1:31",
    "chr3\t88234\trs4000001\tG\tA\t155.09\tPASS\tAC=1\tGT:DP\t0/1:14",
    "chrUn_gl000225\t1200\t.\tA\tT\t66.33\tFAIL\tAC=1\tGT:DP\t0/1:8",
]


@pytest.fixture
def vcf_path(tmp_path: Path) -> Path:
    """A small VCF in a temporary directory, unique to each test."""
    path = tmp_path / "test.vcf"
    path.write_text("\n".join([META, HEADER, *ROWS]) + "\n")
    return path

TEST_SECRET = "test-secret-value"


@pytest.fixture
def audit_path(tmp_path: Path) -> Path:
    """Where this test's audit entries land."""
    return tmp_path / "audit.jsonl"


@pytest.fixture
def api_client(settings, vcf_path: Path, audit_path: Path) -> APIClient:
    """A client whose API is pointed at this test's own throwaway VCF."""
    settings.VCF_PATH = vcf_path
    settings.AUDIT_LOG_PATH = audit_path
    settings.VCF_API_SECRET = TEST_SECRET
    settings.ALLOWED_HOSTS = ["testserver"]
    return APIClient()


@pytest.fixture
def writer_client(api_client: APIClient) -> APIClient:
    """The same client, carrying a valid write secret."""
    api_client.credentials(HTTP_AUTHORIZATION=TEST_SECRET)
    return api_client