"""아이템(무기·성유물) 경로 테스트. 실행: python3 -m unittest tests.test_item_route -v

ItemRouteTest, ItemRetrieveTest : 지금 통과해야 한다 (라우터·검색 연결)
ItemVectorSearchTest            : 한동우(B)가 core/vector.py 를 채운 뒤 @unittest.skip 을 지우고 통과시킨다
"""
import unittest

from core import vector
from core.kb import load_kb
from core.pipeline import Chatbot
from core.retrieval import retrieve
from core.router import Router

KB = load_kb()
ROUTER = Router(KB)


class ItemRouteTest(unittest.TestCase):
    def test_routes(self):
        cases = {
            "용학살창 효과 뭐야?": ("item", "용학살창", "weapon"),
            "청록색 그림자 4세트 효과 알려줘": ("item", "청록색 그림자", "artifact"),
            "마스터리 올려주는 창 뭐 있어?": ("item", None, None),
            "치명타 피해 올려주는 무기 뭐 있어?": ("item", None, None),
            # 기존 경로는 그대로
            "활을 쓰는 4성 캐릭터를 모두 알려줘": ("filter", None, None),
            "카에데하라 카즈하 추천 성유물은?": ("build", None, None),
            "7.0에서 바뀐 무기 알려줘": ("patch", None, None),
            "카덴로우는 어떤 무기를 써?": ("unknown", None, None),     # 모르는 캐릭터의 무기
            "성유물 추천해줘": ("unknown", None, None),               # 누구에게 맞는지 모름
            "원신에서 제일 센 캐릭터는?": ("unknown", None, None),
        }
        for q, (route, item, kind) in cases.items():
            rr = ROUTER.route(q)
            self.assertEqual((rr.route, rr.item, rr.item_kind), (route, item, kind), q)

    def test_question_is_kept_for_vector_search(self):
        self.assertEqual(ROUTER.route("마스터리 올려주는 창 뭐 있어?").question, "마스터리 올려주는 창 뭐 있어?")


class ItemRetrieveTest(unittest.TestCase):
    def setUp(self):
        vector.set_item_index(None, None, [])       # 다른 테스트가 넣은 재료 지우기

    def test_name_question_uses_document(self):
        ev = retrieve(ROUTER.route("용학살창 효과 뭐야?"), KB)
        self.assertEqual([e["doc_id"] for e in ev], ["weapon:dragonsbane"])
        self.assertIn("물 원소 또는 불 원소", ev[0]["text"])    # documents_ko.jsonl 본문 (1재련 효과)

    def test_no_name_without_vector_index_is_not_found(self):
        r = Chatbot(KB).ask("마스터리 올려주는 창 뭐 있어?")
        self.assertEqual(r["route"], "item")
        self.assertFalse(r["found"])
        self.assertIn("무기·성유물", r["message"])

    def test_vector_failure_does_not_crash(self):
        original = vector.item_vector_search
        vector.item_vector_search = lambda q, k=5: (_ for _ in ()).throw(RuntimeError("DB 없음"))
        try:
            r = Chatbot(KB).ask("마스터리 올려주는 창 뭐 있어?")
        finally:
            vector.item_vector_search = original
        self.assertFalse(r["found"])

    def test_vector_results_become_evidence(self):
        original = vector.item_vector_search
        vector.item_vector_search = lambda q, k=5: ["weapon:dragonsbane", "없는:문서", "artifact:wandererstroupe"]
        try:
            ev = retrieve(ROUTER.route("마스터리 올려주는 무기 뭐 있어?"), KB)
        finally:
            vector.item_vector_search = original
        self.assertEqual([e["doc_id"] for e in ev], ["weapon:dragonsbane", "artifact:wandererstroupe"])
        self.assertEqual([e["kind"] for e in ev], ["weapon", "artifact"])


class ItemVectorSearchTest(unittest.TestCase):
    """가짜 임베딩(낱말이 들어 있으면 그 축이 1)으로 검색 순서를 확인한다. 실제 모델 없이 돌아간다."""

    WORDS = ["마스터리", "치명타", "공격력", "물", "불"]

    def encode(self, texts):
        import numpy as np      # numpy는 requirements-llm.txt 쪽이라 이 테스트 안에서만 쓴다
        rows = np.array([[1.0 if w in t else 0.0 for w in self.WORDS] for t in texts]) + 1e-6
        return rows / np.linalg.norm(rows, axis=1, keepdims=True)

    def setUp(self):
        docs = {"weapon:dragonsbane": "원소 마스터리 물 불", "weapon:skywardspine": "치명타 공격력",
                "artifact:wandererstroupe": "원소 마스터리"}
        vector.set_item_index(self.encode, self.encode(list(docs.values())), list(docs))

    def tearDown(self):
        vector.set_item_index(None, None, [])

    def test_top_k_order(self):
        self.assertEqual(vector.item_vector_search("치명타 올려주는 무기", k=1), ["weapon:skywardspine"])
        top2 = vector.item_vector_search("마스터리 올려주는 거", k=2)
        self.assertEqual(set(top2), {"weapon:dragonsbane", "artifact:wandererstroupe"})

    def test_empty_index_returns_empty(self):
        vector.set_item_index(None, None, [])
        self.assertEqual(vector.item_vector_search("아무 질문"), [])

    def test_chatbot_uses_vector_results(self):
        r = Chatbot(KB).ask("치명타 올려주는 무기 뭐 있어?")
        self.assertTrue(r["found"])
        self.assertEqual(r["evidence"][0]["doc_id"], "weapon:skywardspine")


if __name__ == "__main__":
    unittest.main()
