import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from route_builder.generate import build_stops, build_stops_from_census, generate_html
from route_builder.route import Stop


class GenerationTests(unittest.TestCase):
    def test_supplied_data_and_fixture_join(self):
        stops = build_stops(ROOT / "sample_data/route_addresses", ROOT / "sample_data/demo_coordinates.json")
        self.assertEqual(len(stops), 22)
        self.assertEqual(stops[0].id, "01")
        self.assertEqual(stops[0].source_address, "410 E. Grand Blanc Rd., Grand Blanc, MI 48439")

    def test_output_is_self_contained_and_escapes_address(self):
        html = generate_html([Stop("01", "</script><script>alert(1)</script>", 42, -83)], ROOT / "templates")
        self.assertIn("START MY ROUTE", html)
        self.assertIn("START AT SELECTED STOP", html)
        self.assertIn("Location permission was denied", html)
        self.assertIn("localStorage", html)
        self.assertIn("REVISIT SKIPPED STOPS", html)
        self.assertIn("\\u003c/script>", html)
        self.assertNotIn("__ROUTE_DATA__", html)
        self.assertNotIn("<script>alert(1)</script>", html)

    def test_census_test_route_uses_matched_coordinates(self):
        with TemporaryDirectory() as directory:
            csv_path = Path(directory) / "addresses.csv"
            report_path = Path(directory) / "census.csv"
            csv_path.write_text('id,address\n01,"10 Main St, Flint, MI 48503"\n')
            report_path.write_text('id,source_address,census_result,census_latitude,census_longitude\n01,"10 Main St, Flint, MI 48503",MATCH,43.0,-83.0\n')
            stops = build_stops_from_census(csv_path, report_path)
            self.assertEqual(stops[0].latitude, 43.0)
            html = generate_html(stops, ROOT / "templates", "TEST ONLY: verify each destination")
            self.assertIn("TEST ONLY: verify each destination", html)
            self.assertNotIn("coordinates are placeholders", html)
