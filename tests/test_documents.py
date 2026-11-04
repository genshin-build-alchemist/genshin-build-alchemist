"""문서 전처리 테스트 (P1 기본 단계 1-1). 실행: python3 -m unittest tests.test_documents -v

- 작은 원본 묶음(fixtures/genshin_db_mini)으로 정제 규칙을 검사하고
- 저장소에 들어 있는 결과(data/docs/documents_ko.jsonl)가 캐릭터 데이터와 맞는지 검사한다.
"""
import json
import re
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from core.documents import build_documents, clean, make_report, value_or_none, write_outputs

HERE = Path(__file__).resolve().parent
MINI = HERE / "fixtures" / "genshin_db_mini"
MINI_PATCHES = HERE / "fixtures" / "patch_changes_mini.json"
ROOT = HERE.parent
DOCS = ROOT / "data" / "docs" / "documents_ko.jsonl"
TAG = re.compile(r"<[^>]+>")


class CleanTest(unittest.TestCase):
    def test_clean(self):
        self.assertEqual(clean("<color=#FFD780FF>태양꽃</color>  을\n\n 만든다 "), "태양꽃 을\n만든다")
        self.assertEqual(clean(None), "")
        self.assertEqual(value_or_none("없음"), None)
        self.assertEqual(value_or_none(" 몬드 "), "몬드")


class BuildFromFixtureTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.docs, cls.stats, cls.raw = build_documents(MINI, MINI_PATCHES)
        cls.by_id = {d["doc_id"]: d for d in cls.docs}

    def test_kinds_and_ids(self):
        kinds = Counter(d["kind"] for d in self.docs)
        self.assertEqual(kinds, Counter({"character": 2, "talent": 3, "constellation": 1,
                                         "weapon": 1, "artifact": 1, "patch": 1}))
        self.assertEqual(len(self.by_id), len(self.docs), "doc_id 중복")

    def test_no_tags_or_placeholders(self):
        for d in self.docs:
            self.assertIsNone(TAG.search(d["text"]), d["doc_id"])
            self.assertNotRegex(d["text"], r"\{\d\}", d["doc_id"])
        self.assertEqual(self.stats.tags_removed["talent"], 6)          # 여는 태그 + 닫는 태그

    def test_excluded_fields_not_in_text(self):
        text = "\n".join(d["text"] for d in self.docs)
        for word in ("테스트성우", "모라", "아주 긴 이야기", "ELEMENT_GEO"):
            self.assertNotIn(word, text)

    def test_empty_values(self):
        aether = self.by_id["character:aether"]
        self.assertIn("원소: 정보 없음", aether["text"])
        self.assertIn("지역: 정보 없음", aether["text"])
        self.assertTrue(aether["text"].startswith("아이테르\n"))          # 칭호가 없으면 괄호도 없음
        self.assertIsNone(aether["metadata"]["element"])
        self.assertIsNone(aether["metadata"]["region"])

    def test_character_metadata(self):
        meta = self.by_id["character:albedo"]["metadata"]
        self.assertEqual({k: meta[k] for k in ("name", "element", "weapon", "rarity", "region")},
                         {"name": "알베도", "element": "바위", "weapon": "한손검", "rarity": "5성", "region": "몬드"})

    def test_weapon_uses_filled_r1(self):
        text = self.by_id["weapon:absolution"]["text"]
        self.assertIn("치명타 피해가 20% 증가한다", text)
        self.assertIn("주옵션: 치명타 피해 9.6%", text)

    def test_duplicate_removed(self):
        self.assertEqual(self.stats.duplicates, [("weapon:absolution_dup", "weapon:absolution")])

    def test_talent_and_patch_docs(self):
        self.assertEqual(self.by_id["talent:albedo:combat2"]["metadata"]["slot"], "원소 스킬")
        self.assertIn("알베도 고유 특성 1", self.by_id["talent:albedo:passive1"]["text"])
        self.assertIn("신규 추가됨", self.by_id["patch:7.0:characters:alyosha"]["text"])

    def test_report_and_outputs(self):
        report = make_report(self.docs, self.stats, self.raw)
        for section in ("## 1. 전체 요약", "## 2. 정제 항목", "## 3. 제외한 필드", "## 4. 예시", "## 5. 개인정보"):
            self.assertIn(section, report)
        self.assertNotIn("테스트성우", report)                          # 비교표에도 성우 이름을 쓰지 않음
        with tempfile.TemporaryDirectory() as d:
            out = write_outputs(self.docs, report, d)
            lines = (out / "documents_ko.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), len(self.docs))


@unittest.skipUnless(DOCS.exists(), "data/docs/documents_ko.jsonl 이 없음 (python3 -m core.documents)")
class CommittedDocumentsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.docs = [json.loads(line) for line in DOCS.read_text(encoding="utf-8").splitlines()]

    def test_counts_and_clean(self):
        kinds = Counter(d["kind"] for d in self.docs)
        self.assertEqual(kinds["character"], 124)
        self.assertEqual(kinds["artifact"], 63)
        self.assertEqual(len({d["doc_id"] for d in self.docs}), len(self.docs))
        self.assertFalse([d["doc_id"] for d in self.docs if TAG.search(d["text"])])

    def test_character_docs_match_characters_ko(self):
        # 문서 메타데이터가 평가셋의 정답 출처(characters_ko.json)와 같아야 검색·평가가 어긋나지 않는다
        chars = {c["name"]: c for c in json.loads((ROOT / "data" / "characters_ko.json").read_text(encoding="utf-8"))["characters"]}
        docs = {d["metadata"]["name"]: d["metadata"] for d in self.docs if d["kind"] == "character"}
        self.assertEqual(set(docs), set(chars))
        for name, c in chars.items():
            for f in ("element", "weapon", "rarity", "region"):
                self.assertEqual(docs[name][f], c[f], f"{name} {f}")


if __name__ == "__main__":
    unittest.main()
