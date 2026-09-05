"""Offset/limit pagination over a stream of items."""

from collections.abc import Iterable
from dataclasses import dataclass
from itertools import islice

DEFAULT_LIMIT = 20
MAX_LIMIT = 1000


@dataclass(frozen=True)
class Page[T]:
    """One window into a stream, plus what a caller needs to navigate."""

    items: list[T]
    offset: int
    limit: int
    has_next: bool

    @property
    def next_offset(self) -> int | None:
        return self.offset + self.limit if self.has_next else None

    @property
    def previous_offset(self) -> int | None:
        if self.offset <= 0:
            return None
        return max(self.offset - self.limit, 0)


def paginate[T](items: Iterable[T], offset: int = 0, limit: int = DEFAULT_LIMIT) -> Page[T]:
    """Return the window starting at `offset`, without materialising what it skips."""
    if offset < 0:
        raise ValueError(f"offset must be zero or greater, got {offset}")
    if limit < 1:
        raise ValueError(f"limit must be at least 1, got {limit}")

    limit = min(limit, MAX_LIMIT)

    # Take one extra item to learn whether a next page exists, without a second pass.
    window = list(islice(items, offset, offset + limit + 1))

    return Page(
        items=window[:limit],
        offset=offset,
        limit=limit,
        has_next=len(window) > limit,
    )
