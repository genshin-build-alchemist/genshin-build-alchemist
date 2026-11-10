"""고정 평가셋 검사: 지문이 그대로인지, 학습/평가 분리가 지켜졌는지. 실행: python3 -m unittest tests.test_evalset -v"""
import hashlib
import json
import re
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVALSET = ROOT / "data" / "eval" / "questions_info_v2.json"
NOTEBOOK = ROOT / "notebooks" / "01_eval_info.ipynb"
CHARACTERS = ROOT / "data" / "characters_ko.json"

# 고정본 지문. 바꾸려면 data/eval/README.md의 '새 버전' 절차를 따른다.
EXPECTED_SHA256 = "5677082a29dca568cb6222c092061ff0c27983c7cc3d8a03fcd0901736c61ad7"


def questions_sha256(qs):
    """노트북의 questions_sha256과 같은 계산."""
    text = json.dumps(qs, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class FrozenEvalSetTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(EVALSET.read_text(encoding="utf-8"))
        cls.questions = cls.data["questions"]
        cls.eval_chars = set(cls.data["eval_characters"])

    def test_fingerprint_unchanged(self):
        sha = questions_sha256(self.questions)
        self.assertEqual(sha, EXPECTED_SHA256, "고정 평가셋이 바뀌었습니다. 손으로 고쳤다면 되돌리세요.")
        self.assertEqual(self.data["sha256"], EXPECTED_SHA256)
        self.assertEqual(self.data["dataset_version"], "info_v2")

    def test_notebook_expects_same_fingerprint(self):
        source = "".join("".join(c["source"]) for c in json.loads(NOTEBOOK.read_text(encoding="utf-8"))["cells"])
        found = re.findall(r'EXPECTED_SHA256 = "([0-9a-f]{64})"', source)
        self.assertEqual(found, [EXPECTED_SHA256], "노트북의 EXPECTED_SHA256이 고정본 지문과 다릅니다.")

    def test_counts(self):
        count = Counter((q["split"], q["type"]) for q in self.questions)
        self.assertEqual(len(self.questions), 628)
        self.assertEqual(sum(v for (sp, _), v in count.items() if sp == "eval"), 121)
        self.assertEqual({f"{sp}_{t}": count[(sp, t)] for sp in ("train", "eval")
                          for t in ("lookup", "filter", "unknown")}, self.data["counts"])
        self.assertEqual(len(self.eval_chars), 23)

    def test_ids_unique_and_fields_present(self):
        ids = [q["id"] for q in self.questions]
        self.assertEqual(len(ids), len(set(ids)))
        for q in self.questions:
            for key in ("id", "type", "field", "question", "gold", "split"):
                self.assertIn(key, q, q["id"])
            self.assertIn(q["split"], ("train", "eval"))
            if q["type"] == "unknown":
                self.assertEqual(q["gold"], [], q["id"])

    def test_no_eval_character_in_train(self):
        # 학습용 질문(예시·파인튜닝 데이터 재료)의 캐릭터와 정답에 평가용 캐릭터가 나오면 안 된다
        for q in self.questions:
            if q["split"] != "train":
                continue
            self.assertNotIn(q.get("character"), self.eval_chars, q["id"])
            self.assertFalse(set(q["gold"]) & self.eval_chars, q["id"])

    def test_eval_lookup_uses_only_eval_characters(self):
        # 캐릭터 단위 분리: 평가용 lookup 질문은 평가용 캐릭터만 묻는다
        for q in self.questions:
            if q["split"] == "eval" and q["type"] == "lookup":
                self.assertIn(q["character"], self.eval_chars, q["id"])

    def test_gold_matches_character_data(self):
        # 정답이 현재 캐릭터 데이터와 맞는지 (데이터를 갱신했는데 평가셋을 안 바꾼 경우를 잡는다)
        chars = {c["name"]: c for c in json.loads(CHARACTERS.read_text(encoding="utf-8"))["characters"]}
        for q in self.questions:
            if q["type"] == "lookup":
                self.assertEqual(q["gold"], [chars[q["character"]][q["field"]]], q["id"])


if __name__ == "__main__":
    unittest.main()
