import unittest

from patchnotes.textutil import clean_text, humanize_field, shorten


class CleanTextTest(unittest.TestCase):
    def test_removes_color_tags(self):
        raw = "<color=#FFD780FF>일반 공격</color>\n창으로 공격한다."
        self.assertEqual(clean_text(raw), "일반 공격\n창으로 공격한다.")

    def test_collapses_spaces_and_blank_lines(self):
        self.assertEqual(clean_text("가   나\n\n\n다  "), "가 나\n다")

    def test_non_string_is_returned_as_is(self):
        self.assertEqual(clean_text([1, 2]), [1, 2])
        self.assertIsNone(clean_text(None))


class ShortenTest(unittest.TestCase):
    def test_joins_lines_and_truncates(self):
        self.assertEqual(shorten("가\n나"), "가 / 나")
        self.assertEqual(shorten("a" * 10, limit=5), "aaaaa…")


class HumanizeFieldTest(unittest.TestCase):
    def test_skill_and_subfield(self):
        self.assertEqual(humanize_field("combat2/description"), "원소 스킬 설명")

    def test_list_index_is_one_based(self):
        self.assertEqual(humanize_field("combat3/attributes/labels[0]"), "원소 폭발 수치 항목 #1")

    def test_passive_and_constellation(self):
        self.assertEqual(humanize_field("passive2/name"), "고유 특성 2 이름")
        self.assertEqual(humanize_field("c4/effect"), "명의 자리 4 효과")

    def test_unknown_field_is_kept(self):
        self.assertEqual(humanize_field("weird/field"), "weird field")


if __name__ == "__main__":
    unittest.main()
