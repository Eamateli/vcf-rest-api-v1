"""Every mutation is recorded; nothing else is."""

import json

VALID = {"CHROM": "chr1", "POS": 1000, "ID": "rs123", "REF": "G", "ALT": "A"}


def entries(audit_path):
    if not audit_path.exists():
        return []
    return [json.loads(line) for line in audit_path.read_text().splitlines()]


def test_a_post_is_recorded_with_no_previous_state(writer_client, audit_path):
    writer_client.post("/variants", VALID, format="json")
    entry = entries(audit_path)[0]
    assert entry["method"] == "POST"
    assert entry["id"] == "rs123"
    assert entry["before"] is None
    assert entry["after"] == VALID


def test_a_put_records_every_row_it_replaced_verbatim(writer_client, audit_path):
    writer_client.put("/variants?id=rs4000001", {**VALID, "ID": "rs4000001"}, format="json")
    entry = entries(audit_path)[0]
    assert entry["method"] == "PUT"
    assert len(entry["before"]) == 2
    assert all(row.count("\t") == 9 for row in entry["before"])
    assert "rs4000001" in entry["before"][0]


def test_a_delete_records_the_removed_rows_and_no_after_state(writer_client, audit_path):
    writer_client.delete("/variants?id=rs4000001")
    entry = entries(audit_path)[0]
    assert entry["method"] == "DELETE"
    assert len(entry["before"]) == 2
    assert entry["after"] is None


def test_reads_are_not_recorded(writer_client, audit_path):
    writer_client.get("/variants")
    writer_client.get("/variants?id=rs4000001")
    assert entries(audit_path) == []


def test_a_rejected_write_is_not_recorded(writer_client, audit_path):
    writer_client.post("/variants", {**VALID, "CHROM": "chr99"}, format="json")
    assert entries(audit_path) == []


def test_a_forbidden_write_is_not_recorded(api_client, audit_path):
    api_client.post("/variants", VALID, format="json")
    assert entries(audit_path) == []


def test_entries_accumulate_one_line_per_mutation(writer_client, audit_path):
    writer_client.post("/variants", VALID, format="json")
    writer_client.post("/variants", {**VALID, "ID": "rs124"}, format="json")
    writer_client.delete("/variants?id=rs123")
    assert [entry["method"] for entry in entries(audit_path)] == ["POST", "POST", "DELETE"]


def test_every_entry_is_a_complete_json_object_on_its_own_line(writer_client, audit_path):
    """JSONL: each line parses independently, so a truncated tail costs one record."""
    writer_client.post("/variants", VALID, format="json")
    writer_client.delete("/variants?id=rs123")
    for line in audit_path.read_text().splitlines():
        assert set(json.loads(line)) == {"ts", "method", "id", "before", "after", "authenticated"}
