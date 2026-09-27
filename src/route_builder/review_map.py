"""Offline organizer overview of geocoding candidates."""

import csv
import html
from collections import defaultdict
from math import isfinite
from pathlib import Path
from urllib.parse import urlencode


def read_validation(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise ValueError("Validation report has no stops")
    located = 0
    for row in rows:
        if not row.get("latitude") or not row.get("longitude"):
            if row.get("status") == "FAILED":
                continue
            raise ValueError(f"Stop {row.get('id', '?')} has no usable coordinates")
        try:
            lat, lon = float(row["latitude"]), float(row["longitude"])
        except (KeyError, ValueError) as exc:
            raise ValueError(f"Stop {row.get('id', '?')} has no usable coordinates") from exc
        if not (isfinite(lat) and isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError(f"Stop {row['id']} has invalid coordinates")
        located += 1
    if not located:
        raise ValueError("Validation report has no located stops")
    return rows


def generate_review_map(rows: list[dict[str, str]]) -> str:
    """Create a portable coordinate overview with links to street maps."""
    points = defaultdict(list)
    for row in rows:
        if not row.get("latitude") or not row.get("longitude"):
            continue
        points[(float(row["latitude"]), float(row["longitude"]))].append(row)
    lats = [point[0] for point in points]
    lons = [point[1] for point in points]
    min_lat, max_lat = min(lats), max(lats)
    min_lon, max_lon = min(lons), max(lons)
    lat_span = max(max_lat - min_lat, 0.01)
    lon_span = max(max_lon - min_lon, 0.01)
    markers = []
    for (lat, lon), group in points.items():
        x = 45 + 810 * (lon - min_lon) / lon_span
        y = 45 + 510 * (max_lat - lat) / lat_span
        ids = ", ".join(row["id"] for row in group)
        color = "#136b37" if all(row["status"] == "READY" for row in group) else "#b65000"
        label = html.escape(ids)
        title = html.escape("; ".join(row["source_address"] for row in group))
        markers.append(f'<g><title>{label}: {title}</title><circle cx="{x:.1f}" cy="{y:.1f}" r="19" fill="{color}" stroke="white" stroke-width="3"/><text x="{x:.1f}" y="{y+5:.1f}" text-anchor="middle" fill="white" font-size="12" font-weight="bold">{label}</text></g>')
    table_rows = []
    for row in rows:
        links = "No coordinate"
        if row.get("latitude") and row.get("longitude"):
            lat, lon = row["latitude"], row["longitude"]
            osm_url = "https://www.openstreetmap.org/" + "?" + urlencode({"mlat": lat, "mlon": lon, "zoom": 18})
            google_url = "https://www.google.com/maps/search/?" + urlencode({"api": 1, "query": f"{lat},{lon}"})
            links = f'<a href="{html.escape(osm_url, quote=True)}" target="_blank" rel="noopener">OSM pin</a> · <a href="{html.escape(google_url, quote=True)}" target="_blank" rel="noopener">Google pin</a>'
        fields = [row["id"], row["status"], row["source_address"], row["matched_address"], row["notes"]]
        cells = "".join(f"<td>{html.escape(value)}</td>" for value in fields)
        table_rows.append(f'<tr>{cells}<td>{links}</td></tr>')
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Geocode review</title>
<style>body{{font-family:system-ui,sans-serif;margin:0;color:#111;background:#f4f5f4}}main{{max-width:1200px;margin:auto;padding:20px}}h1{{margin-bottom:4px}}p{{line-height:1.5}}svg{{width:100%;height:auto;background:#eaf0ed;border:1px solid #aaa;border-radius:8px}}table{{width:100%;border-collapse:collapse;background:white}}th,td{{text-align:left;vertical-align:top;padding:9px;border-bottom:1px solid #ccc}}th{{background:#dde6e0}}tr:nth-child(even){{background:#f6f7f6}}.scroll{{overflow-x:auto}}.ready{{color:#136b37}}.review{{color:#b65000}}a{{color:#064f9e}}</style></head><body><main><h1>Geocode review</h1><p>This diagram shows relative coordinates, not streets or driving routes. Green = READY; orange = REVIEW. Open a pin in OpenStreetMap or Google Maps to check the actual building and driveway. Multiple IDs in one circle share the exact same geocoder point.</p>
<svg viewBox="0 0 900 600" role="img" aria-label="Relative location of geocoded stops"><text x="15" y="24" font-size="15">North ↑</text>{''.join(markers)}</svg>
<p>Geocoding data © OpenStreetMap contributors. Source addresses are preserved. No point is approved for volunteer use by this diagram.</p>
<div class="scroll"><table><thead><tr><th>ID</th><th>Status</th><th>Source address</th><th>Matched address</th><th>Reason</th><th>Inspect pin</th></tr></thead><tbody>{''.join(table_rows)}</tbody></table></div></main></body></html>'''


def write_review_map(validation_path: str | Path, output_path: str | Path) -> Path:
    rows = read_validation(validation_path)
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(generate_review_map(rows), encoding="utf-8")
    return target
