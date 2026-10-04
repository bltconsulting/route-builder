import csv
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from route_builder.matrix import DrivingMatrix
from route_builder.route import Stop
from route_builder.routing import build_optimized_route


class RoutingOutputTests(unittest.TestCase):
    def test_export_preserves_addresses_and_closes_loop(self):
        stops = [Stop("a", "1 First St", 42.0, -83.0), Stop("b", "2 Second St", 42.1, -83.1)]
        matrix = DrivingMatrix([[0, 12], [15, 0]], [[0, 100], [120, 0]], [2, 3])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            comparison = root / "comparison.csv"
            with comparison.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=["id", "census_matched_address"])
                writer.writeheader()
                writer.writerows([{"id": "a", "census_matched_address": "1 FIRST ST"}, {"id": "b", "census_matched_address": "2 SECOND ST"}])
            with patch("route_builder.routing.build_stops_from_census", return_value=stops), patch("route_builder.routing.OsrmMatrixAdapter") as adapter, patch("route_builder.routing.solve_closed_loop", return_value=[1, 0]):
                adapter.return_value.table.return_value = matrix
                order = build_optimized_route(root / "input.csv", comparison, root / "out", "https://example.test", "North-Route.html")
            with (root / "out" / "route.csv").open(newline="", encoding="utf-8") as stream:
                rows = list(csv.DictReader(stream))
            html = (root / "out" / "North-Route.html").read_text(encoding="utf-8")
            self.assertEqual(order, ["b", "a"])
            self.assertEqual([(r["id"], r["next_id"]) for r in rows], [("b", "a"), ("a", "b")])
            self.assertEqual(rows[0]["leg_duration_s"], "15")
            self.assertEqual(rows[1]["source_address"], "1 First St")
            self.assertEqual(rows[1]["matched_address"], "1 FIRST ST")
            self.assertLess(html.index('"id": "b"'), html.index('"id": "a"'))
            self.assertIn("TEST ROUTE", html)


if __name__ == "__main__":
    unittest.main()
