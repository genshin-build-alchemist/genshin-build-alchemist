"""실제 모델 연결(core/llm.py) 테스트. 진짜 모델은 내려받지 않고 가짜 tokenizer·model로 흐름만 확인한다.
실행: python3 -m unittest tests.test_llm -v
"""
import contextlib
import unittest
from unittest import mock

from core import llm
from core.answer import LLMAnswerer, MockAnswerer


class FakeTensor(list):
    @property
    def shape(self):
        return (1, len(self[0]))


class FakeInputs(dict):
    def to(self, device):
        self["device"] = device
        return self


class FakeTokenizer:
    eos_token_id = 0

    def __init__(self):
        self.messages = None

    def apply_chat_template(self, messages, tokenize, add_generation_prompt):
        self.messages = messages
        return "<chat>" + messages[0]["content"]

    def __call__(self, text, return_tensors):
        return FakeInputs(input_ids=FakeTensor([[1, 2, 3]]))

    def decode(self, tokens, skip_special_tokens):
        return "".join(tokens)


class FakeModel:
    device = "cpu"

    def __init__(self, support_stop_strings=True):
        self.support_stop_strings = support_stop_strings
        self.calls = []

    def generate(self, **kwargs):
        self.calls.append(kwargs)
        if "stop_strings" in kwargs and not self.support_stop_strings:
            raise TypeError("unexpected keyword stop_strings")
        return [[1, 2, 3, '["바위"]']]       # 앞 3개는 입력 토큰, 뒤가 새로 만든 답


class FakeTorch:
    no_grad = staticmethod(contextlib.nullcontext)


class GenerateTest(unittest.TestCase):
    def test_same_settings_as_notebook(self):
        tok, model = FakeTokenizer(), FakeModel()
        generate = llm.make_generate(tok, model, FakeTorch())
        self.assertEqual(generate("알베도 원소?"), '["바위"]')       # 입력 부분은 잘라 내고 답만
        self.assertEqual(tok.messages, [{"role": "user", "content": "알베도 원소?"}])
        call = model.calls[0]
        self.assertFalse(call["do_sample"])                            # 매번 같은 답
        self.assertEqual(call["max_new_tokens"], 160)
        self.assertEqual(call["stop_strings"], ["]"])

    def test_matches_notebook_generate(self):
        # 노트북 셀 6의 generate()를 가짜 모델로 실행해서, 모델에 넘기는 설정이 core와 같은지 비교
        import json
        from pathlib import Path
        nb = json.loads((Path(__file__).resolve().parent.parent / "notebooks" / "01_eval_info.ipynb").read_text(encoding="utf-8"))
        cell = next("".join(c["source"]) for c in nb["cells"] if "def generate(" in "".join(c["source"]))
        nb_model, core_model = FakeModel(), FakeModel()
        env = {"tokenizer": FakeTokenizer(), "model": nb_model, "torch": FakeTorch(), "MAX_NEW_TOKENS": 160}
        exec(cell[cell.index("def generate("):], env)
        core_generate = llm.make_generate(FakeTokenizer(), core_model, FakeTorch())
        self.assertEqual(env["generate"]("질문"), core_generate("질문"))
        strip = lambda call: {k: v for k, v in call.items() if k != "tokenizer"}   # noqa: E731
        self.assertEqual(strip(nb_model.calls[0]), strip(core_model.calls[0]))

    def test_old_transformers_without_stop_strings(self):
        model = FakeModel(support_stop_strings=False)
        generate = llm.make_generate(FakeTokenizer(), model, FakeTorch())
        self.assertEqual(generate("q"), '["바위"]')
        self.assertNotIn("stop_strings", model.calls[-1])


class PickDeviceTest(unittest.TestCase):
    def fake_torch(self, cuda, mps):
        return mock.Mock(cuda=mock.Mock(is_available=lambda: cuda),
                         backends=mock.Mock(mps=mock.Mock(is_available=lambda: mps)))

    def test_order(self):
        self.assertEqual(llm.pick_device(self.fake_torch(True, True)), "cuda")
        self.assertEqual(llm.pick_device(self.fake_torch(False, True)), "mps")
        self.assertEqual(llm.pick_device(self.fake_torch(False, False)), "cpu")
        self.assertEqual(llm.pick_device(self.fake_torch(True, True), "cpu"), "cpu")


class AnswererFromEnvTest(unittest.TestCase):
    def test_default_is_mock(self):
        self.assertIsInstance(llm.answerer_from_env({}), MockAnswerer)
        self.assertIsInstance(llm.answerer_from_env({"GBA_ANSWERER": "MOCK"}), MockAnswerer)

    def test_unknown_value(self):
        with self.assertRaises(ValueError):
            llm.answerer_from_env({"GBA_ANSWERER": "gpt"})

    def test_llm(self):
        with mock.patch.object(llm, "load_generate", return_value=lambda prompt: "[]") as loader:
            a = llm.answerer_from_env({"GBA_ANSWERER": "llm"})
        loader.assert_called_once_with("Qwen/Qwen2.5-3B-Instruct", None, 160)
        self.assertIsInstance(a, LLMAnswerer)
        self.assertEqual((a.name, a.method, a.postprocess), ("Qwen/Qwen2.5-3B-Instruct", "rag_v5", True))

    def test_llm_options(self):
        env = {"GBA_ANSWERER": "llm", "GBA_MODEL": "Qwen/Qwen2.5-1.5B-Instruct", "GBA_DEVICE": "mps",
               "GBA_METHOD": "rag", "GBA_POSTPROCESS": "0", "GBA_MAX_NEW_TOKENS": "64"}
        with mock.patch.object(llm, "load_generate", return_value=lambda prompt: "[]") as loader:
            a = llm.answerer_from_env(env)
        loader.assert_called_once_with("Qwen/Qwen2.5-1.5B-Instruct", "mps", 64)
        self.assertEqual((a.method, a.postprocess), ("rag", False))


if __name__ == "__main__":
    unittest.main()
