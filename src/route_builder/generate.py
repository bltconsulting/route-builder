"""Produce one portable volunteer HTML file from a validated fixture route."""

import hashlib
import json
import csv
import html as html_module
from math import isfinite
from pathlib import Path

from .input import read_addresses
from .route import Stop


def read_fixture(path: str | Path) -> dict[str, tuple[float, float]]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Fixture must be an object keyed by stop id")
    points = {}
    for stop_id, pair in raw.items():
        if not isinstance(pair, list) or len(pair) != 2:
            raise ValueError(f"Fixture {stop_id}: expected [latitude, longitude]")
        lat, lon = pair
        if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)) or not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError(f"Fixture {stop_id}: invalid coordinates")
        points[stop_id] = (float(lat), float(lon))
    return points


def build_stops(csv_path: str | Path, fixture_path: str | Path) -> list[Stop]:
    addresses = read_addresses(csv_path)
    fixture = read_fixture(fixture_path)
    ids = {address.id for address in addresses}
    missing = ids - fixture.keys()
    extra = fixture.keys() - ids
    if missing or extra:
        raise ValueError(f"Fixture IDs differ from CSV: missing={sorted(missing)}, extra={sorted(extra)}")
    return [Stop(address.id, address.source_address, *fixture[address.id]) for address in addresses]


def build_stops_from_census(csv_path: str | Path, comparison_path: str | Path) -> list[Stop]:
    addresses = read_addresses(csv_path)
    with Path(comparison_path).open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    by_id = {row["id"]: row for row in rows}
    if len(by_id) != len(rows) or set(by_id) != {address.id for address in addresses}:
        raise ValueError("Census report IDs do not match the CSV")
    stops = []
    for address in addresses:
        row = by_id[address.id]
        if row["source_address"] != address.source_address or row["census_result"] != "MATCH":
            raise ValueError(f"Stop {address.id}: source address changed or Census match is not unique")
        try:
            lat, lon = float(row["census_latitude"]), float(row["census_longitude"])
        except ValueError as exc:
            raise ValueError(f"Stop {address.id}: missing Census coordinates") from exc
        if not (isfinite(lat) and isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError(f"Stop {address.id}: invalid Census coordinates")
        stops.append(Stop(address.id, address.source_address, lat, lon))
    return stops


def generate_html(stops: list[Stop], template_dir: str | Path, notice: str = "DEMO ONLY: these coordinates are placeholders. Do not use this route for deliveries.") -> str:
    if not stops:
        raise ValueError("Cannot generate an empty route")
    root = Path(template_dir)
    payload = json.dumps([{"id": s.id, "address": s.source_address, "lat": s.latitude, "lon": s.longitude} for s in stops], ensure_ascii=False)
    payload = payload.replace("<", "\\u003c").replace("&", "\\u0026")
    route_id = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    html = (root / "volunteer_route.html").read_text(encoding="utf-8")
    logic = (root / "route_state.js").read_text(encoding="utf-8")
    return html.replace("__ROUTE_DATA__", payload).replace("__ROUTE_ID__", route_id).replace("__ROUTE_LOGIC__", logic).replace("__ROUTE_NOTICE__", html_module.escape(notice))
