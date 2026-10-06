"""PDF packets keep route order and address-review hints."""

import csv
from pathlib import Path

import pytest

from route_builder.route_pdfs import write_route_pdfs
from test_printable_maps import road_zip


def test_master_and_individual_pdfs_show_match_hints_without_ids(tmp_path: Path) -> None:
    fitz = pytest.importorskip("pymupdf")
    roads = tmp_path / "roads.zip"
    road_zip(roads)
    routes = tmp_path / "routes.csv"
    with routes.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=["route_number", "stop_number", "id", "source_address",
                                                     "matched_address", "latitude", "longitude", "review_note"])
        writer.writeheader()
        writer.writerows([
            dict(route_number=1, stop_number=1, id="sensitive-id", source_address="1 Example Rd",
                 matched_address="1 EXAMPLE ST", latitude=42.02, longitude=-83.08,
                 review_note="Street differs from Census match"),
            dict(route_number=2, stop_number=1, id="another-id", source_address="2 Example Rd",
                 matched_address="2 EXAMPLE RD", latitude=42.08, longitude=-83.02, review_note=""),
        ])
    files = write_route_pdfs(routes, roads, tmp_path / "packet")
    assert len(files) == 3
    with fitz.open(files[0]) as master:
        assert len(master) == 2
        first = master[0].get_text()
        assert "Possible actual address: 1 EXAMPLE ST" in first
        assert "sensitive-id" not in first
        assert "Route 1 overview" in first
    with fitz.open(files[1]) as route_one:
        assert len(route_one) == 1
        assert "1 Example Rd" in route_one[0].get_text()
    with pytest.raises(ValueError, match="already exists"):
        write_route_pdfs(routes, roads, tmp_path / "packet")
