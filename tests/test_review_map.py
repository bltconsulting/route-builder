import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from route_builder.review_map import generate_review_map


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
