"""후처리(core/answer.py의 clean_answer) 테스트: 모델이 쓴 이름·값을 근거의 정확한 글자로 맞추는지 확인한다.
실행: python3 -m unittest tests.test_postprocess -v
"""
import unittest

from core.answer import LLMAnswerer, clean_answer
from core.kb import load_kb
from core.pipeline import Chatbot

EVIDENCE = ["라이덴 쇼군: 원소 번개 / 무기 장병기 / 5성 / 지역 이나즈마",
            "쿠키 시노부: 원소 번개 / 무기 한손검 / 4성 / 지역 이나즈마",
            "카미사토 아야카: 원소 얼음 / 무기 한손검 / 5성 / 지역 이나즈마",
            "카미사토 아야토: 원소 물 / 무기 한손검 / 5성 / 지역 이나즈마"]


class PostprocessTest(unittest.TestCase):
    def test_fix_names(self):
        self.assertEqual(clean_answer(["라이デン 쇼군", "쿠피시노부"], EVIDENCE), ["라이덴 쇼군", "쿠키 시노부"])

    def test_drop_names_not_in_evidence(self):
        self.assertEqual(clean_answer(["베티", "라이덴 쇼군"], EVIDENCE), ["라이덴 쇼군"])

    def test_keep_exact_names(self):
        self.assertEqual(clean_answer(["카미사토 아야카", "카미사토 아야토"], EVIDENCE),
                         ["카미사토 아야카", "카미사토 아야토"])

    def test_values(self):
        self.assertEqual(clean_answer(["번개 원소"], EVIDENCE), ["번개"])
        self.assertEqual(clean_answer(["5"], EVIDENCE), ["5성"])

    def test_no_evidence(self):
        self.assertEqual(clean_answer(["알베도"], []), [])

    def test_chatbot_uses_postprocess(self):
        kb = load_kb()
        raw = '["라이デン 쇼군", "쿠피시노부", "베티"]'
        on = Chatbot(kb, LLMAnswerer(lambda prompt: raw, name="fake"))
        off = Chatbot(kb, LLMAnswerer(lambda prompt: raw, name="fake", postprocess=False))
        question = "이나즈마 출신 번개 원소 캐릭터를 모두 알려줘"
        self.assertEqual(on.ask(question)["answer"], ["라이덴 쇼군", "쿠키 시노부"])
        self.assertEqual(off.ask(question)["answer"], ["라이デン 쇼군", "쿠피시노부", "베티"])


if __name__ == "__main__":
    unittest.main()
