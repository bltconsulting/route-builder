"""Census Geocoder adapter and reproducible comparison report."""

import csv
import json
import logging
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .input import read_addresses
from .route import distance_km

LOG = logging.getLogger(__name__)
ENDPOINT = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"
BENCHMARK = "Public_AR_Current"


class CensusGeocoder:
    def __init__(self, cache_path: str | Path):
        self.cache_path = Path(cache_path)
        self.cache = json.loads(self.cache_path.read_text(encoding="utf-8")) if self.cache_path.exists() else {}
        self.last_request = 0.0

    def search(self, address: str) -> list[dict]:
        key = f"{BENCHMARK}|{address}"
        if key in self.cache:
            LOG.info("Cached Census lookup: %s", address)
            return self.cache[key]
        elapsed = time.monotonic() - self.last_request
        if self.last_request and elapsed < 0.5:
            time.sleep(0.5 - elapsed)
        url = ENDPOINT + "?" + urlencode({"address": address, "benchmark": BENCHMARK, "format": "json"})
        request = Request(url, headers={"User-Agent": "RouteBuilderLocal/0.1 (+https://github.com/bltconsulting/route-builder)", "Accept": "application/json"})
        self.last_request = time.monotonic()
        with urlopen(request, timeout=30) as response:
            data = json.load(response)
        matches = data["result"]["addressMatches"]
        if not isinstance(matches, list):
            raise ValueError("Census Geocoder returned unexpected matches")
        self.cache[key] = matches
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(json.dumps(self.cache, ensure_ascii=False, indent=2), encoding="utf-8")
        LOG.info("Census lookup: %s (%d matches)", address, len(matches))
        return matches


def compare_row(stop_id: str, source: str, matches: list[dict], nominatim: dict[str, str]) -> dict[str, str]:
    row = {"id": stop_id, "source_address": source, "census_result": "NO MATCH", "census_match_count": str(len(matches)), "census_matched_address": "", "census_latitude": "", "census_longitude": "", "census_zip": "", "census_tiger_line": "", "census_google_pin": "", "nominatim_status": nominatim.get("status", ""), "nominatim_matched_address": nominatim.get("matched_address", ""), "nominatim_latitude": nominatim.get("latitude", ""), "nominatim_longitude": nominatim.get("longitude", ""), "nominatim_google_pin": "", "separation_meters": "", "notes": ""}
    if row["nominatim_latitude"] and row["nominatim_longitude"]:
        row["nominatim_google_pin"] = "https://www.google.com/maps/search/?" + urlencode({"api": 1, "query": f"{row['nominatim_latitude']},{row['nominatim_longitude']}"})
    if not matches:
        row["notes"] = "No Census address-range match"
        return row
    match = matches[0]
    coords = match.get("coordinates") or {}
    components = match.get("addressComponents") or {}
    row.update(census_result="MATCH" if len(matches) == 1 else "MULTIPLE", census_matched_address=str(match.get("matchedAddress", "")), census_latitude=str(coords.get("y", "")), census_longitude=str(coords.get("x", "")), census_zip=str(components.get("zip", "")), census_tiger_line=str((match.get("tigerLine") or {}).get("tigerLineId", "")))
    if row["census_latitude"] and row["census_longitude"]:
        row["census_google_pin"] = "https://www.google.com/maps/search/?" + urlencode({"api": 1, "query": f"{row['census_latitude']},{row['census_longitude']}"})
    notes = []
    if len(matches) > 1:
        notes.append("Multiple Census matches; first shown")
    if row["census_zip"] and row["census_zip"] not in source:
        notes.append("Census ZIP differs from source")
    if row["census_latitude"] and row["census_longitude"] and row["nominatim_latitude"] and row["nominatim_longitude"]:
        meters = 1000 * distance_km(float(row["census_latitude"]), float(row["census_longitude"]), float(row["nominatim_latitude"]), float(row["nominatim_longitude"]))
        row["separation_meters"] = f"{meters:.0f}"
        if meters > 250:
            notes.append("Coordinates differ by over 250 m")
    row["notes"] = "; ".join(notes)
    return row


def compare_csv(csv_path: str | Path, validation_path: str | Path, geocoder: CensusGeocoder, output_path: str | Path) -> list[dict[str, str]]:
    with Path(validation_path).open(newline="", encoding="utf-8") as stream:
        nominatim = {row["id"]: row for row in csv.DictReader(stream)}
    rows = [compare_row(address.id, address.source_address, geocoder.search(address.source_address), nominatim.get(address.id, {})) for address in read_addresses(csv_path)]
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    LOG.info("Wrote %s: %d Census matches, %d no matches", target, sum(row["census_result"] != "NO MATCH" for row in rows), sum(row["census_result"] == "NO MATCH" for row in rows))
    return rows
