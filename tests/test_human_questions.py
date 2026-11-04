"""사람 질문 정답 채우기 테스트. 실행: python3 -m unittest tests.test_human_questions -v"""
import csv
import tempfile
import unittest
from pathlib import Path

from core.human_questions import answer_for_target, fill_csv, fill_rows
from core.kb import load_kb

KB = load_kb()
TEMPLATE = Path(__file__).resolve().parent.parent / "data" / "eval" / "human_questions_template.csv"


class AnswerForTargetTest(unittest.TestCase):
    def test_lookup(self):
        self.assertEqual(answer_for_target("알베도/원소", KB), (["바위"], None))
        self.assertEqual(answer_for_target("진/무기", KB), (["한손검"], None))
        self.assertEqual(answer_for_target("북두/성급", KB), (["4성"], None))
        self.assertEqual(answer_for_target(" 알하이탐 / 지역 ", KB), (["수메르"], None))

    def test_filter(self):
        names, msg = answer_for_target("지역=몬드, 성급=5성", KB)
        self.assertIsNone(msg)
        self.assertEqual(names, sorted(c["name"] for c in KB.characters
                                       if c["region"] == "몬드" and c["rarity"] == "5성"))
        self.assertIn("알베도", names)

    def test_value_spelling_is_normalized(self):
        a = answer_for_target("원소=불, 무기=활", KB)[0]
        self.assertEqual(answer_for_target("원소=불원소, 무기=활", KB)[0], a)
        self.assertEqual(answer_for_target("성급=5, 지역=몬드 출신", KB)[0],
                         answer_for_target("성급=5성급, 지역=몬드", KB)[0])

    def test_unknown_is_empty(self):
        self.assertEqual(answer_for_target("", KB), ([], None))

    def test_errors_suggest_fixes(self):
        answer, msg = answer_for_target("알베로/원소", KB)       # 오타
        self.assertIsNone(answer)
        self.assertIn("알베도", msg)
        self.assertIsNone(answer_for_target("알베도/키", KB)[0])
        self.assertIsNone(answer_for_target("지역=몬드드", KB)[0])
        self.assertIsNone(answer_for_target("알베도 원소", KB)[0])

    def test_missing_data_and_empty_filter_are_warnings(self):
        no_region = next(c["name"] for c in KB.characters if not c["region"])
        self.assertEqual(answer_for_target(f"{no_region}/지역", KB)[0], [])
        answer, msg = answer_for_target("지역=몬드, 무기=법구, 원소=번개, 성급=5성", KB)
        self.assertEqual(answer, [])
        self.assertIn("없어서", msg)


class FillTest(unittest.TestCase):
    def test_rows_and_manual_answer_check(self):
        rows = [{"question": "알베도 속성?", "target": "알베도/원소", "answer": "불"},
                {"question": "", "target": "진/무기"},                       # 빈 질문은 건너뜀
                {"question": "오타 질문", "target": "알베로/원소"}]
        out, errors = fill_rows(rows, KB)
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0]["answer"], "바위")
        self.assertTrue(out[0]["check"].startswith("확인:"))
        self.assertEqual(errors, 1)
        self.assertTrue(out[1]["check"].startswith("오류:"))

    def test_template_fills_without_errors(self):
        with tempfile.TemporaryDirectory() as d:
            dst, out, errors = fill_csv(TEMPLATE, Path(d) / "filled.csv", KB)
            with open(dst, encoding="utf-8-sig", newline="") as f:
                rows = list(csv.DictReader(f))
        self.assertEqual(errors, 0)
        self.assertEqual(len(rows), 5)
        self.assertEqual(rows[0]["answer"], "바위")
        self.assertEqual(rows[4]["answer"], "")          # 데이터에 없는 질문
        self.assertEqual(list(rows[0]), ["question", "answer", "target", "note", "check"])


if __name__ == "__main__":
    unittest.main()
