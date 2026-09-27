import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from route_builder.input import read_addresses


class InputTests(unittest.TestCase):
    def test_preserves_id_and_exact_address(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "addresses.csv"
            path.write_text('id,address\n01," 10 Main St, Flint, MI "\n')
            self.assertEqual(read_addresses(path)[0].id, "01")
            self.assertEqual(read_addresses(path)[0].source_address, " 10 Main St, Flint, MI ")

    def test_rejects_unquoted_comma(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "addresses.csv"
            path.write_text("id,address\n01,10 Main St, Flint, MI\n")
            with self.assertRaisesRegex(ValueError, "CSV line 2.*quote addresses"):
                read_addresses(path)

    def test_rejects_duplicate_ids(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "addresses.csv"
            path.write_text("id,address\n01,First\n01,Second\n")
            with self.assertRaisesRegex(ValueError, "duplicate id"):
                read_addresses(path)
