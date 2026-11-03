"""고정 평가셋을 core/ 라우터·검색으로 돌려 보는 테스트.

노트북(notebooks/01_eval_info.ipynb)은 core/ 를 그대로 쓰므로, 라우터·검색을 고친 PR이
평가 결과를 망가뜨리지 않는지 여기서 먼저 확인한다. 실행: python3 -m unittest tests.test_eval_routing -v
"""
import json
import unittest
from collections import Counter
from pathlib import Path

from core.kb import load_kb
from core.retrieval import retrieve
from core.router import Router

EVALSET = Path(__file__).resolve().parent.parent / "data" / "eval" / "questions_info_v1.json"
KB = load_kb()
ROUTER = Router(KB)
DATA = json.loads(EVALSET.read_text(encoding="utf-8"))
EVAL_CHARS = set(DATA["eval_characters"])
TRAIN_POOL = [c for c in KB.characters if c["name"] not in EVAL_CHARS]


def pool_for(q):
    """노트북과 같은 규칙: 학습용 질문은 학습용 캐릭터만, 평가 질문은 전체에서 검색."""
    return TRAIN_POOL if q["split"] == "train" else KB.characters


def retrieved_names(q):
    rr = ROUTER.route(q["question"])
    return rr.route, [e["data"]["name"] for e in retrieve(rr, KB, pool_for(q)) if e["kind"] == "character"]


class EvalSetRoutingTest(unittest.TestCase):
    def test_every_question_routes_to_its_type(self):
        wrong = [(q["id"], q["type"], ROUTER.route(q["question"]).route)
                 for q in DATA["questions"] if ROUTER.route(q["question"]).route != q["type"]]
        self.assertEqual(wrong, [], f"라우터가 틀린 질문 {len(wrong)}개 (앞 5개): {wrong[:5]}")

    def test_retrieval_contains_every_gold_answer(self):
        # 근거를 완벽히 읽으면 만점이 나와야 한다 (= RAG 점수 상한 1.0). 검색이 정답을 놓치면 실패.
        misses = []
        for q in DATA["questions"]:
            route, names = retrieved_names(q)
            if q["type"] == "lookup" and names != [q["character"]]:
                misses.append(q["id"])
            elif q["type"] == "filter" and not set(q["gold"]) <= set(names):
                misses.append(q["id"])
            elif q["type"] == "unknown" and names:
                misses.append(q["id"])
        self.assertEqual(misses, [], f"검색이 정답을 놓친 질문 {len(misses)}개: {misses[:5]}")

    def test_train_questions_never_see_eval_characters(self):
        for q in DATA["questions"]:
            if q["split"] == "train":
                _, names = retrieved_names(q)
                self.assertFalse(set(names) & EVAL_CHARS, q["id"])

    def test_filter_evidence_size(self):
        sizes = [len(retrieved_names(q)[1]) for q in DATA["questions"] if q["type"] == "filter"]
        self.assertLessEqual(max(sizes), 30)
        self.assertEqual(Counter(q["type"] for q in DATA["questions"])["filter"], len(sizes))


if __name__ == "__main__":
    unittest.main()
