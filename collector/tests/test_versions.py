import unittest

from patchnotes.collector import parse_version


class ParseVersionTest(unittest.TestCase):
    def test_typical_subjects(self):
        self.assertEqual(parse_version("7.1 data"), "7.1")
        self.assertEqual(parse_version("7.0 import 2"), "7.0")
        self.assertEqual(parse_version("6.4 part 1"), "6.4")
        self.assertEqual(parse_version("6.3 max win"), "6.3")

    def test_non_version_subjects(self):
        self.assertIsNone(parse_version("fix typo"))
        self.assertIsNone(parse_version("v5.2.14"))
        self.assertIsNone(parse_version(""))

    def test_two_digit_minor(self):
        self.assertEqual(parse_version("10.12 data"), "10.12")


if __name__ == "__main__":
    unittest.main()
