import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from route_builder.matrix import DrivingMatrix
from route_builder.optimize import solve_closed_loop


class OptimizeTests(unittest.TestCase):
    def test_closed_loop_covers_each_stop_once(self):
        costs = [[0, 1, 9, 1], [1, 0, 1, 9], [9, 1, 0, 1], [1, 9, 1, 0]]
        matrix = DrivingMatrix(costs, costs, [0, 0, 0, 0])
        order = solve_closed_loop(matrix, 1)
        self.assertEqual(order[0], 0)
        self.assertEqual(set(order), {0, 1, 2, 3})
        self.assertEqual(sum(costs[order[i]][order[(i + 1) % 4]] for i in range(4)), 4)
