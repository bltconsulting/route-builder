"""Balanced geographic grouping followed by a closed driving loop per group."""

import csv
import logging
import re
from collections import Counter, defaultdict
from math import cos, radians
from pathlib import Path

from .generate import build_stops_from_census
from .geocode import street_key
from .matrix import OsrmMatrixAdapter
from .optimize import solve_closed_loop
from .route import Stop

LOG = logging.getLogger(__name__)
FIELDS = (
    "route_number", "stop_number", "id", "source_address", "matched_address",
    "latitude", "longitude", "review_note", "next_id", "leg_distance_m", "leg_duration_s", "road_snap_m",
)


def match_notes(stops: list[Stop], matched: dict[str, str]) -> dict[str, str]:
    """Flag address differences and coincident points without removing stops."""
    source_counts = Counter(stop.source_address.casefold().strip() for stop in stops)
    coordinate_ids: dict[tuple[float, float], list[str]] = defaultdict(list)
    for stop in stops:
        coordinate_ids[(stop.latitude, stop.longitude)].append(stop.id)
    notes = {}
    for stop in stops:
        source_parts = [part.strip() for part in stop.source_address.split(",")]
        match_parts = [part.strip() for part in matched[stop.id].split(",")]
        source_line = re.sub(r"\s+(?:apt|unit|#)\s*\S+$", "", source_parts[0], flags=re.I)
        source_street = re.sub(r"^\d+\s+", "", source_line)
        matched_street = re.sub(r"^\d+\s+", "", match_parts[0])
        warnings = []
        source_number = re.match(r"^\d+", source_line)
        matched_number = re.match(r"^\d+", match_parts[0])
        if not source_number or not matched_number or source_number.group() != matched_number.group():
            warnings.append("House number differs from Census match")
        if street_key(source_street) != street_key(matched_street):
            warnings.append("Street differs from Census match")
        if len(source_parts) > 1 and len(match_parts) > 1:
            source_city = re.sub(r"\s+MI$", "", source_parts[1], flags=re.I)
            if source_city.casefold() != match_parts[1].casefold():
                warnings.append("City differs from Census match")
        if source_counts[stop.source_address.casefold().strip()] > 1:
            warnings.append("Duplicate source address")
        other_ids = [stop_id for stop_id in coordinate_ids[(stop.latitude, stop.longitude)]
                     if stop_id != stop.id]
        if other_ids and source_counts[stop.source_address.casefold().strip()] == 1:
            warnings.append("Estimated coordinate shared with ID " + ", ".join(other_ids))
        notes[stop.id] = "; ".join(warnings)
    return notes


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
    review_notes = match_notes(stops, matched)
    output = Path(output_dir)
    target = output / "routes.csv"
    summary_target = output / "route_summary.csv"
    for existing in (target, summary_target):
        if existing.exists():
            raise ValueError(f"{existing} already exists; choose a new output folder to preserve it")
    rows = []
    summary = []
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
                "longitude": stop.longitude, "review_note": review_notes[stop.id],
                "next_id": group[next_index].id,
                "leg_distance_m": round(matrix.distances[local_index][next_index]),
                "leg_duration_s": round(matrix.durations[local_index][next_index]),
                "road_snap_m": round(matrix.snap_distances[local_index], 1),
            })
        LOG.info("Route %d: %d stops, %.1f minutes closed-loop driving",
                 route_number, len(group),
                 sum(matrix.durations[order[i]][order[(i + 1) % len(order)]]
                     for i in range(len(order))) / 60)
        route_rows = rows[-len(group):]
        summary.append({
            "route_number": route_number, "stop_count": len(group),
            "loop_distance_km": round(sum(int(row["leg_distance_m"]) for row in route_rows) / 1000, 1),
            "loop_driving_minutes": round(sum(int(row["leg_duration_s"]) for row in route_rows) / 60, 1),
            "review_count": sum(bool(row["review_note"]) for row in route_rows),
        })
    output.mkdir(parents=True, exist_ok=True)
    with target.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    with summary_target.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(summary[0]))
        writer.writeheader()
        writer.writerows(summary)
    minutes = [row["loop_driving_minutes"] for row in summary]
    if max(minutes) > 2 * min(minutes):
        LOG.warning("Driving workloads vary substantially (%.1f to %.1f minutes); review route balance",
                    min(minutes), max(minutes))
    LOG.warning("Review route groups and all destination pins before sharing; Census coordinates are estimated")
    if any(review_notes.values()):
        LOG.warning("%d stops have address or duplicate-coordinate review notes in routes.csv",
                    sum(bool(note) for note in review_notes.values()))
    return target
