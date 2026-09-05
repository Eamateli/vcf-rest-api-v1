"""Safe writes: locking, atomic replacement, and the trailing-newline repair."""

import threading

from vcf_core.repository import VcfRepository
from vcf_core.storage import append_line, file_lock, replace_lines


def test_append_adds_the_line_and_a_trailing_newline(tmp_path):
    path = tmp_path / "f.txt"
    path.write_text("a\n")
    append_line(path, "b")
    assert path.read_text() == "a\nb\n"


def test_append_repairs_a_missing_trailing_newline(tmp_path):
    """Without the repair the new row would be glued onto the previous one."""
    path = tmp_path / "f.txt"
    path.write_text("a\nb")
    append_line(path, "c")
    assert path.read_text() == "a\nb\nc\n"


def test_append_works_on_an_empty_file(tmp_path):
    path = tmp_path / "f.txt"
    path.write_text("")
    append_line(path, "a")
    assert path.read_text() == "a\n"


def test_replace_lines_swaps_the_whole_file(tmp_path):
    path = tmp_path / "f.txt"
    path.write_text("old1\nold2\n")
    replace_lines(path, ["new1", "new2", "new3"])
    assert path.read_text() == "new1\nnew2\nnew3\n"


def test_a_failure_mid_rewrite_leaves_the_original_intact(tmp_path):
    """os.replace only runs once the temp file is complete."""
    path = tmp_path / "f.txt"
    path.write_text("original\n")

    def exploding_lines():
        yield "partial"
        raise RuntimeError("boom")

    try:
        replace_lines(path, exploding_lines())
    except RuntimeError:
        pass

    assert path.read_text() == "original\n"
    assert not list(tmp_path.glob("*.tmp"))


def test_the_lock_is_held_exclusively(tmp_path):
    """A second holder must wait, so the two critical sections cannot overlap."""
    path = tmp_path / "f.txt"
    path.write_text("")
    order = []

    def worker(name):
        with file_lock(path):
            order.append(f"{name}-in")
            threading.Event().wait(0.05)
            order.append(f"{name}-out")

    first = threading.Thread(target=worker, args=("a",))
    second = threading.Thread(target=worker, args=("b",))
    first.start()
    second.start()
    first.join()
    second.join()

    assert order[0].endswith("-in")
    assert order[1] == order[0].replace("-in", "-out")


def test_concurrent_appends_lose_no_lines(vcf_path):
    """Eight threads, ten appends each. All eighty rows must survive, intact."""
    def worker(worker_id):
        repository = VcfRepository(vcf_path)
        for index in range(10):
            repository.append("chr1", 1000 + index, f"rs{worker_id}{index:03d}", "G", "A")

    threads = [threading.Thread(target=worker, args=(n,)) for n in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    rows = [line for line in vcf_path.read_text().splitlines() if not line.startswith("#")]
    # Appended IDs are rs<worker><index>, six characters; fixture IDs are longer.
    written = [row for row in rows if len(row.split("\t")[2]) == 6]

    assert len(written) == 80, "some appends were lost"
    assert len(set(written)) == 80, "two appends interleaved into one row"
    assert {row.count("\t") for row in rows} == {9}, "a row was corrupted"
