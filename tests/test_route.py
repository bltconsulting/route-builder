import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from route_builder.route import Stop, rotate_loop


class RotationTests(unittest.TestCase):
    def test_rotates_without_reordering_loop(self):
        stops = [Stop("A", "A", 42.0, -83.0), Stop("B", "B", 42.1, -83.0), Stop("C", "C", 42.2, -83.0)]
        self.assertEqual([s.id for s in rotate_loop(stops, 42.2, -83.0)], ["C", "A", "B"])

    def test_empty_route_rejected(self):
        with self.assertRaises(ValueError):
            rotate_loop([], 0, 0)
