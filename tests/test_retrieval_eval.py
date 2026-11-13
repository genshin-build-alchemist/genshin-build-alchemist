"""검색 평가(정답 근거 문서, Hit@k) 테스트. 실행: python3 -m unittest tests.test_retrieval_eval -v"""
import hashlib
import json
import unittest
from pathlib import Path

from core.kb import load_kb
from core.retrieval_eval import (EVIDENCE, STYLE_DEV, STYLE_EVAL, allowed_doc_ids, build_evidence, by_note,
                                 csv_questions, dev_questions, eval_questions, evaluate_retrieval,
                                 gold_doc_ids_for_target, keyword_search_fn, load_documents, load_evalset, score)

ROOT = Path(__file__).resolve().parent.parent
NOTEBOOK = ROOT / "notebooks" / "01_eval_info.ipynb"
KB = load_kb()
DATA = load_evalset()
DOCS = load_documents()
DOC_IDS = {d["doc_id"] for d in DOCS}
EVAL_NAMES = set(DATA["eval_characters"])


class EvidenceFileTest(unittest.TestCase):
    def test_file_is_up_to_date(self):
        saved = json.loads(EVIDENCE.read_text(encoding="utf-8"))
        self.assertEqual(saved, build_evidence(DATA, KB),
                         "evidence_info_v2.json이 코드와 다름: python3 -m core.retrieval_eval --write")
        self.assertEqual(saved["questions_sha256"], DATA["sha256"])

    def test_every_question_has_valid_evidence(self):
        ev = build_evidence(DATA, KB)["evidence"]
        self.assertEqual(set(ev), {q["id"] for q in DATA["questions"]})
        for q in DATA["questions"]:
            docs = ev[q["id"]]
            self.assertTrue(set(docs) <= DOC_IDS, f"{q['id']}: 문서 파일에 없는 doc_id {docs}")
            expected = {"lookup": 1, "filter": len(q["gold"]), "unknown": 0}[q["type"]]
            self.assertEqual(len(docs), expected, q["id"])

    def test_examples(self):
        ev = build_evidence(DATA, KB)["evidence"]
        self.assertEqual(ev["lookup_weapon_aether"], ["character:aether"])
        self.assertEqual(ev["unknown_00"], [])
        self.assertEqual(len(ev["filter_element-물_rarity-4성"]), 4)


class DevSetTest(unittest.TestCase):
    def test_same_as_notebook(self):
        # 노트북 셀의 few_shot_examples / build_dev_set 코드를 그대로 실행해서 같은 60문항인지 확인
        nb = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
        src = "".join("".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code")
        funcs = []
        for name in ("def few_shot_examples", "def build_dev_set"):
            start = src.index(name)
            funcs.append(src[start:src.index("\n\n\n", start)])
        env = {"hashlib": hashlib, "questions": DATA["questions"]}
        exec("\n\n".join(funcs), env)
        self.assertEqual([q["id"] for q in env["build_dev_set"]()], [q["id"] for q in dev_questions(DATA)])

    def test_shape(self):
        dev = dev_questions(DATA)
        self.assertEqual(len(dev), 60)
        self.assertTrue(all(q["split"] == "train" for q in dev))
        self.assertEqual(sum(q["type"] == "filter" for q in dev), 16)
        self.assertEqual(sum(q["type"] == "unknown" for q in dev), 4)
        self.assertEqual(len(eval_questions(DATA)), 121)


class ScoreTest(unittest.TestCase):
    def test_lookup(self):
        s = score(["b", "a", "c"], ["a"], ks=(1, 3))
        self.assertEqual((s["hit@1"], s["hit@3"], s["recall@3"], s["all@3"]), (0.0, 1.0, 1.0, 1.0))

    def test_filter_and_duplicates(self):
        # 같은 문서의 청크가 여러 번 나오면 처음 것만 센다
        s = score(["a", "a", "x", "b", "c"], ["a", "b", "c"], ks=(2, 3, 5))
        self.assertEqual(s["recall@2"], 1 / 3)
        self.assertEqual(s["recall@3"], 2 / 3)
        self.assertEqual(s["all@5"], 1.0)

    def test_no_gold(self):
        self.assertIsNone(score(["a"], []))


class PoolTest(unittest.TestCase):
    def test_train_question_excludes_eval_characters(self):
        q = next(q for q in DATA["questions"] if q["split"] == "train")
        pool = allowed_doc_ids(q, DOCS, EVAL_NAMES)
        eval_docs = {d["doc_id"] for d in DOCS if d["metadata"].get("name") in EVAL_NAMES}
        self.assertTrue(eval_docs)
        self.assertFalse(pool & eval_docs)
        self.assertIn("weapon:absolution", pool)

    def test_eval_question_sees_everything(self):
        q = next(q for q in DATA["questions"] if q["split"] == "eval")
        self.assertIsNone(allowed_doc_ids(q, DOCS, EVAL_NAMES))

    def test_search_outside_pool_is_rejected(self):
        eval_doc = next(d["doc_id"] for d in DOCS if d["metadata"].get("name") in EVAL_NAMES)
        with self.assertRaises(ValueError):
            evaluate_retrieval(lambda question, pool: [eval_doc], dev_questions(DATA)[:5], kb=KB, docs=DOCS)
        with self.assertRaises(ValueError):
            evaluate_retrieval(lambda question, pool: ["없는:문서"], eval_questions(DATA)[:1], kb=KB, docs=DOCS)


class TargetTest(unittest.TestCase):
    def test_targets(self):
        self.assertEqual(gold_doc_ids_for_target("알베도/원소", KB), ["character:albedo"])
        self.assertEqual(gold_doc_ids_for_target("", KB), [])
        mond5 = gold_doc_ids_for_target("지역=몬드, 성급=5성", KB)
        self.assertIn("character:albedo", mond5)
        with self.assertRaises(ValueError):
            gold_doc_ids_for_target("없는캐릭터/원소", KB)

    def test_style_csv(self):
        dev = csv_questions(STYLE_DEV, KB)
        self.assertEqual(len(dev), 1748)
        self.assertTrue(all(q["split"] == "train" and len(q["gold_docs"]) == 1 for q in dev))
        self.assertTrue(all(q["split"] == "eval" for q in csv_questions(STYLE_EVAL, KB)))


class KeywordBaselineTest(unittest.TestCase):
    """키워드 검색 기준점. 템플릿 질문은 만점. 말투 변형: rag_v5 별명 표·띄어쓰기 처리 전 0.681 -> 후 0.95"""

    def test_template_questions(self):
        search = keyword_search_fn(KB)
        for qs in (dev_questions(DATA), eval_questions(DATA)):
            r = evaluate_retrieval(search, qs, kb=KB, docs=DOCS)
            self.assertEqual(r["by_type"]["lookup"]["hit@1"], 1.0)
            self.assertEqual(r["by_type"]["filter"]["all@30"], 1.0)

    def test_style_questions(self):
        r = evaluate_retrieval(keyword_search_fn(KB), csv_questions(STYLE_DEV, KB), kb=KB, docs=DOCS)
        notes = by_note(r)
        self.assertGreater(notes["띄어쓰기 없음"], 0.75)     # rag_v5 전에는 0.0 (별명·한 글자 이름은 아직 못 받음)
        self.assertEqual(notes["존댓말"], 1.0)
        self.assertEqual(notes["짧은 반말"], 1.0)


if __name__ == "__main__":
    unittest.main()
