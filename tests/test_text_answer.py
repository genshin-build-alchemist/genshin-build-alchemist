"""문장 답 모드(패치·아이템) 테스트. 실제 모델 대신 가짜 generate 함수를 쓴다.
실행: python3 -m unittest tests.test_text_answer -v"""
import json
import unittest

from core.answer import (LLMAnswerer, TEXT_MAX_NEW_TOKENS, build_text_prompt, clean_build_explain,
                         load_text_examples, parse_list_answer, parse_text_answer)
from core.kb import load_kb
from core.pipeline import Chatbot

KB = load_kb()


class FakeGenerate:
    """프롬프트와 max_new_tokens를 기록하고 정해진 글을 돌려준다."""

    def __init__(self, reply):
        self.reply = reply
        self.prompts = []
        self.tokens = []

    def __call__(self, prompt, max_new_tokens=None):
        self.prompts.append(prompt)
        self.tokens.append(max_new_tokens)
        return self.reply


class ParseTextTest(unittest.TestCase):
    def test_json_with_commas_inside(self):
        text = '["고유 특성 2: 확산, 별 확산 반응에도 발동한다", "명의 자리 4: 회복량은 같다"]'
        self.assertEqual(parse_text_answer(text), ["고유 특성 2: 확산, 별 확산 반응에도 발동한다",
                                                   "명의 자리 4: 회복량은 같다"])
        # 이름 목록용 파서는 쉼표에서 자르지 않는지 비교용 (JSON이면 같다)
        self.assertEqual(len(parse_list_answer(text)), 2)

    def test_broken_json_falls_back_to_lines(self):
        text = '[\n"고유 특성 2: 별 확산 반응에도 발동한다",\n"명의 자리 4: 별 확산 반응 추가"\n'
        self.assertEqual(parse_text_answer(text), ["고유 특성 2: 별 확산 반응에도 발동한다", "명의 자리 4: 별 확산 반응 추가"])

    def test_cut_off_one_line_json(self):
        # 길이 제한에서 잘려 한 줄 JSON이 깨져도 문장별로 나뉜다
        text = '["7.1 신규 무기는 나비의 우화, 은강검이다", "6.7 신규 캐릭터로 추가됐'
        self.assertEqual(parse_text_answer(text), ["7.1 신규 무기는 나비의 우화, 은강검이다", "6.7 신규 캐릭터로 추가됐"])

    def test_plain_lines_keep_version_numbers(self):
        # 글머리표만 지우고 문장 앞의 버전 숫자는 남긴다
        text = "1. 7.1 신규 무기는 은강검이다\n- 3단계 효과가 바뀌었다"
        self.assertEqual(parse_text_answer(text), ["7.1 신규 무기는 은강검이다", "3단계 효과가 바뀌었다"])

    def test_empty(self):
        self.assertEqual(parse_text_answer("[]"), [])

    def test_at_most_five(self):
        self.assertEqual(len(parse_text_answer(json.dumps([f"문장 {i}" for i in range(8)], ensure_ascii=False))), 5)


class TextPromptTest(unittest.TestCase):
    def test_prompt_has_rules_examples_evidence(self):
        bot = Chatbot(KB)
        ev = [{"text": e["text"]} for e in bot.ask("7.0에서 카에데하라 카즈하 뭐 바뀌었어?")["evidence"]]
        prompt = build_text_prompt("7.0에서 카에데하라 카즈하 뭐 바뀌었어?", ev)
        self.assertIn("JSON 배열", prompt)
        self.assertIn("별 확산", prompt)                 # 근거 본문이 들어감
        self.assertEqual(prompt.count("[예시 근거]"), len(load_text_examples()))
        self.assertTrue(prompt.endswith("답:"))

    def test_examples_do_not_use_demo_character(self):
        raw = json.dumps(load_text_examples(), ensure_ascii=False)
        self.assertNotIn("카즈하", raw)

    def test_long_evidence_is_clipped(self):
        prompt = build_text_prompt("질문", [{"text": "가" * 5000}])
        self.assertIn(" …", prompt)
        self.assertLess(prompt.count("가"), 1000)


class LLMRouteTest(unittest.TestCase):
    def test_patch_uses_text_mode(self):
        gen = FakeGenerate('["고유 특성 2: 확산뿐 아니라 별 확산 반응을 일으켜도 원소 피해 보너스를 제공한다"]')
        bot = Chatbot(KB, LLMAnswerer(gen))
        r = bot.ask("7.0에서 카에데하라 카즈하 뭐 바뀌었어?")
        self.assertEqual(r["answer"], ["고유 특성 2: 확산뿐 아니라 별 확산 반응을 일으켜도 원소 피해 보너스를 제공한다"])
        self.assertEqual(gen.tokens, [TEXT_MAX_NEW_TOKENS])
        self.assertIn("변경 기록에서 찾은 내용:\n- 고유 특성 2", r["message"])

    def test_lookup_still_uses_rag_v4(self):
        gen = FakeGenerate('["바람"]')
        bot = Chatbot(KB, LLMAnswerer(gen))
        r = bot.ask("카에데하라 카즈하의 원소는 뭐야?")
        self.assertEqual(r["answer"], ["바람"])
        self.assertEqual(gen.tokens, [None])            # 이름 목록 경로는 기존 그대로
        self.assertNotIn("문장 하나", gen.prompts[0])

    def test_generate_without_max_new_tokens(self):
        calls = []

        def old_generate(prompt):                       # 노트북의 옛 generate(prompt) 모양
            calls.append(prompt)
            return '["고유 특성 2: 별 확산 반응에도 발동한다"]'

        r = Chatbot(KB, LLMAnswerer(old_generate)).ask("7.0에서 카에데하라 카즈하 뭐 바뀌었어?")
        self.assertEqual(len(calls), 1)
        self.assertEqual(r["answer"], ["고유 특성 2: 별 확산 반응에도 발동한다"])

    def test_no_evidence_no_call(self):
        gen = FakeGenerate('["지어낸 답"]')
        r = Chatbot(KB, LLMAnswerer(gen)).ask("4.0 패치 내용 알려줘")
        self.assertFalse(r["found"])
        self.assertEqual(gen.prompts, [])


class PatchEvidenceCleanTest(unittest.TestCase):
    """코랩 실제 모델 확인(11/10)에서 나온 문제를 막는 테스트."""

    def test_unreadable_lines_removed(self):
        # 산드로네 답에 '{param11:F1P}' 같은 자리표시자가 그대로 나왔다 -> 근거에서 뺀다
        ev = Chatbot(KB).ask("7.0에서 산드로네 원소 폭발 바뀌었어?")["evidence"]
        text = "\n".join(e["text"] for e in ev)
        self.assertNotIn("{param", text)
        self.assertIn("원소 폭발", text)

    def test_weapon_refinements_2_to_5_removed(self):
        # 6.7 무기 질문이 [] 로 나왔다: 재련 1~5단계가 반복돼 근거가 길었다 -> 1단계만 남긴다
        ev = Chatbot(KB).ask("6.7에서 바뀐 무기 알려줘")["evidence"]
        text = "\n".join(e["text"] for e in ev)
        self.assertIn("재련 1단계", text)
        self.assertNotIn("- r2 ", text)
        self.assertNotIn("values #", text)

    def test_burst_line_reaches_prompt(self):
        # 근거를 앞에서부터 자르면 뒤쪽 '원소 폭발' 줄이 잘려 나갔다 -> 줄마다 자른다
        q = "7.0에서 산드로네 원소 폭발 바뀌었어?"
        prompt = build_text_prompt(q, Chatbot(KB).ask(q)["evidence"])
        self.assertIn("원소 폭발 설명", prompt.split("[근거]")[-1])

    def test_short_llm_answer_uses_sentence_message(self):
        # 짧은 문장 답이 '7.0 버전 신규 캐릭터: 7.0 신규 캐릭터는 ...'처럼 겹쳐 보였다
        # (신규 목록은 이제 모델 없이 근거를 묶어 답한다: EmptyPatchAnswerTest)
        gen = FakeGenerate('["7.0 신규 캐릭터는 알료샤, 오데트이다"]')
        r = Chatbot(KB, LLMAnswerer(gen)).ask("7.0 신규 캐릭터 누구야?")
        self.assertEqual(r["message"], "7.0 버전의 변경 기록에서 찾은 내용:\n- 7.0 신규 캐릭터: 알료샤, 오데트")

    def test_mock_patch_message_unchanged(self):
        self.assertEqual(Chatbot(KB).ask("7.0 신규 캐릭터 누구야?")["message"], "7.0 버전 신규 캐릭터: 알료샤, 오데트")


class StopStringTest(unittest.TestCase):
    def test_nested_arrays_are_flattened(self):
        # 코랩에서 모델이 [["문장1"], ["문장2"]]처럼 겹쳐 썼다
        text = '[\n  ["신규 무기: 나비의 우화, 새순"],\n  ["스킬 수정: 오데트(원소 스킬)"]\n]'
        self.assertEqual(parse_text_answer(text), ["신규 무기: 나비의 우화, 새순", "스킬 수정: 오데트(원소 스킬)"])

    def test_text_mode_does_not_stop_at_bracket(self):
        calls = []

        def gen(prompt, max_new_tokens=None, stop_strings=("]",)):
            calls.append(stop_strings)
            return '["7.1 신규 무기: 나비의 우화"]'

        Chatbot(KB, LLMAnswerer(gen)).ask("7.0에서 카에데하라 카즈하 뭐 바뀌었어?")
        Chatbot(KB, LLMAnswerer(gen)).ask("카에데하라 카즈하의 원소는 뭐야?")
        self.assertEqual(calls, [None, ("]",)])     # 문장 답은 끝까지, 이름 목록은 기존대로 ']'에서 멈춤


class GroupPatchLinesTest(unittest.TestCase):
    def test_version_question_is_grouped(self):
        # 3B 모델이 요약 42줄을 직접 묶다가 수정된 무기를 신규 무기에 넣었다 -> 미리 종류별로 묶어 준다
        from core.answer import group_patch_lines
        from core.retrieval import retrieve
        from core.router import Router
        ev = retrieve(Router(KB).route("7.0에서 뭐 바뀌었어?"), KB)
        lines = group_patch_lines(ev)
        new_weapons = next(l for l in lines if l.startswith("7.0 신규 무기:"))
        self.assertNotIn("나른한 새해", new_weapons)            # 수정된 무기는 신규에 없다
        self.assertTrue(any(l.startswith("7.0 무기 수정:") and "나른한 새해(재련 효과)" in l for l in lines))
        self.assertIn("7.0 신규 캐릭터: 알료샤, 오데트", lines)
        self.assertFalse(any("신규 스킬" in l for l in lines))
        prompt = build_text_prompt("7.0에서 뭐 바뀌었어?", ev).split("[근거]")[-1]
        self.assertIn("7.0 무기 수정:", prompt)

    def test_few_records_keep_detail(self):
        from core.retrieval import retrieve
        from core.router import Router
        ev = retrieve(Router(KB).route("7.0에서 카에데하라 카즈하 뭐 바뀌었어?"), KB)
        self.assertIn("별 확산", build_text_prompt("q", ev).split("[근거]")[-1])


class AddedRecordLineTest(unittest.TestCase):
    def test_new_character_uses_summary_line(self):
        # '7.0 신규 캐릭터 누구야?'에 근거가 '[원신 7.0 데이터 변경] 알료샤 - 캐릭터 / 신규 추가됨'으로 들어가
        # 예시('7.1 나비의 우화: 신규 무기 추가')와 모양이 달라 모델이 [] 로 답했다 -> 신규는 늘 한 줄 요약
        ev = Chatbot(KB).ask("7.0 신규 캐릭터 누구야?")["evidence"]
        self.assertEqual([e["text"] for e in ev], ["7.0 알료샤: 신규 캐릭터 추가", "7.0 오데트: 신규 캐릭터 추가"])

    def test_modified_record_keeps_detail(self):
        ev = Chatbot(KB).ask("6.7에서 바뀐 무기 알려줘")["evidence"]
        texts = {e["title"]: e["text"] for e in ev}
        self.assertEqual(texts["초월의 열쇠"], "6.7 초월의 열쇠: 신규 무기 추가")
        self.assertIn("→", texts["암철검"])



class EmptyPatchAnswerTest(unittest.TestCase):
    """11/10 코랩(7.2 데이터): 근거가 1~3줄인 패치 질문 4개에 3B가 []로 답했다."""

    def test_added_list_needs_no_model(self):
        gen = FakeGenerate("[]")
        bot = Chatbot(KB, LLMAnswerer(gen))
        self.assertEqual(bot.ask("7.2 신규 캐릭터 누구야?")["answer"], ["7.2 신규 캐릭터: 미탸, 발레리"])
        self.assertEqual(bot.ask("5.0 신규 캐릭터 누구야?")["answer"], ["5.0 신규 캐릭터: 카치나, 키니치, 말라니"])
        self.assertEqual(bot.ask("7.2 신규 무기 뭐야?")["answer"], ["7.2 신규 무기: 별빛 계시"])
        self.assertEqual(gen.prompts, [])                       # 신규 목록은 모델을 부르지 않는다

    def test_empty_model_answer_falls_back_to_evidence(self):
        r = Chatbot(KB, LLMAnswerer(FakeGenerate("[]"))).ask("5.6에서 엠버 뭐 바뀌었어?")
        self.assertEqual(r["answer"], ["일반 공격 이름: 일반 공격·신궁 → 명사수"])
        self.assertIn("변경 기록에서 찾은 내용", r["message"])

    def test_specific_part_question_keeps_empty_answer(self):
        # '원소 폭발 바뀌었어?'의 []는 '그 부분은 안 바뀜'일 수 있어서 근거로 채우지 않는다
        r = Chatbot(KB, LLMAnswerer(FakeGenerate("[]"))).ask("7.0에서 산드로네 원소 폭발 바뀌었어?")
        self.assertEqual(r["answer"], [])

    def test_model_answer_is_kept_when_not_empty(self):
        r = Chatbot(KB, LLMAnswerer(FakeGenerate('["일반 공격: 이름이 명사수로 바뀌었다"]'))).ask("5.6에서 엠버 뭐 바뀌었어?")
        self.assertEqual(r["answer"], ["일반 공격: 이름이 명사수로 바뀌었다"])


class BuildAnswerTest(unittest.TestCase):
    """11/10 코랩: rag_v4 이름 목록 프롬프트로는 '카즈하 빌드 추천해줘'에 3B가 []를 냈다.
    추천 목록은 카드 그대로, 모델은 카드 설명(notes)으로 '이유' 한 문장만."""
    Q = "카에데하라 카즈하 빌드 추천해줘"
    CARD = KB.card_by_character["카에데하라 카즈하"]

    def test_lists_come_from_card_even_if_model_fails(self):
        r = Chatbot(KB, LLMAnswerer(FakeGenerate("[]"))).ask(self.Q)
        self.assertEqual(r["answer"][0], "추천 무기: " + ", ".join(self.CARD["weapons"]))
        self.assertIn("추천 성유물: 청록색 그림자", r["answer"])
        self.assertEqual(r["answer"][-1], "이유: " + self.CARD["notes"])     # 모델이 실패하면 카드 설명 원문
        self.assertTrue(r["message"].startswith("카에데하라 카즈하 빌드 (GenshinBuilds"))

    def test_model_writes_only_the_reason(self):
        gen = FakeGenerate("원소 마스터리를 올리면 확산으로 팀 피해를 키울 수 있어서 마스터리 위주로 맞춘다.")
        r = Chatbot(KB, LLMAnswerer(gen)).ask(self.Q)
        self.assertEqual(r["answer"][-1], "이유: 원소 마스터리를 올리면 확산으로 팀 피해를 키울 수 있어서 마스터리 위주로 맞춘다.")
        self.assertEqual(len(gen.prompts), 1)
        self.assertIn(self.CARD["notes"], gen.prompts[0])
        self.assertNotIn("오래된 자유의 서약", gen.prompts[0])           # 목록은 모델에게 주지 않는다

    def test_made_up_number_falls_back_to_notes(self):
        notes = "원소 마스터리를 최대한 올린다."
        self.assertEqual(clean_build_explain("원소 마스터리를 1000까지 올리면 피해가 300% 오른다.", notes), notes)
        self.assertEqual(clean_build_explain("", notes), notes)

    def test_section_by_question(self):
        bot = Chatbot(KB, LLMAnswerer(FakeGenerate("[]"), explain_build=False))
        weapons = bot.ask("카에데하라 카즈하 무기 추천해줘")["answer"]
        self.assertTrue(weapons[0].startswith("추천 무기:"))
        self.assertFalse(any(a.startswith("추천 성유물") for a in weapons))
        arts = bot.ask("카에데하라 카즈하 성유물 추천해줘")["answer"]
        self.assertFalse(any(a.startswith("추천 무기") for a in arts))
        self.assertTrue(any(a.startswith("주옵션:") for a in arts))

    def test_no_model_call_when_explain_off(self):
        gen = FakeGenerate("[]")
        Chatbot(KB, LLMAnswerer(gen, explain_build=False)).ask(self.Q)
        self.assertEqual(gen.prompts, [])


if __name__ == "__main__":
    unittest.main()
