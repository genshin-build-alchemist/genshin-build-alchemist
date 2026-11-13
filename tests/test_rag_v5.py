"""rag_v5 테스트: 조건 검색 '조건 모두 만족' + 동의어·줄임 이름 표 + '추천' 아이템 질문 + 빌드 이유 빈말 차단. 실행: python3 -m unittest tests.test_rag_v5 -v"""
import glob
import json
import re
import unittest
from pathlib import Path

from core.aliases import character_aliases
from core.answer import FILTER_MODEL_MAX, LLMAnswerer, clean_build_explain
from core.kb import load_kb
from core.pipeline import Chatbot
from core.retrieval import FILTER_TOP_K, filter_characters, retrieve
from core.router import Router

KB = load_kb()
ROUTER = Router(KB)
EVALSET = Path(__file__).resolve().parent.parent / "data" / "eval" / "questions_info_v2.json"
DATA = json.loads(EVALSET.read_text(encoding="utf-8"))
EVAL_CHARS = set(DATA["eval_characters"])
TRAIN_POOL = [c for c in KB.characters if c["name"] not in EVAL_CHARS]


def pool_for(q):
    return TRAIN_POOL if q["split"] == "train" else KB.characters


def names(rr, pool=None, filter_mode=None):
    return [e["title"] for e in retrieve(rr, KB, pool, filter_mode=filter_mode) if e["kind"] == "character"]


class FilterAllConditionsTest(unittest.TestCase):
    def test_evidence_equals_gold_for_every_filter_question(self):
        # '조건 모두 만족' 근거 = 정답 목록 그대로 (모델은 받아 적기만 하면 된다)
        wrong = []
        for q in DATA["questions"]:
            if q["type"] != "filter":
                continue
            got = names(ROUTER.route(q["question"]), pool_for(q))
            if sorted(got) != sorted(q["gold"]):
                wrong.append(q["id"])
        self.assertEqual(wrong, [], f"근거가 정답과 다른 조건 질문 {len(wrong)}개: {wrong[:5]}")

    def test_every_evidence_matches_all_conditions(self):
        rr = ROUTER.route("몬드 출신 5성 캐릭터 누구 있어?")
        for name in names(rr):
            c = KB.char_by_name[name]
            self.assertEqual((c["region"], c["rarity"]), ("몬드", "5성"))

    def test_any_mode_reproduces_old_retrieval(self):
        # rag ~ rag_v4 결과를 다시 만들 때: 조건이 하나라도 맞으면, 상위 30명
        rr = ROUTER.route("몬드 출신 5성 캐릭터 누구 있어?")
        old = names(rr, filter_mode="any")
        self.assertEqual(len(old), FILTER_TOP_K)
        self.assertTrue(set(names(rr)) <= set(old))

    def test_single_condition_is_not_cut_at_30(self):
        rr = ROUTER.route("5성 캐릭터 누구 있어?")
        self.assertEqual(len(names(rr)), sum(1 for c in KB.characters if c["rarity"] == "5성"))

    def test_bad_mode(self):
        with self.assertRaises(ValueError):
            filter_characters({"rarity": "5성"}, KB.characters, "some")

    def test_long_list_answered_from_data_without_model(self):
        calls = []
        bot = Chatbot(KB, LLMAnswerer(lambda prompt, **kw: calls.append(prompt) or "[]"))
        r = bot.ask("5성 캐릭터 누구 있어?")
        self.assertEqual(calls, [])
        self.assertGreater(len(r["answer"]), FILTER_MODEL_MAX)
        self.assertTrue(all(KB.char_by_name[n]["rarity"] == "5성" for n in r["answer"]))

    def test_short_list_still_uses_model(self):
        calls = []
        bot = Chatbot(KB, LLMAnswerer(lambda prompt, **kw: calls.append(prompt) or '["알베도"]'))
        bot.ask("몬드 출신 5성 캐릭터 누구 있어?")
        self.assertEqual(len(calls), 1)


class AliasTest(unittest.TestCase):
    def test_short_names(self):
        for q, full in (("카즈하 원소 뭐야?", "카에데하라 카즈하"), ("이토 어느 나라 캐릭이야?", "아라타키 이토"),
                        ("라이덴은 무슨 무기 써?", "라이덴 쇼군"), ("미코는 원소가 뭐예요?", "야에 미코")):
            rr = ROUTER.route(q)
            self.assertEqual((rr.route, rr.character), ("lookup", full), q)

    def test_short_name_build(self):
        rr = ROUTER.route("카즈하 성유물 추천해줘")
        self.assertEqual((rr.route, rr.character), ("build", "카에데하라 카즈하"))

    def test_full_name_still_works(self):
        self.assertEqual(ROUTER.route("카에데하라 카즈하 원소 뭐야?").character, "카에데하라 카즈하")

    def test_ambiguous_family_name_is_not_alias(self):
        aliases = character_aliases(KB.char_by_name)
        self.assertNotIn("카미사토", aliases)          # 아야카 / 아야토
        self.assertEqual(aliases["아야카"], "카미사토 아야카")

    def test_alias_not_inside_other_word(self):
        self.assertIsNone(ROUTER.route("사라진 캐릭터 있어?").character)

    def test_no_space_question(self):
        rr = ROUTER.route("에일로이몇성임")
        self.assertEqual((rr.route, rr.character, rr.asked_field), ("lookup", "에일로이", "rarity"))
        self.assertEqual(ROUTER.route("클레어디사람임").asked_field, "region")    # '레어'를 성급으로 보지 않는다

    def test_weapon_synonym(self):
        rr = ROUTER.route("창 쓰는 5성 캐릭터 누구 있어?")
        self.assertEqual((rr.route, rr.conditions), ("filter", {"weapon": "장병기", "rarity": "5성"}))
        self.assertEqual(ROUTER.route("대검 쓰는 4성 캐릭터").conditions, {"weapon": "양손검", "rarity": "4성"})

    def test_character_cue_goes_to_filter(self):
        self.assertEqual(ROUTER.route("활 쓰는 4성 누구 있어?").route, "filter")
        self.assertEqual(ROUTER.route("치명타 올려주는 활 뭐 있어?").route, "item")     # 아이템 질문은 그대로


class RecommendItemTest(unittest.TestCase):
    def test_item_detail_with_recommend_goes_to_item(self):
        for q in ("치명타 올려주는 활 추천해줘", "공격력 올려주는 대검 추천해줘", "원소 마스터리 올려주는 성유물 추천해줘"):
            self.assertEqual(ROUTER.route(q).route, "item", q)

    def test_recommend_without_detail_stays_unknown(self):
        for q in ("성유물 추천해줘", "무기 추천해줘", "활 캐릭터 추천해줘", "몬드 5성 캐릭터 추천해줘"):
            self.assertEqual(ROUTER.route(q).route, "unknown", q)

    def test_build_with_character_unchanged(self):
        self.assertEqual(ROUTER.route("카즈하 성유물 추천해줘").route, "build")


CARDS = [json.loads(Path(f).read_text(encoding="utf-8"))
         for f in sorted(glob.glob(str(Path(__file__).resolve().parent.parent / "data" / "build_cards" / "[!_]*.json")))]
# 어느 캐릭터에나 붙일 수 있는 빈말 (11/11 코랩에서 3B가 쓴 문장과 같은 꼴)
FILLERS = ("{n}의 능력을 최대한 활용할 수 있도록 균형 잡힌 빌드입니다.",
           "{n}는 파티의 원소 피해를 높이는 강력한 서포터라서 이렇게 맞춥니다.",
           "원소폭발과 원소전투 스킬을 효과적으로 활용해 피해를 극대화하기 위해서입니다.",
           "치명타와 공격력을 높여 최적의 성능을 내기 위한 조합입니다.",
           "이 무기와 성유물이 {n}에게 가장 잘 어울립니다.")


class BuildFillerTest(unittest.TestCase):
    def test_filler_falls_back_to_notes_for_every_card(self):
        passed = [(c["character"], f) for c in CARDS for f in FILLERS
                  if clean_build_explain(f.format(n=c["character"]), c["notes"], c["character"]) != c["notes"]]
        self.assertEqual(passed, [])

    def test_sentence_from_card_is_kept(self):
        for c in CARDS:
            first = re.split(r"(?<=\.)\s", c["notes"])[0]
            self.assertEqual(clean_build_explain(first, c["notes"], c["character"]), first, c["character"])

    def test_paraphrase_with_card_words_is_kept(self):
        notes = next(c["notes"] for c in CARDS if c["character"] == "카에데하라 카즈하")
        t = "원소 마스터리를 올리면 확산으로 팀 피해를 키울 수 있어서 마스터리 위주로 맞춘다."
        self.assertEqual(clean_build_explain(t, notes, "카에데하라 카즈하"), t)


if __name__ == "__main__":
    unittest.main()
