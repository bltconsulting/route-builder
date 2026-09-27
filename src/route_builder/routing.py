"""Write the canonical road-optimized cycle and its volunteer test page."""

import csv
import logging
from pathlib import Path

from .generate import build_stops_from_census, generate_html
from .matrix import OsrmMatrixAdapter
from .optimize import solve_closed_loop

LOG = logging.getLogger(__name__)


def build_optimized_route(csv_path: str | Path, comparison_path: str | Path, output_dir: str | Path, matrix_endpoint: str) -> list[str]:
    stops = build_stops_from_census(csv_path, comparison_path)
    with Path(comparison_path).open(newline="", encoding="utf-8") as stream:
        matched_addresses = {row["id"]: row["census_matched_address"] for row in csv.DictReader(stream)}
    output = Path(output_dir)
    matrix = OsrmMatrixAdapter(matrix_endpoint, output / "driving_matrix_cache.json").table(stops)
    large_snaps = [(stops[i].id, distance) for i, distance in enumerate(matrix.snap_distances) if distance > 100]
    if large_snaps:
        detail = ", ".join(f"{stop_id} ({distance:.0f} m)" for stop_id, distance in large_snaps)
        raise ValueError(f"Coordinates snapped too far from a drivable road: {detail}")
    order = solve_closed_loop(matrix)
    output.mkdir(parents=True, exist_ok=True)
    rows = []
    for sequence, index in enumerate(order, 1):
        next_index = order[sequence % len(order)]
        stop = stops[index]
        rows.append({"sequence": sequence, "id": stop.id, "source_address": stop.source_address, "matched_address": matched_addresses[stop.id], "latitude": stop.latitude, "longitude": stop.longitude, "next_id": stops[next_index].id, "leg_distance_m": round(matrix.distances[index][next_index]), "leg_duration_s": round(matrix.durations[index][next_index]), "road_snap_m": round(matrix.snap_distances[index], 1)})
    with (output / "route.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    ordered_stops = [stops[index] for index in order]
    notice = "TEST ROUTE: road order is optimized, but Census coordinates are estimated. Verify each destination before driving or sharing."
    template_dir = Path(__file__).resolve().parents[2] / "templates"
    (output / "route.html").write_text(generate_html(ordered_stops, template_dir, notice), encoding="utf-8")
    total_seconds = sum(matrix.durations[order[i]][order[(i + 1) % len(order)]] for i in range(len(order)))
    total_meters = sum(matrix.distances[order[i]][order[(i + 1) % len(order)]] for i in range(len(order)))
    LOG.info("Closed loop: %d stops, %.1f km, %.1f minutes of driving; returns from %s to %s", len(order), total_meters / 1000, total_seconds / 60, stops[order[-1]].id, stops[order[0]].id)
    return [stops[index].id for index in order]
