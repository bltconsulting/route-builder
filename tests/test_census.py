import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from route_builder.census import compare_row


class CensusTests(unittest.TestCase):
    def test_comparison_flags_large_coordinate_gap(self):
        match = {"matchedAddress": "5370 E HILL RD, GRAND BLANC, MI, 48439", "coordinates": {"x": -83.598658, "y": 42.945250}, "addressComponents": {"zip": "48439"}, "tigerLine": {"tigerLineId": "123"}}
        near = compare_row("05", "5370 E Hill Rd, Grand Blanc, MI 48439", [match], {"status": "REVIEW", "latitude": "42.945225", "longitude": "-83.598696"})
        self.assertEqual(near["census_result"], "MATCH")
        self.assertLess(int(near["separation_meters"]), 10)
        far = compare_row("05", "5370 E Hill Rd, Grand Blanc, MI 48439", [match], {"latitude": "42.9", "longitude": "-83.5"})
        self.assertIn("over 250 m", far["notes"])
        self.assertEqual(compare_row("05", "source", [], {})["census_result"], "NO MATCH")
