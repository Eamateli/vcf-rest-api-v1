"""Append-only record of every change made to the VCF.

One JSON object per line (JSONL): appending costs a single write, the file streams
line by line at any size, and a crash mid-write costs one record rather than
corrupting the whole document.
"""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def record(
    path: Path,
    *,
    method: str,
    variant_id: str | None,
    before: list[str] | None,
    after: dict[str, Any] | None,
    authenticated: bool = True,
) -> None:
    """Append one JSON object describing a mutation. Never rewrites earlier lines.

    `before` holds the raw source lines that were replaced or removed, verbatim and
    complete, so prior state stays reconstructible. A single shared secret carries no
    identity, so `authenticated` records only that a valid secret was presented.
    """
    entry = {
        "ts": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "method": method,
        "id": variant_id,
        "before": before,
        "after": after,
        "authenticated": authenticated,
    }
    with path.open("a") as handle:
        handle.write(json.dumps(entry, separators=(",", ":")) + "\n")
