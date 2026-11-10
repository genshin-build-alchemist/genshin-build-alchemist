"""패치 질문 검색·답 테스트. 실행: python3 -m unittest tests.test_patch_search -v"""
import unittest

from core.kb import load_kb
from core.pipeline import Chatbot
from core.retrieval import PATCH_DETAIL_MAX, patch_records
from core.router import Router

KB = load_kb()
ROUTER = Router(KB)


class PatchRouteTest(unittest.TestCase):
    def test_folder_and_added(self):
        cases = {
            "7.1 신규 무기 뭐야?": ("weapons", True),
            "7.0 신규 캐릭터 누구야?": ("characters", True),
            "7.0에서 바뀐 무기 알려줘": ("weapons", False),
            "7.0 별자리 바뀐 캐릭터": ("constellations", False),
            "7.0에서 뭐 바뀌었어?": (None, False),
        }
        for q, (folder, added) in cases.items():
            rr = ROUTER.route(q)
            self.assertEqual((rr.route, rr.patch_folder, rr.patch_added), ("patch", folder, added), q)


class PatchRecordsTest(unittest.TestCase):
    def test_character_without_version_searches_all_versions(self):
        # 버전 없이 캐릭터만 물으면 최신 버전이 아니라 수집된 모든 버전에서 찾는다
        recs = patch_records(ROUTER.route("산드로네 패치로 뭐 바뀌었어?"), KB)
        self.assertTrue(recs)
        self.assertEqual({r["entity_name"] for r in recs}, {"산드로네"})
        self.assertEqual({r["version"] for r in recs}, {"6.7", "7.0"})

    def test_filters(self):
        recs = patch_records(ROUTER.route("7.1 신규 무기 뭐야?"), KB)
        self.assertTrue(recs)
        self.assertTrue(all(r["folder"] == "weapons" and r["change_type"] == "added" for r in recs))

    def test_version_outside_data(self):
        self.assertEqual(patch_records(ROUTER.route("4.0 패치 내용 알려줘"), KB), [])

    def test_collected_range(self):
        # 팀 결정: 패치 데이터는 5.0부터 (collector --since 5.0). 표기만 바뀐 기록은 수집 때 걸러진다
        self.assertEqual(KB.versions[0], "5.0")
        self.assertEqual(KB.version_range, f"5.0~{KB.latest_version}")
        from collector.patchnotes.noise import noise_rule
        noisy = [(r["version"], r["entity_name"], c["field"]) for r in KB.patches for c in r["changes"] if noise_rule(c)]
        self.assertEqual(noisy, [])

    def test_older_version_question(self):
        recs = patch_records(ROUTER.route("5.0 신규 캐릭터 누구야?"), KB)
        self.assertEqual({r["entity_name"] for r in recs}, {"카치나", "키니치", "말라니"})


class PatchAnswerTest(unittest.TestCase):
    def setUp(self):
        self.bot = Chatbot(KB)

    def test_new_weapons(self):
        r = self.bot.ask("7.1 신규 무기 뭐야?")
        weapons = {w["name"] for w in KB.weapons}
        self.assertTrue(r["answer"])
        self.assertTrue(set(r["answer"]) <= weapons, r["answer"])
        self.assertIn("신규 무기", r["message"])

    def test_character_all_versions(self):
        r = self.bot.ask("산드로네 패치로 뭐 바뀌었어?")
        self.assertTrue(r["found"])
        self.assertIn("6.7 신규 캐릭터", r["answer"])
        self.assertTrue(any(a.startswith("7.0 ") for a in r["answer"]))

    def test_detail_evidence_for_few_records(self):
        # 기록이 적으면 근거에 바뀌기 전 → 후 본문이 들어간다 (시연 6번: 카즈하 고유 특성 2)
        r = self.bot.ask("7.0에서 카에데하라 카즈하 뭐 바뀌었어?")
        self.assertEqual(r["answer"], ["고유 특성 2"])
        self.assertLessEqual(len(r["evidence"]), PATCH_DETAIL_MAX)
        text = r["evidence"][0]["text"]
        self.assertIn("→", text)
        self.assertIn("별 확산", text)
        self.assertEqual(r["evidence"][0]["doc_id"], "patch:7.0:talents:kaedeharakazuha")

    def test_summary_evidence_for_many_records(self):
        r = self.bot.ask("7.0에서 뭐 바뀌었어?")
        self.assertGreater(len(r["evidence"]), PATCH_DETAIL_MAX)
        self.assertTrue(all("\n" not in e["text"] for e in r["evidence"]))

    def test_not_found_messages(self):
        r = self.bot.ask("7.1에서 사유 뭐 바뀌었어?")
        self.assertFalse(r["found"])
        self.assertIn("7.1 버전 사유의 변경 기록", r["message"])


if __name__ == "__main__":
    unittest.main()
