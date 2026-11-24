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
        vector.item_vector_search = lambda q, k=5, **kw: (_ for _ in ()).throw(RuntimeError("DB 없음"))
        try:
            r = Chatbot(KB).ask("마스터리 올려주는 창 뭐 있어?")
        finally:
            vector.item_vector_search = original
        self.assertFalse(r["found"])

    def test_vector_results_become_evidence(self):
        original = vector.item_vector_search
        vector.item_vector_search = lambda q, k=5, **kw: ["weapon:dragonsbane", "없는:문서", "artifact:wandererstroupe"]
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
        self.assertEqual(vector.item_index_size(), 3)
        vector.set_item_index(None, None, [])
        self.assertEqual(vector.item_index_size(), 0)
        self.assertEqual(vector.item_vector_search("아무 질문"), [])

    def test_load_missing_folder_is_false(self):
        """임베딩 파일이 없는 폴더면 False, 검색 재료는 비워진다 (API는 그대로 뜬다)."""
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            self.assertFalse(vector.load_item_index(d))
        self.assertEqual(vector.item_index_size(), 0)

    def test_chatbot_uses_vector_results(self):
        r = Chatbot(KB).ask("치명타 올려주는 무기 뭐 있어?")
        self.assertTrue(r["found"])
        self.assertEqual(r["evidence"][0]["doc_id"], "weapon:skywardspine")


if __name__ == "__main__":
    unittest.main()


class ItemFilterWireTest(unittest.TestCase):
    """질문에서 뽑은 조건(무기 종류·주옵션·성급)이 벡터 검색에 넘어가는지 (가짜 임베딩 + 실제 메타데이터)."""

    @classmethod
    def setUpClass(cls):
        import json
        import numpy as np
        from core.retrieval import DOCS_PATH
        docs = [json.loads(l) for l in DOCS_PATH.read_text(encoding="utf-8").splitlines() if l.strip()]
        docs = [d for d in docs if d.get("kind") in ("weapon", "artifact")]
        rng = np.random.default_rng(0)
        vecs = rng.normal(size=(len(docs), 8)).astype("float32")
        vecs /= np.linalg.norm(vecs, axis=1, keepdims=True)
        vector.set_item_index(lambda texts: vecs[:1], vecs, [d["doc_id"] for d in docs], [d["metadata"] for d in docs])

    @classmethod
    def tearDownClass(cls):
        vector._clear_item_index()

    def _weapons(self, q):
        ev = retrieve(ROUTER.route(q), KB)
        self.assertTrue(ev, q)
        return [e["data"] for e in ev]

    def test_bow_with_crit(self):
        for w in self._weapons("치명타 올려주는 활 뭐 있어?"):
            self.assertEqual(w["weapon"], "활")
            self.assertIn(w["main_stat"], ("치명타 확률", "치명타 피해"))
            self.assertIn(w["rarity"], ("4성", "5성"))

    def test_spear_synonym_and_rarity(self):
        for w in self._weapons("원충 올려주는 4성 창 뭐 있어?"):
            self.assertEqual((w["weapon"], w["main_stat"], w["rarity"]), ("장병기", "원소 충전 효율", "4성"))

    def test_artifact_question_returns_artifacts(self):
        ev = retrieve(ROUTER.route("보호막 성유물 뭐 있어?"), KB)
        self.assertTrue(ev)
        self.assertTrue(all(e["kind"] == "artifact" for e in ev))


class ItemFiltersMainStatTest(unittest.TestCase):
    """주옵션 필터는 질문이 주옵션을 직접 말할 때만 건다 (11/19 아이템 검색 평가: 효과 질문에서 정답이 빠지던 문제)."""

    def test_main_stat_when_asked_directly(self):
        from core.retrieval import item_filters
        cases = {
            "치명타 올려주는 활 추천해줘": ["치명타 확률", "치명타 피해"],
            "원소 충전 효율 올려 주는 장병기": ["원소 충전 효율"],
            "공격력 높여 주는 대검 뭐 있어?": ["공격력"],
            "주옵션이 원충인 한손검": ["원소 충전 효율"],
        }
        for q, stats in cases.items():
            self.assertEqual(item_filters(q).get("main_stat"), stats, q)

    def test_no_main_stat_for_effect_words(self):
        from core.retrieval import item_filters
        for q, wtype in (("치명타가 발생하면 확률적으로 원소 구슬을 생성하는 한손검은?", "한손검"),
                         ("일반 공격과 강공격으로 부적을 모아 파티의 공격 속도와 공격력을 높이는 대검은?", "양손검"),
                         ("HP 최대치가 증가하고 HP가 절반 미만이면 추가 공격력을 얻는 장병기는?", "장병기")):
            f = item_filters(q)
            self.assertNotIn("main_stat", f, q)
            self.assertEqual(f.get("weapon_type"), wtype, q)     # 무기 종류 필터는 그대로


class ItemFiltersKindTest(unittest.TestCase):
    """질문에 '성유물'·'무기'가 없어도 무기인지 성유물인지 알아본다 (무기 질문에 성유물이 나오던 문제)."""

    def test_kind_from_cue_words(self):
        from core.retrieval import item_filters
        cases = {
            "원소폭발 발동 후 이동 속도와 공격 속도가 증가하는 검은?": "weapon",
            "재련하면 효과가 좋아지는 무기": "weapon",
            "치명타 올려주는 활": "weapon",
            "4세트 효과로 원소폭발 피해가 증가하는 세트는?": "artifact",
            "2세트 효과가 원소 충전 효율 20%인 거 뭐야?": "artifact",
            "HP 기반 캐릭터한테 좋은 세트 추천해줘": "artifact",
            "확산 반응 피해 올려주는 성유물": "artifact",
            # 성유물 질문 속 무기 종류는 착용 캐릭터 설명 (11/23 동우님 평가에서 무기로 잘못 분류)
            "원소 마스터리를 높이고 법구 또는 활을 사용하는 캐릭터의 강공격 피해를 강화하는 성유물 세트는?": "artifact",
            "한손검 캐릭터한테 좋은 4세트 뭐야?": "artifact",
        }
        for q, kind in cases.items():
            self.assertEqual(item_filters(q).get("kind"), kind, q)

    def test_no_kind_when_unclear(self):
        from core.retrieval import item_filters
        for q in ("원소 마스터리 올려주는 거 추천해줘", "성유물이랑 무기 같이 추천해줘"):
            self.assertNotIn("kind", item_filters(q), q)
        self.assertNotEqual(item_filters("검투사 4세트 효과").get("kind"), "weapon")   # 세트 이름 속 '검'

    def test_artifact_question_drops_weapon_type(self):
        from core.retrieval import item_filters
        f = item_filters("원소 마스터리를 높이고 법구 또는 활을 사용하는 캐릭터의 강공격 피해를 강화하는 성유물 세트는?")
        self.assertEqual(f.get("kind"), "artifact")
        self.assertNotIn("weapon_type", f)       # 성유물에는 무기 종류가 없어서 남기면 아무것도 못 찾는다



class ItemAliasTest(unittest.TestCase):
    """커뮤니티 별명·스탯 줄임말 (core/aliases.py ITEM_ALIASES, retrieval.ITEM_MAIN_STATS)"""

    def test_alias_questions_from_item_eval(self):
        # 아이템 평가(60문항)에서 이름 찾기가 놓쳤던 별명 질문
        cases = {
            "안개회광 효과 알려줘": "안개를 가르는 회광",
            "호마 효과 알려줘": "호마의 지팡이",
            "검투사 4세트 효과 뭐야": "검투사의 피날레",
            "추억의 세트 옵션 알려줘": "추억의 시메나와",
            "얼음바람 4세트 뭐야": "얼음바람 속에서 길잃은 용사",
        }
        for q, item in cases.items():
            rr = ROUTER.route(q)
            self.assertEqual((rr.route, rr.item), ("item", item), q)

    def test_risky_words_are_not_aliases(self):
        # 한 글자, 원소 이름, 두 아이템에 걸리는 말은 넣지 않는다
        from core.aliases import ITEM_ALIASES
        for word in ("검", "번", "청", "왕", "얼", "얼음", "반암", "진사", "달빛", "두루마리", "제사"):
            self.assertNotIn(word, ITEM_ALIASES, word)

    def test_element_question_is_not_item(self):
        rr = ROUTER.route("얼음 원소 캐릭터 누구 있어?")
        self.assertNotEqual(rr.route, "item")

    def test_stat_abbreviations(self):
        from core.retrieval import item_filters
        cases = {
            "공퍼 올려주는 한손검": ["공격력"],
            "체퍼 주옵션 무기": ["HP"],
            "방퍼 올려주는 대검": ["방어력"],
            "물피 높여주는 양손검": ["물리 피해 보너스"],
        }
        for q, stat in cases.items():
            self.assertEqual(item_filters(q).get("main_stat"), stat, q)

    def test_base_attack_is_weapon_cue(self):
        from core.retrieval import item_filters
        self.assertEqual(item_filters("기초공 높은 거 뭐 있어?").get("kind"), "weapon")
