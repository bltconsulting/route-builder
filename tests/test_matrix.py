import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from route_builder.matrix import parse_osrm_table


class MatrixTests(unittest.TestCase):
    def test_parses_asymmetric_driving_matrix(self):
        result = parse_osrm_table({"code": "Ok", "durations": [[0, 12], [15, 0]], "distances": [[0, 100], [120, 0]], "sources": [{"distance": 2}, {"distance": 4}]}, 2)
        self.assertEqual(result.durations[1][0], 15)
        self.assertEqual(result.distances[0][1], 100)
        self.assertEqual(result.snap_distances, [2, 4])

    def test_rejects_unreachable_leg(self):
        data = {"code": "Ok", "durations": [[0, None], [10, 0]], "distances": [[0, 100], [100, 0]], "sources": [{"distance": 0}, {"distance": 0}]}
        with self.assertRaisesRegex(ValueError, "unreachable"):
            parse_osrm_table(data, 2)
