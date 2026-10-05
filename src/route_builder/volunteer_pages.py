"""Generate one self-contained navigation widget per planned route."""

import math
from pathlib import Path

from .generate import generate_html
from .printable_maps import read_routes
from .route import Stop


def write_volunteer_pages(routes_csv: str | Path, output_dir: str | Path) -> list[Path]:
    groups = read_routes(routes_csv)
    folder = Path(output_dir)
    ids = [row["id"] for rows in groups.values() for row in rows]
    if len(ids) != len(set(ids)) or any(not stop_id for stop_id in ids):
        raise ValueError("Planned routes must have unique, nonblank source IDs")
    template_dir = Path(__file__).resolve().parents[2] / "templates"
    pages = []
    for number, rows in groups.items():
        expected_next = [row["id"] for row in rows[1:]] + [rows[0]["id"]]
        if [row.get("next_id") for row in rows] != expected_next:
            raise ValueError(f"Route {number} does not close in stop-number order")
        stops = []
        for row in rows:
            latitude, longitude = float(row["latitude"]), float(row["longitude"])
            if not (math.isfinite(latitude) and math.isfinite(longitude)
                    and -90 <= latitude <= 90 and -180 <= longitude <= 180):
                raise ValueError(f"Stop {row['id']} has invalid coordinates")
            if not row["source_address"].strip():
                raise ValueError(f"Stop {row['id']} has no address")
            stops.append(Stop(row["id"], row["source_address"], latitude, longitude))
        target = folder / f"Route-{number:02d}-REVIEW.html"
        notice = (f"Route {number} review copy. Destination pins use estimated Census coordinates. "
                  "Confirm pins and route assignments before sharing.")
        pages.append((target, generate_html(stops, template_dir, notice, title=f"Route {number}")))
    for target, _ in pages:
        if target.exists():
            raise ValueError(f"{target} already exists; choose a new output folder")
    folder.mkdir(parents=True, exist_ok=True)
    for target, page in pages:
        target.write_text(page, encoding="utf-8")
    return [target for target, _ in pages]
