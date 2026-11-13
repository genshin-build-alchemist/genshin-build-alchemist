"""lib/text.py와 content/*.yaml 테스트 (yaml 읽기 · based_on · 굵게 표시).

실행 (저장소 루트에서): python -m unittest discover -s dashboard/tests
"""
import datetime
import os
import sys
import tempfile
import unittest
from pathlib import Path

DASHBOARD = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(DASHBOARD))

from lib import loader, text  # noqa: E402

CONTENT_FILES = {"stages": "official", "performance": "official", "response_time": "dev",
                 "aux": "aux", "model_compare": "model_compare"}


def folder_result(folder="dev", latest="2026-11-10T06:05:17"):
    return {"folder": folder, "latest_created_at": latest}


class LoadContentTest(unittest.TestCase):
    def test_missing_file_is_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(text.load_content("nope", tmp), {})
            self.assertEqual(text.stage_order(tmp), loader.DEFAULT_ORDER)

    def test_reads_yaml(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "stages.yaml").write_text("order: [a, b]\n", encoding="utf-8")
            self.assertEqual(text.stage_order(tmp), ["a", "b"])

    def test_all_content_files_load(self):
        for name in CONTENT_FILES:
            with self.subTest(name=name):
                self.assertTrue(text.load_content(name), f"{name}.yaml이 비어 있거나 없음")

    def test_works_from_other_directory(self):
        old = os.getcwd()
        with tempfile.TemporaryDirectory() as tmp:
            os.chdir(tmp)
            try:
                order = text.stage_order()
            finally:
                os.chdir(old)
        self.assertEqual(order[0], "baseline")


class BasedOnTest(unittest.TestCase):
    def test_same_is_none(self):
        content = {"based_on": {"folder": "dev", "created_at": "2026-11-10T06:05:17"}}
        self.assertIsNone(text.based_on_status(content, folder_result()))

    def test_unquoted_date_is_same(self):
        # yaml에 따옴표 없이 쓰면 datetime으로 읽힌다 -> 같은 시각이면 같다고 본다
        content = {"based_on": {"folder": "dev", "created_at": datetime.datetime(2026, 11, 10, 6, 5, 17)}}
        self.assertIsNone(text.based_on_status(content, folder_result()))

    def test_newer_data_shows_message(self):
        content = {"based_on": {"folder": "dev", "created_at": "2026-11-01T00:00:00"}}
        self.assertEqual(text.based_on_status(content, folder_result()), text.STALE_MSG)

    def test_other_folder_shows_message(self):
        content = {"based_on": {"folder": "aux", "created_at": "2026-11-10T06:05:17"}}
        self.assertEqual(text.based_on_status(content, folder_result()), text.STALE_MSG)

    def test_missing_based_on_shows_message(self):
        self.assertIn(text.STALE_MSG, text.based_on_status({}, folder_result()))


class RichTest(unittest.TestCase):
    def test_bold_and_escape(self):
        self.assertEqual(text.rich("**굵게** a < b"), "<b>굵게</b> a &lt; b")
        self.assertEqual(text.rich("줄1\n줄2"), "줄1<br>줄2")
        self.assertEqual(text.rich('"따옴표"'), '"따옴표"')
        self.assertEqual(text.rich("`max_new_tokens=160`, `]`"), "<code>max_new_tokens=160</code>, <code>]</code>")


@unittest.skipUnless(all((loader.DATA_DIR / f).is_dir() for f in loader.FOLDERS), "dashboard/data 폴더가 없음")
class ContentMatchesDataTest(unittest.TestCase):
    """지금 yaml 글이 지금 데이터를 보고 쓴 것인지 (based_on이 최신인지)."""

    def test_based_on_is_current(self):
        order = text.stage_order()
        for name, folder in CONTENT_FILES.items():
            with self.subTest(name=name):
                content = text.load_content(name)
                self.assertEqual(content["based_on"]["folder"], folder)
                self.assertIsNone(text.based_on_status(content, loader.load_folder(folder, order=order)))

    def test_stage_order_covers_data(self):
        order = text.stage_order()
        for folder in ("official", "dev", "aux"):
            methods = {r["key"] for r in loader.load_folder(folder, order=order)["runs"]}
            self.assertTrue(methods <= set(order), f"{folder}: stages.yaml에 없는 단계 {methods - set(order)}")

    def test_every_stage_has_texts(self):
        stages = text.load_content("stages")
        for key in stages["order"]:
            self.assertEqual(set(stages["stages"][key]) >= {"label", "change", "learned", "problem"}, True, key)


if __name__ == "__main__":
    unittest.main()
