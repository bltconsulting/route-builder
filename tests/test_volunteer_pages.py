"""Planned-route navigation widgets stay ordered and self-contained."""

import csv
import re
from pathlib import Path

import pytest

from route_builder.volunteer_pages import write_volunteer_pages


def test_one_widget_per_closed_route_with_distinct_saved_progress(tmp_path: Path) -> None:
    routes = tmp_path / "routes.csv"
    with routes.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=[
            "route_number", "stop_number", "id", "source_address",
            "latitude", "longitude", "review_note", "matched_address", "next_id",
        ])
        writer.writeheader()
        writer.writerows([
            dict(route_number=1, stop_number=1, id="a", source_address="1 First St",
                 latitude=42.0, longitude=-83.0, review_note="Street differs from Census match",
                 matched_address="1 FIRST AVE", next_id="b"),
            dict(route_number=1, stop_number=2, id="b", source_address="2 Second St",
                 latitude=42.1, longitude=-83.1, review_note="", next_id="a"),
            dict(route_number=2, stop_number=1, id="c", source_address="3 Third St",
                 latitude=42.2, longitude=-83.2, review_note="", next_id="d"),
            dict(route_number=2, stop_number=2, id="d", source_address="4 Fourth St",
                 latitude=42.3, longitude=-83.3, review_note="", next_id="c"),
        ])
    pages = write_volunteer_pages(routes, tmp_path / "pages")
    assert [page.name for page in pages] == ["Route-01-REVIEW.html", "Route-02-REVIEW.html"]
    first, second = (page.read_text() for page in pages)
    assert first.index('"id": "a"') < first.index('"id": "b"')
    assert '"id": "c"' not in first
    assert "<h1>Route 1</h1>" in first and "<h1>Route 2</h1>" in second
    assert "START MY ROUTE" in first and "REVISIT SKIPPED STOPS" in first
    assert '"possible_actual_address": "1 FIRST AVE"' in first
    assert "Possible actual address:" in first
    assert "<script src=" not in first and "<link rel=" not in first
    assert re.search(r"route-builder-[a-f0-9]{16}", first).group() != re.search(
        r"route-builder-[a-f0-9]{16}", second).group()
    with pytest.raises(ValueError, match="already exists"):
        write_volunteer_pages(routes, tmp_path / "pages")


def test_incomplete_loop_is_rejected_before_writing(tmp_path: Path) -> None:
    routes = tmp_path / "routes.csv"
    routes.write_text("route_number,stop_number,id,source_address,latitude,longitude,review_note,next_id\n"
                      "1,1,a,1 First St,42,-83,,b\n1,2,b,2 Second St,42.1,-83.1,,wrong\n")
    with pytest.raises(ValueError, match="does not close"):
        write_volunteer_pages(routes, tmp_path / "pages")
    assert not (tmp_path / "pages").exists()
