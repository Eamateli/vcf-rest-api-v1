"""Safe writes: one writer at a time, and never a half-written file."""

import fcntl
import os
import tempfile
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from pathlib import Path

LOCK_SUFFIX = ".lock"


@contextmanager
def file_lock(path: Path) -> Iterator[None]:
    """Hold an exclusive lock on a sidecar file for the duration of the block."""
    lock_path = path.with_name(path.name + LOCK_SUFFIX)
    with lock_path.open("w") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def _ends_with_newline(path: Path) -> bool:
    """Check the final byte without reading the file."""
    with path.open("rb") as handle:
        handle.seek(-1, os.SEEK_END)
        return handle.read(1) == b"\n"


def append_line(path: Path, line: str) -> None:
    """Append one row, repairing a missing trailing newline first."""
    if path.stat().st_size and not _ends_with_newline(path):
        with path.open("a") as handle:
            handle.write("\n")
    with path.open("a") as handle:
        handle.write(line.rstrip("\n") + "\n")


def replace_lines(path: Path, lines: Iterable[str]) -> None:
    """Rewrite the file atomically: build a temp file alongside it, then swap."""
    fd, temp_name = tempfile.mkstemp(dir=path.parent, prefix=path.name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as handle:
            for line in lines:
                handle.write(line.rstrip("\n") + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    except BaseException:
        Path(temp_name).unlink(missing_ok=True)
        raise
