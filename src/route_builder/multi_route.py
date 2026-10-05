"""Balanced geographic grouping followed by a closed driving loop per group."""

import csv
import logging
from math import cos, radians
from pathlib import Path

from .generate import build_stops_from_census
from .matrix import OsrmMatrixAdapter
from .optimize import solve_closed_loop
from .route import Stop

LOG = logging.getLogger(__name__)
FIELDS = (
    "route_number", "stop_number", "id", "source_address", "matched_address",
    "latitude", "longitude", "next_id", "leg_distance_m", "leg_duration_s", "road_snap_m",
)


def balanced_geo_groups(stops: list[Stop], route_count: int) -> list[list[int]]:
    """Assign every stop to a compact group with counts differing by at most one."""
    count = len(stops)
    if route_count < 1 or route_count > count // 2:
        raise ValueError("Route count must be positive and allow at least two stops per route")
    scale = cos(radians(sum(stop.latitude for stop in stops) / count))
    points = [(stop.longitude * scale, stop.latitude) for stop in stops]
    mean = (sum(x for x, _ in points) / count, sum(y for _, y in points) / count)

    def distance(a: tuple[float, float], b: tuple[float, float]) -> float:
        return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2

    seeds = [min(range(count), key=lambda i: (distance(points[i], mean), i))]
    while len(seeds) < route_count:
        seeds.append(max((i for i in range(count) if i not in seeds),
                         key=lambda i: (min(distance(points[i], points[j]) for j in seeds), -i)))
    centers = [points[i] for i in seeds]
    base, remainder = divmod(count, route_count)
    capacities = [base + (i < remainder) for i in range(route_count)]
    previous: tuple[int, ...] | None = None
    assignment: tuple[int, ...] = ()
    for _ in range(30):
        remaining = capacities.copy()
        choices = []
        for index, point in enumerate(points):
            ranked = sorted((distance(point, center), route) for route, center in enumerate(centers))
            regret = ranked[1][0] - ranked[0][0] if route_count > 1 else 0
            choices.append((-regret, ranked[0][0], index))
        labels = [-1] * count
        for _, _, index in sorted(choices):
            route = min((r for r in range(route_count) if remaining[r]),
                        key=lambda r: (distance(points[index], centers[r]), r))
            labels[index] = route
            remaining[route] -= 1
        assignment = tuple(labels)
        if assignment == previous:
            break
        previous = assignment
        for route in range(route_count):
            members = [points[i] for i, label in enumerate(assignment) if label == route]
            centers[route] = (sum(x for x, _ in members) / len(members),
                              sum(y for _, y in members) / len(members))
    return [[i for i, label in enumerate(assignment) if label == route] for route in range(route_count)]


def build_multi_route_csv(input_csv: str | Path, comparison_csv: str | Path,
                          route_count: int, output_dir: str | Path, matrix_endpoint: str) -> Path:
    stops = build_stops_from_census(input_csv, comparison_csv)
    groups = balanced_geo_groups(stops, route_count)
    with Path(comparison_csv).open(newline="", encoding="utf-8") as stream:
        matched = {row["id"]: row["census_matched_address"] for row in csv.DictReader(stream)}
    output = Path(output_dir)
    target = output / "routes.csv"
    if target.exists():
        raise ValueError(f"{target} already exists; choose a new output folder to preserve it")
    rows = []
    for route_number, indices in enumerate(groups, 1):
        group = [stops[i] for i in indices]
        matrix = OsrmMatrixAdapter(matrix_endpoint, output / f"route_{route_number:02d}_matrix_cache.json").table(group)
        if any(distance > 100 for distance in matrix.snap_distances):
            bad = [group[i].id for i, distance in enumerate(matrix.snap_distances) if distance > 100]
            raise ValueError(f"Route {route_number}: coordinates snapped too far from a road: {', '.join(bad)}")
        order = solve_closed_loop(matrix)
        for position, local_index in enumerate(order):
            next_index = order[(position + 1) % len(order)]
            stop = group[local_index]
            rows.append({
                "route_number": route_number, "stop_number": position + 1,
                "id": stop.id, "source_address": stop.source_address,
                "matched_address": matched[stop.id], "latitude": stop.latitude,
                "longitude": stop.longitude, "next_id": group[next_index].id,
                "leg_distance_m": round(matrix.distances[local_index][next_index]),
                "leg_duration_s": round(matrix.durations[local_index][next_index]),
                "road_snap_m": round(matrix.snap_distances[local_index], 1),
            })
        LOG.info("Route %d: %d stops, %.1f minutes closed-loop driving",
                 route_number, len(group),
                 sum(matrix.durations[order[i]][order[(i + 1) % len(order)]]
                     for i in range(len(order))) / 60)
    output.mkdir(parents=True, exist_ok=True)
    with target.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    LOG.warning("Review route groups and all destination pins before sharing; Census coordinates are estimated")
    return target
