"""Synthetic edge cases for gray inline-address contact rows."""

import unittest

from route_builder.contacts.ys_inline import Line, parse_pages


class InlineHeaderTests(unittest.TestCase):
    def test_page_break_carries_address_and_blank_phone(self):
        pages = [
            [Line(1, 23, 700, "Genesee - Burton City - 007 · Burton · 1445 · Iva St")],
            [Line(2, 18, 39, "Doe, Jane"),
             Line(2, 23, 63, "Genesee - Burton City - 007 · Burton · 5058 · Way St"),
             Line(2, 18, 82, "Smith, Pat"), Line(2, 175, 82, "(810) 555-0100")],
        ]
        rows, report = parse_pages(pages)
        self.assertEqual([row['Address'] for row in rows], ['1445 Iva St', '5058 Way St'])
        self.assertEqual([row['Phone'] for row in rows], ['', '(810) 555-0100'])
        self.assertEqual(report['carried_pages'], [2])
        self.assertEqual(report['header_count'], 2)

    def test_unpaired_header_rejected(self):
        with self.assertRaisesRegex(ValueError, 'no name'):
            parse_pages([[Line(1, 23, 40, 'Genesee - Burton City - 007 · Burton · 5058 · Way St')]])


if __name__ == '__main__':
    unittest.main()
