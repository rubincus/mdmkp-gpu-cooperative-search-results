"""Unit tests of the evaluators of verify_solutions.py and verify_scherer.py.

The first instance is the one of Proposition 1 of the manuscript: four items with profits 1, 1, 2 and 2, the capacity
rows x1 + x3 <= 1, x1 + x4 <= 1, x2 + x3 <= 1 and x2 + x4 <= 1, and the demand row x1 + x2 + x3 + x4 >= 2. Its
feasible selections are {1, 2} and {3, 4}, and both are isolated.

Usage: python -m unittest discover -s scripts
"""
import unittest
from fractions import Fraction

from verify_scherer import evaluate as evaluate_exact, neighbours as neighbours_exact, parse_file, scaled_bytes
from verify_solutions import evaluate, neighbours, parse_instance

ISOLATED = b"""4 4 1
1 1 2 2
1 0 1 0
1 0 0 1
0 1 1 0
0 1 0 1
1 1 1 1
1 1 1 1
2
"""

# the same items with one capacity row x1 + x2 + x3 + x4 <= 3 and one demand row x1 + x2 + x3 + x4 >= 1
OPEN = b"""4 1 1
1 1 2 2
1 1 1 1
3
1 1 1 1
1
"""


class EvaluatorTest(unittest.TestCase):
    def setUp(self):
        self.isolated = parse_instance(ISOLATED)
        self.open = parse_instance(OPEN)

    def test_parse(self):
        inst = self.isolated
        self.assertEqual((inst['n'], inst['m'], inst['q']), (4, 4, 1))
        self.assertEqual(inst['p'], [1, 1, 2, 2])
        self.assertEqual(inst['b'], [1, 1, 1, 1])
        self.assertEqual(inst['e'], [2])

    def test_trailing_data_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_instance(ISOLATED + b' 7')

    def test_feasible_selections(self):
        self.assertEqual(evaluate(self.isolated, [0, 1]), {'profit': 2, 'cardinality': 2, 'feasible': True})
        self.assertEqual(evaluate(self.isolated, [2, 3]), {'profit': 4, 'cardinality': 2, 'feasible': True})

    def test_infeasible_selections(self):
        self.assertFalse(evaluate(self.isolated, [0, 2])['feasible'])      # capacity row x1 + x3 <= 1
        self.assertFalse(evaluate(self.isolated, [3])['feasible'])         # demand row
        self.assertFalse(evaluate(self.isolated, [0, 1, 2])['feasible'])   # capacity rows

    def test_invalid_indices(self):
        self.assertIsNone(evaluate(self.isolated, [0, 0]))
        self.assertIsNone(evaluate(self.isolated, [4]))
        self.assertIsNone(evaluate(self.isolated, [-1]))

    def test_isolated_selections(self):
        self.assertEqual(neighbours(self.isolated, [0, 1]), (8, 0, 0))
        self.assertEqual(neighbours(self.isolated, [2, 3]), (8, 0, 0))

    def test_open_neighbourhood(self):
        # from {1, 2}: two drops, two additions and four swaps, all feasible; the additions and the swaps improve
        self.assertEqual(neighbours(self.open, [0, 1]), (8, 8, 6))
        # from {1, 2, 3}: three drops and three swaps are feasible; the addition of item 4 exceeds the capacity
        self.assertEqual(neighbours(self.open, [0, 1, 2]), (7, 6, 2))


# the instance of Proposition 1 in the format of Scherer (2024), with best-found value 4
SCHERER_ISOLATED = """[1, 4.0]
[4, 4, 1]
[1.0, 1.0, 2.0, 2.0]
[1.0, 1.0, 1.0, 1.0]
[2.0]
[[1.0, 0.0, 1.0, 0.0], [1.0, 0.0, 0.0, 1.0], [0.0, 1.0, 1.0, 0.0], [0.0, 1.0, 0.0, 1.0]]
[[1.0, 1.0, 1.0, 1.0]]
"""

# two items with the capacity row 0.1 x1 + 0.2 x2 <= 0.3, which double precision would declare violated by {1, 2}
SCHERER_DECIMAL = """[2, 0.5]
[2, 1, 1]
[0.25, 0.25]
[0.3]
[0.1]
[[0.1, 0.2]]
[[0.05, 0.05]]
"""


class ExactEvaluatorTest(unittest.TestCase):
    def test_parse(self):
        inst = parse_file(SCHERER_ISOLATED)[1]
        self.assertEqual((inst['n'], inst['m'], inst['q'], inst['best']), (4, 4, 1, 4))
        self.assertEqual(inst['e'], [2])

    def test_isolated_selections(self):
        inst = parse_file(SCHERER_ISOLATED)[1]
        self.assertEqual(evaluate_exact(inst, [2, 3]), {'profit': 4, 'cardinality': 2, 'feasible': True})
        self.assertEqual(neighbours_exact(inst, [0, 1]), (8, 0, 0))
        self.assertEqual(neighbours_exact(inst, [2, 3]), (8, 0, 0))

    def test_exact_decimals(self):
        inst = parse_file(SCHERER_DECIMAL)[2]
        self.assertGreater(0.1 + 0.2, 0.3)
        self.assertEqual(evaluate_exact(inst, [0, 1]), {'profit': Fraction(1, 2), 'cardinality': 2, 'feasible': True})
        # from {1, 2}: the demand row 0.05 x1 + 0.05 x2 >= 0.1 needs both items, so no drop is feasible
        self.assertEqual(neighbours_exact(inst, [0, 1]), (2, 0, 0))

    def test_conservative_rounding(self):
        inst = parse_file(SCHERER_DECIMAL)[2]
        self.assertEqual(scaled_bytes(inst, 1000, '\n'), b'2 1 1\n250 250\n100 200\n300\n50 50\n100\n')


if __name__ == '__main__':
    unittest.main()
