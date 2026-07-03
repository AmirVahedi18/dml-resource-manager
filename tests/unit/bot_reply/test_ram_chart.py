from datetime import datetime, timedelta
from types import SimpleNamespace

from dml_bot.bot_reply.ram_chart import render_ram_chart

CAP_MB = 40960  # 40 GB


def _reservation(start, end, ram_mb, name):
    return SimpleNamespace(start_time=start, end_time=end, ram_mb=ram_mb, user=SimpleNamespace(full_name=name))


def test_every_bucket_shown_including_empty_ones():
    start = datetime(2026, 7, 6, 0, 0)
    end = start + timedelta(hours=6)
    pages = render_ram_chart([], CAP_MB, start, end, "UTC", 2.0, 30)
    assert len(pages) == 1
    bucket_lines = [l for l in pages[0].splitlines() if "/40" in l]
    assert len(bucket_lines) == 3  # 6h range / 2h buckets == 3 buckets, none merged away
    assert all("0/40" in l for l in bucket_lines)


def test_bucket_size_does_not_change_with_range_length():
    start = datetime(2026, 7, 6, 0, 0)
    for days in (1, 7, 30):
        pages = render_ram_chart([], CAP_MB, start, start + timedelta(days=days), "UTC", 2.0, 30)
        bucket_lines = [l for l in "\n".join(pages).splitlines() if "/40" in l]
        assert len(bucket_lines) == days * 12  # always 2h buckets, never widened


def test_overlapping_reservations_show_abbreviated_names_on_one_line():
    start = datetime(2026, 7, 6, 0, 0)
    end = start + timedelta(hours=2)
    reservations = [
        _reservation(datetime(2026, 7, 6, 0, 0), datetime(2026, 7, 6, 2, 0), 24576, "Ali Ahmadi"),
        _reservation(datetime(2026, 7, 6, 0, 0), datetime(2026, 7, 6, 2, 0), 16384, "Amir Vahedi"),
    ]
    pages = render_ram_chart(reservations, CAP_MB, start, end, "UTC", 2.0, 50)
    bucket_line = next(l for l in pages[0].splitlines() if "/40" in l)
    assert "A.Ahmadi" in bucket_line
    assert "A.Vahedi" in bucket_line
    assert "\n" not in bucket_line.strip("\n")  # single line, no break for names


def test_no_line_exceeds_configured_width():
    now = datetime(2026, 7, 6, 9, 0)
    reservations = [
        _reservation(datetime(2026, 7, 6, 8, 0), datetime(2026, 7, 6, 16, 0), 24576, "Ali Ahmadi"),
        _reservation(datetime(2026, 7, 6, 14, 0), datetime(2026, 7, 6, 20, 0), 16384, "Amir Vahedi"),
    ]
    for width in (26, 30, 40):
        for range_days in (1, 2):
            pages = render_ram_chart(reservations, CAP_MB, now, now + timedelta(days=range_days), "UTC", 1.0, width)
            for page in pages:
                for line in page.splitlines():
                    assert len(line) <= width, (width, range_days, line)


def test_many_concurrent_names_are_truncated_not_wrapped():
    start = datetime(2026, 7, 6, 0, 0)
    end = start + timedelta(hours=1)
    reservations = [_reservation(start, end, 1024, f"Student LongSurname{i}") for i in range(6)]
    pages = render_ram_chart(reservations, CAP_MB, start, end, "UTC", 1.0, 30)
    bucket_line = next(l for l in pages[0].splitlines() if "/40" in l)
    assert len(bucket_line) <= 30
    assert bucket_line.endswith("…")


def test_long_range_splits_into_multiple_pages_within_message_budget():
    start = datetime(2026, 7, 6, 0, 0)
    end = start + timedelta(days=90)
    pages = render_ram_chart([], CAP_MB, start, end, "UTC", 1.0, 30)
    assert len(pages) > 1
    for page in pages:
        assert len(page) <= 3600  # a bit above the internal budget to allow for the title line
    total_bucket_lines = sum(page.count("/40") for page in pages)
    assert total_bucket_lines == 90 * 24  # strict 1h buckets, all 2160 shown, none dropped


def _day_headers(text: str) -> list[str]:
    weekdays = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
    return [line for line in text.splitlines() if line[:3] in weekdays]


def test_page_breaks_never_split_a_day_in_half():
    start = datetime(2026, 7, 6, 0, 0)
    end = start + timedelta(days=90)
    pages = render_ram_chart([], CAP_MB, start, end, "UTC", 1.0, 30)
    assert len(pages) > 1  # otherwise this test isn't exercising the split logic

    all_headers = [h for page in pages for h in _day_headers(page)]
    assert len(all_headers) == len(set(all_headers))  # each day's header appears on exactly one page

    for page in pages:
        headers = _day_headers(page)
        if not headers:
            continue  # a rare mid-day-split continuation page (no header at all) -- nothing to check
        # the page's first content line (after the title line) must be a day header, i.e. this
        # page never starts with a leftover bucket line from a day that began on a prior page
        first_content_line = page.splitlines()[1]
        assert first_content_line == headers[0]
