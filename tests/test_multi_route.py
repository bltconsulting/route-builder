"""Deterministic multi-route grouping and export without network calls."""

import csv
from pathlib import Path
from unittest.mock import patch

import pytest

from route_builder.matrix import DrivingMatrix
from route_builder.multi_route import balanced_geo_groups, build_multi_route_csv
from route_builder.route import Stop


def test_balanced_groups_keep_nearby_stops_together() -> None:
    stops = [Stop(str(i), f"{i} Example St", 42 + (i % 5) * 0.001,
                  -83 if i < 5 else -82.5) for i in range(10)]
    groups = balanced_geo_groups(stops, 2)
    assert sorted(map(len, groups)) == [5, 5]
    assert {frozenset(group) for group in groups} == {
        frozenset(range(5)), frozenset(range(5, 10)),
    }
    assert sorted(index for group in groups for index in group) == list(range(10))


def test_multi_route_csv_numbers_stops_and_closes_each_loop(tmp_path: Path) -> None:
    stops = [Stop(str(i), f"{i} Example St", 42, -83 + i * 0.01) for i in range(6)]
    comparison = tmp_path / "comparison.csv"
    with comparison.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["id", "census_matched_address"])
        writer.writeheader()
        writer.writerows({"id": stop.id, "census_matched_address": stop.source_address.upper()}
                         for stop in stops)

    def fake_matrix(group: list[Stop]) -> DrivingMatrix:
        size = len(group)
        costs = [[0 if i == j else 60 for j in range(size)] for i in range(size)]
        return DrivingMatrix(costs, costs, [0] * size)

    with patch("route_builder.multi_route.build_stops_from_census", return_value=stops), \
         patch("route_builder.multi_route.OsrmMatrixAdapter") as adapter, \
         patch("route_builder.multi_route.solve_closed_loop", side_effect=lambda matrix: list(range(len(matrix.durations)))):
        adapter.return_value.table.side_effect = fake_matrix
        target = build_multi_route_csv(tmp_path / "input.csv", comparison, 2, tmp_path / "out",
                                       "https://example.test")
    with target.open(newline="", encoding="utf-8-sig") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 6
    assert sorted(row["id"] for row in rows) == [str(i) for i in range(6)]
    for route_number in ("1", "2"):
        route = [row for row in rows if row["route_number"] == route_number]
        assert [row["stop_number"] for row in route] == ["1", "2", "3"]
        assert route[-1]["next_id"] == route[0]["id"]
        assert all(row["matched_address"] == row["source_address"].upper() for row in route)


def test_route_count_requires_two_stops_per_route() -> None:
    stops = [Stop(str(i), f"{i} Example St", 42, -83) for i in range(5)]
    with pytest.raises(ValueError, match="at least two stops"):
        balanced_geo_groups(stops, 3)
