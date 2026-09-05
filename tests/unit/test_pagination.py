"""Unit tests for vcf_core.pagination."""

import pytest

from vcf_core.pagination import DEFAULT_LIMIT, MAX_LIMIT, paginate


def test_the_first_page_starts_at_the_beginning():
    assert paginate(range(100), offset=0, limit=20).items == list(range(20))


def test_an_offset_skips_that_many_items():
    assert paginate(range(100), offset=40, limit=20).items == list(range(40, 60))


def test_an_empty_stream_gives_an_empty_page():
    page = paginate([], offset=0, limit=20)
    assert page.items == []
    assert page.has_next is False
    assert page.next_offset is None
    assert page.previous_offset is None


def test_an_offset_past_the_end_gives_an_empty_page():
    page = paginate(range(10), offset=500, limit=20)
    assert page.items == []
    assert page.has_next is False


def test_a_limit_larger_than_the_stream_returns_everything():
    page = paginate(range(10), offset=0, limit=20)
    assert page.items == list(range(10))
    assert page.has_next is False


def test_has_next_is_true_when_more_items_follow():
    page = paginate(range(100), offset=0, limit=20)
    assert page.has_next is True
    assert page.next_offset == 20


def test_has_next_is_false_on_an_exact_final_page():
    page = paginate(range(40), offset=20, limit=20)
    assert page.items == list(range(20, 40))
    assert page.has_next is False
    assert page.next_offset is None


def test_the_first_page_has_no_previous():
    assert paginate(range(100), offset=0, limit=20).previous_offset is None


def test_previous_offset_steps_back_one_page():
    assert paginate(range(100), offset=40, limit=20).previous_offset == 20


def test_previous_offset_never_goes_below_zero():
    assert paginate(range(100), offset=5, limit=20).previous_offset == 0


def test_the_default_limit_is_used_when_none_is_given():
    assert paginate(range(100)).limit == DEFAULT_LIMIT


def test_limit_is_capped_to_protect_memory():
    assert paginate(range(5), offset=0, limit=99_999_999).limit == MAX_LIMIT


@pytest.mark.parametrize("offset", [-1, -100])
def test_a_negative_offset_is_rejected(offset):
    with pytest.raises(ValueError):
        paginate(range(10), offset=offset)


@pytest.mark.parametrize("limit", [0, -1])
def test_a_limit_below_one_is_rejected(limit):
    with pytest.raises(ValueError):
        paginate(range(10), limit=limit)


def test_pagination_reads_only_one_item_beyond_the_page():
    """The first page must not consume the whole stream."""
    consumed = []

    def counting_stream():
        for value in range(1_000_000):
            consumed.append(value)
            yield value

    paginate(counting_stream(), offset=0, limit=20)

    assert len(consumed) == 21


def test_pagination_still_reads_everything_it_skips():
    """Offset pagination is O(n): skipped items are read, just never returned."""
    consumed = []

    def counting_stream():
        for value in range(1_000_000):
            consumed.append(value)
            yield value

    paginate(counting_stream(), offset=200, limit=20)

    assert len(consumed) == 221
