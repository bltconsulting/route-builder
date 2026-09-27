"""Small geocoding boundary and conservative organizer validation."""

import csv
import json
import logging
import re
import time
from math import isfinite
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .input import Address, read_addresses

LOG = logging.getLogger(__name__)
STREET_WORDS = {"e": "east", "w": "west", "n": "north", "s": "south", "rd": "road", "st": "street", "dr": "drive", "cir": "circle", "blvd": "boulevard", "hwy": "highway", "ln": "lane", "ct": "court", "ave": "avenue"}


def street_key(value: str) -> str:
    words = re.findall(r"[a-z0-9]+", value.lower())
    return "".join(STREET_WORDS.get(word, word) for word in words)


def fallback_queries(source_address: str) -> list[str]:
    """Try limited formatting changes; fallback matches always require review."""
    parts = [part.strip() for part in source_address.split(",")]
    if len(parts) >= 4 and not re.search(r"\d", parts[0]) and re.search(r"\d", parts[1]):
        parts = parts[1:]
    base = ", ".join(parts)
    base = re.sub(r"\s+#\w+", "", base)
    base = re.sub(r"\b(e|w|n|s|rd|st|dr|cir|blvd|hwy|ln|ct|ave)\b\.?", lambda match: STREET_WORDS[match.group(1).lower()], base, flags=re.I)
    queries = [base]
    without_city = re.sub(r",\s*[^,]+,\s*MI\s*(\d{5})$", r", Michigan \1", base, flags=re.I)
    if without_city != base:
        queries.append(without_city)
    return [query for query in queries if query != source_address]


class NominatimGeocoder:
    """Nominatim-compatible search adapter with a local response cache."""

    def __init__(self, endpoint: str, user_agent: str, cache_path: str | Path):
        if not endpoint.startswith("https://"):
            raise ValueError("Geocoder endpoint must use HTTPS")
        if not user_agent.strip():
            raise ValueError("An identifying User-Agent is required")
        self.endpoint = endpoint
        self.user_agent = user_agent
        self.cache_path = Path(cache_path)
        self.cache = json.loads(self.cache_path.read_text(encoding="utf-8")) if self.cache_path.exists() else {}
        self.last_request = 0.0

    def search(self, address: str) -> list[dict]:
        key = f"{self.endpoint}|{address}"
        if key in self.cache:
            LOG.info("Cached geocode: %s", address)
            return self.cache[key]
        elapsed = time.monotonic() - self.last_request
        if self.last_request and elapsed < 1.1:
            time.sleep(1.1 - elapsed)
        query = urlencode({"q": address, "format": "jsonv2", "addressdetails": 1, "limit": 3})
        request = Request(f"{self.endpoint}?{query}", headers={"User-Agent": self.user_agent, "Accept": "application/json"})
        self.last_request = time.monotonic()
        with urlopen(request, timeout=20) as response:
            candidates = json.load(response)
        if not isinstance(candidates, list):
            raise ValueError("Geocoder returned an unexpected response")
        self.cache[key] = candidates
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(json.dumps(self.cache, ensure_ascii=False, indent=2), encoding="utf-8")
        LOG.info("Geocoded: %s (%d candidates)", address, len(candidates))
        return candidates


def classify(address: Address, candidates: list[dict], *, relaxed: bool = False) -> dict[str, str]:
    row = {"id": address.id, "source_address": address.source_address, "matched_address": "", "latitude": "", "longitude": "", "status": "FAILED", "notes": "No geocode candidate", "candidate_count": str(len(candidates)), "other_candidates": "", "provider_metadata": "", "attribution": "© OpenStreetMap contributors"}
    if not candidates:
        return row
    match = candidates[0]
    row.update(matched_address=str(match.get("display_name", "")), latitude=str(match.get("lat", "")), longitude=str(match.get("lon", "")), status="REVIEW")
    row["other_candidates"] = " | ".join(str(candidate.get("display_name", "")) for candidate in candidates[1:])
    row["provider_metadata"] = json.dumps({key: match.get(key) for key in ("osm_type", "osm_id", "category", "type", "place_rank")}, ensure_ascii=False)
    parts = match.get("address") or {}
    source_numbers = re.findall(r"\b\d+\b", address.source_address)
    house = str(parts.get("house_number", ""))
    postcode = str(parts.get("postcode", ""))
    road = str(parts.get("road", ""))
    reasons = []
    if relaxed:
        reasons.append("found through relaxed search; confirm location")
    if len(candidates) > 1:
        reasons.append("multiple candidates")
    if not house or not source_numbers or source_numbers[0] != house:
        reasons.append("house number unverified")
    if not postcode or postcode not in address.source_address:
        reasons.append("postal code unverified")
    normalized_source = street_key(address.source_address)
    normalized_road = street_key(road)
    if not normalized_road or normalized_road not in normalized_source:
        reasons.append("street unverified")
    try:
        lat, lon = float(row["latitude"]), float(row["longitude"])
        if not (isfinite(lat) and isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError
    except ValueError:
        reasons.append("coordinates invalid or missing")
    if not reasons:
        row["status"] = "READY"
        row["notes"] = "Unique candidate; house number, street, and postal code match. Organizer should still inspect."
    else:
        row["notes"] = "; ".join(reasons)
    return row


def validate_csv(csv_path: str | Path, geocoder: NominatimGeocoder, output_path: str | Path) -> list[dict[str, str]]:
    addresses = read_addresses(csv_path)
    rows = []
    for address in addresses:
        candidates = geocoder.search(address.source_address)
        relaxed = False
        if not candidates:
            for query in fallback_queries(address.source_address):
                candidates = geocoder.search(query)
                if candidates:
                    relaxed = True
                    break
        rows.append(classify(address, candidates, relaxed=relaxed))
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    LOG.info("Wrote %s: %s", target, ", ".join(f"{status}={sum(row['status'] == status for row in rows)}" for status in ("READY", "REVIEW", "FAILED")))
    LOG.warning("Inspect validation.csv before using any coordinates for volunteer navigation")
    return rows
