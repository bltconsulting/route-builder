import sys
import csv
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from route_builder.review_map import generate_review_map, write_census_review_map


class ReviewMapTests(unittest.TestCase):
    def test_groups_duplicate_points_and_escapes_addresses(self):
        rows = [
            {"id": "04", "status": "REVIEW", "source_address": "10 <Main>", "matched_address": "Main", "latitude": "42.0", "longitude": "-83.0", "notes": "street only"},
            {"id": "18", "status": "REVIEW", "source_address": "20 Main", "matched_address": "Main", "latitude": "42.0", "longitude": "-83.0", "notes": "street only"},
            {"id": "19", "status": "FAILED", "source_address": "Elsewhere", "matched_address": "", "latitude": "", "longitude": "", "notes": "No candidate"},
        ]
        page = generate_review_map(rows)
        self.assertIn("04, 18", page)
        self.assertIn("10 &lt;Main&gt;", page)
        self.assertNotIn("10 <Main>", page)
        self.assertIn("No coordinate", page)
        self.assertIn("openstreetmap.org", page)

    def test_census_review_shows_routed_pin(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "comparison.csv"
            with source.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=["id", "source_address", "census_result", "census_matched_address", "census_latitude", "census_longitude", "nominatim_status", "notes"])
                writer.writeheader()
                writer.writerow({"id": "01", "source_address": "1 Main", "census_result": "MATCH", "census_matched_address": "1 MAIN", "census_latitude": "42.1", "census_longitude": "-83.2", "nominatim_status": "READY", "notes": ""})
            target = Path(directory) / "review.html"
            write_census_review_map(source, target)
            page = target.read_text(encoding="utf-8")
            self.assertIn("Census destination pin review", page)
            self.assertIn("42.1", page)
            self.assertIn("-83.2", page)
            self.assertNotIn("Geocoding data © OpenStreetMap", page)
