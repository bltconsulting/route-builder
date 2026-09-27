import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from route_builder.geocode import classify, fallback_queries, street_key, validate_csv
from route_builder.input import Address


class FakeGeocoder:
    def search(self, address):
        return [{"display_name": "10 Main Street, Flint, MI 48503", "lat": "43.0", "lon": "-83.0", "address": {"house_number": "10", "road": "Main Street", "postcode": "48503"}}]


class GeocodeTests(unittest.TestCase):
    def test_common_street_abbreviations(self):
        self.assertIn(street_key("East Grand Blanc Road"), street_key("410 E. Grand Blanc Rd., Grand Blanc, MI 48439"))

    def test_limited_fallback_queries(self):
        self.assertEqual(fallback_queries("5370 E Hill Rd, Grand Blanc, MI 48439"), ["5370 east Hill road, Grand Blanc, MI 48439", "5370 east Hill road, Michigan 48439"])
        self.assertEqual(fallback_queries("Service Department, 800 N State Rd, Davison, MI 48423")[0], "800 north State road, Davison, MI 48423")

    def test_ready_requires_unique_matching_house_street_and_zip(self):
        address = Address("01", "10 Main Street, Flint, MI 48503")
        match = FakeGeocoder().search(address.source_address)
        self.assertEqual(classify(address, match)["status"], "READY")
        self.assertEqual(classify(address, match * 2)["status"], "REVIEW")
        self.assertIn("10 Main Street", classify(address, match * 2)["other_candidates"])
        self.assertEqual(classify(Address("01", "11 Main Street, Flint, MI 48503"), match)["status"], "REVIEW")
        self.assertEqual(classify(address, [dict(match[0], address={"house_number": "10", "road": "Elsewhere Street", "postcode": "48503"})])["status"], "REVIEW")
        self.assertEqual(classify(address, [dict(match[0], lat="NaN")])["status"], "REVIEW")
        self.assertEqual(classify(address, [])["status"], "FAILED")
        self.assertEqual(classify(address, match, relaxed=True)["status"], "REVIEW")

    def test_report_preserves_source_and_status(self):
        with TemporaryDirectory() as directory:
            source = Path(directory) / "input.csv"
            target = Path(directory) / "validation.csv"
            source.write_text('id,address\n01,"10 Main Street, Flint, MI 48503"\n')
            rows = validate_csv(source, FakeGeocoder(), target)
            self.assertEqual(rows[0]["source_address"], "10 Main Street, Flint, MI 48503")
            self.assertEqual(rows[0]["status"], "READY")
            self.assertIn("provider_metadata", target.read_text())
