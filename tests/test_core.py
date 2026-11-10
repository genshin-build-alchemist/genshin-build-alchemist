"""core 테스트 (PRD 9장 테스트 시나리오 기반). 실행: python3 -m unittest discover -s tests -v"""
import json
import unittest
from pathlib import Path

from core.answer import LLMAnswerer, build_prompt, parse_list_answer
from core.kb import load_kb, slot_label
from core.pipeline import Chatbot
from core.router import Router
from core.validate import recheck_reasons, validate_card

FIXTURE_CARDS = Path(__file__).parent / "fixtures" / "build_cards"
KB = load_kb()
KB_WITH_CARDS = load_kb(build_card_dir=FIXTURE_CARDS)


class SpyAnswerer:
    """모델이 불렸는지 확인하는 가짜 답변기."""
    name = "spy"
    method = "rag"

    def __init__(self):
        self.calls = 0

    def answer(self, question, rr, evidence):
        self.calls += 1
        return ["지어낸 답"]


class RouterTest(unittest.TestCase):
    def setUp(self):
        self.router = Router(KB)

    def test_five_routes(self):
        cases = {
            "알베도 원소가 뭐야?": "lookup",
            "몬드 출신 5성 캐릭터 누구 있어?": "filter",
            "불원소 활 캐릭터 알려줘": "filter",
            "7.0에서 뭐 바뀌었어?": "patch",
            "이번 패치 신규 캐릭터 누구야?": "patch",
            "알베도 추천 성유물은?": "build",
            "성유물 추천해줘": "unknown",            # 캐릭터가 없으면 빌드 질문도 답할 수 없음
            "원신에서 제일 센 캐릭터는?": "unknown",
            "원소 반응이 뭐야?": "unknown",
        }
        for text, expected in cases.items():
            self.assertEqual(self.router.route(text).route, expected, text)

    def test_one_letter_names_are_not_matched_inside_words(self):
        # 9장: 한 글자 이름(소, 진)처럼 헷갈리는 질문에서도 경로를 맞게 고르는가
        self.assertEqual(self.router.route("소 원소 뭐야?").character, "소")
        self.assertEqual(self.router.route("진은 무슨 무기 써?").character, "진")
        self.assertIsNone(self.router.route("원소 반응이 뭐야?").character)
        self.assertIsNone(self.router.route("진짜 센 캐릭터 누구야?").character)

    def test_lookup_field_and_patch_version(self):
        self.assertEqual(self.router.route("알베도 무기 뭐야?").asked_field, "weapon")
        self.assertEqual(self.router.route("알베도는 몇 성이야?").asked_field, "rarity")
        rr = self.router.route("7.0에서 사유 뭐 바뀌었어?")
        self.assertEqual((rr.route, rr.version, rr.character), ("patch", "7.0", "사유"))


class PipelineTest(unittest.TestCase):
    def setUp(self):
        self.bot = Chatbot(KB)

    def test_response_has_api_fields(self):
        r = self.bot.ask("알베도 원소가 뭐야?")
        for key in ("question", "route", "answer", "message", "evidence", "found",
                    "needs_recheck", "model", "method", "data_version"):
            self.assertIn(key, r)
        self.assertEqual(r["answer"], ["바위"])
        self.assertTrue(r["found"])
        json.dumps(r, ensure_ascii=False)       # API로 그대로 보낼 수 있어야 함

    def test_filter_only_matching_characters(self):
        # 9장: 조건 검색에서 조건에 맞지 않는 캐릭터를 섞지 않는가
        r = self.bot.ask("몬드 출신 5성 캐릭터 누구 있어?")
        for name in r["answer"]:
            c = KB.char_by_name[name]
            self.assertEqual((c["region"], c["rarity"]), ("몬드", "5성"))
        self.assertEqual(len(r["answer"]), sum(1 for c in KB.characters
                                               if c["region"] == "몬드" and c["rarity"] == "5성"))

    def test_patch_questions(self):
        self.assertEqual(self.bot.ask("7.0 신규 캐릭터 누구야?")["answer"], ["알료샤", "오데트"])
        self.assertEqual(self.bot.ask("7.0에서 사유 뭐 바뀌었어?")["answer"], ["고유 특성 1", "명의 자리 4"])

    def test_no_evidence_means_no_model_call(self):
        # 9장: 데이터에 없는 질문에 지어내지 않는가 -> 근거가 없으면 모델을 부르지 않는다
        spy = SpyAnswerer()
        bot = Chatbot(KB, spy)
        for q in ("아르셀리아의 원소는 뭐야?", "원신에서 제일 센 캐릭터는?", "4.0 패치 내용 알려줘",
                  "알베도 추천 성유물은?"):     # 기본 데이터에는 빌드 카드가 없음
            r = bot.ask(q)
            self.assertFalse(r["found"], q)
            self.assertEqual(r["answer"], [], q)
        self.assertEqual(spy.calls, 0)

    def test_patch_version_outside_data(self):
        r = self.bot.ask("4.0 패치 내용 알려줘")
        self.assertFalse(r["found"])
        self.assertIn("수집된 버전", r["message"])


class BuildGuideTest(unittest.TestCase):
    def setUp(self):
        self.bot = Chatbot(KB_WITH_CARDS)

    def test_build_answer_with_source(self):
        # 9장: 답변에 빌드 카드의 출처와 확인 버전이 붙는가
        r = self.bot.ask("알베도 추천 무기는?")
        self.assertEqual(r["route"], "build")
        self.assertEqual(r["answer"], ["사면"])
        card_text = next(e["text"] for e in r["evidence"] if e["kind"] == "build_card")
        self.assertIn("7.1 확인", card_text)
        self.assertFalse(r["needs_recheck"])

    def test_recheck_after_patch(self):
        # 9장: 확인 버전 이후 패치로 바뀐 캐릭터·무기의 가이드에 '재확인 필요'가 표시되는가
        r = self.bot.ask("사유 성유물 추천해줘")
        self.assertTrue(r["needs_recheck"])
        self.assertIn("재확인 필요", r["message"])
        r2 = self.bot.ask("진 추천 무기는?")
        self.assertTrue(r2["needs_recheck"])
        self.assertTrue(any("암철검" in e["text"] for e in r2["evidence"] if e["kind"] == "recheck"))

    def test_no_card_no_answer(self):
        r = self.bot.ask("클레 추천 성유물은?")
        self.assertFalse(r["found"])
        self.assertIn("빌드 가이드가 아직 없어요", r["message"])


class ValidateTest(unittest.TestCase):
    def load(self, name):
        return json.loads((FIXTURE_CARDS / name).read_text(encoding="utf-8"))

    def test_good_card_passes(self):
        self.assertEqual(validate_card(self.load("ok_albedo.json"), KB), [])

    def test_bad_card_problems(self):
        # 9장: 카드 속 무기·성유물 이름이 실제 데이터에 있는가
        problems = " | ".join(validate_card(self.load("bad_names.json"), KB))
        for expected in ("없는무기", "없는 성유물", "무기 종류가 맞지 않음", "source_url", "확인 버전", "hat"):
            self.assertIn(expected, problems)

    def test_recheck_reasons(self):
        self.assertEqual(recheck_reasons(self.load("ok_albedo.json"), KB), [])
        sayu = recheck_reasons(self.load("recheck_sayu.json"), KB)
        self.assertEqual({r["version"] for r in sayu}, {"7.0"})
        jean = recheck_reasons(self.load("recheck_weapon_jean.json"), KB)
        self.assertEqual(jean[0]["target"], "암철검")


class AnswerTest(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(parse_list_answer('답: ["불", "물"]'), ["불", "물"])
        self.assertEqual(parse_list_answer("불, 물"), ["불", "물"])
        self.assertEqual(parse_list_answer("[]"), [])

    def test_llm_answerer_uses_evidence_in_prompt(self):
        seen = {}

        def fake_generate(prompt):
            seen["prompt"] = prompt
            return '["바위"]'

        bot = Chatbot(KB, LLMAnswerer(fake_generate, name="fake-llm"))
        r = bot.ask("알베도 원소가 뭐야?")
        self.assertEqual(r["answer"], ["바위"])
        self.assertIn("알베도: 원소 바위", seen["prompt"])
        self.assertEqual(r["model"], "fake-llm")

    def test_baseline_prompt_has_no_evidence(self):
        self.assertNotIn("[근거]", build_prompt("알베도 원소가 뭐야?", [], method="baseline"))

    def test_slot_labels(self):
        self.assertEqual(slot_label("passive1/description"), "고유 특성 1")
        self.assertEqual(slot_label("c4/description"), "명의 자리 4")
        self.assertEqual(slot_label("combat2/attributes/labels[6]"), "원소 스킬")
        self.assertEqual(slot_label("r1/values[3]"), "재련 1단계")


if __name__ == "__main__":
    unittest.main()
