"""라우터 점검 도구 테스트. 실행: python3 -m unittest tests.test_route_check -v"""
import csv
import tempfile
import unittest
from pathlib import Path

from core.kb import load_kb
from core.route_check import check_row, expected_route, run, style_of
from core.router import Router

ROUTER = Router(load_kb())
EVAL = Path(__file__).resolve().parent.parent / "data" / "eval"


class RouteCheckTest(unittest.TestCase):
    def test_expected_route(self):
        self.assertEqual(expected_route("알베도/원소"), ("lookup", "알베도", "element", {}))
        self.assertEqual(expected_route("지역=몬드, 성급=5"), ("filter", None, None, {"region": "몬드", "rarity": "5성"}))
        self.assertEqual(expected_route(""), ("unknown", None, None, {}))

    def test_check_row(self):
        self.assertEqual(check_row(ROUTER, "알베도 원소가 뭐야?", "알베도/원소")[:2], (True, True))
        self.assertEqual(check_row(ROUTER, "몬드 출신 5성 캐릭터 누구 있어?", "지역=몬드, 성급=5성")[:2], (True, True))
        self.assertTrue(check_row(ROUTER, "원신에서 제일 센 캐릭터는?", "")[0])
        self.assertFalse(check_row(ROUTER, "알베도무기뭐씀", "알베도/무기")[0])   # 지금 라우터의 약점

    def test_style_of(self):
        self.assertEqual(style_of("띄어쓰기 없음 (beginner_x_4)"), "띄어쓰기 없음")
        self.assertEqual(style_of(""), "(말투 없음)")

    def test_run_on_file(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "q.csv"
            with open(path, "w", encoding="utf-8-sig", newline="") as f:
                w = csv.DictWriter(f, fieldnames=["question", "target", "note"])
                w.writeheader()
                w.writerow({"question": "알베도 원소가 뭐야?", "target": "알베도/원소", "note": "반말 (a)"})
                w.writerow({"question": "알베도무기뭐씀", "target": "알베도/무기", "note": "붙여쓰기 (b)"})
            result = run(path, ROUTER, show=0)
        self.assertEqual((result["n"], result["correct"]), (2, 1))

    def test_style_sets_are_split_by_character(self):
        # 개발용(학습용 캐릭터)과 평가용(평가용 캐릭터) 말투 질문에 같은 캐릭터가 섞이면 안 된다
        def chars(name):
            with open(EVAL / name, encoding="utf-8-sig", newline="") as f:
                return {r["target"].rsplit("/", 1)[0] for r in csv.DictReader(f)}
        self.assertFalse(chars("style_questions_dev.csv") & chars("style_questions_v1.csv"))
        self.assertEqual(len(chars("style_questions_v1.csv")), 22)


if __name__ == "__main__":
    unittest.main()
