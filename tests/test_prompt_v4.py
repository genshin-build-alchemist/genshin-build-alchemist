"""챗봇 rag_v4·rag_v5 프롬프트(core/answer.py)가 평가 노트북 프롬프트와 글자까지 같은지 확인한다.
rag_v4는 예전 조건 검색(filter_mode='any'), rag_v5는 '조건 모두 만족'(챗봇 기본) 근거로 비교한다.

같아야 평가 점수(macro F1 0.845)가 챗봇에도 그대로 적용된다. 노트북 셀 1~4, 7을 GPU 없이 실행해서 비교한다.
데이터(characters_ko.json)나 노트북 프롬프트가 바뀌면 여기서 실패한다 -> core/rag_v4_examples.json을 다시 만든다.
실행: python3 -m unittest tests.test_prompt_v4 -v
"""
import contextlib
import io
import json
import unittest
from pathlib import Path

from core.answer import LLMAnswerer, build_prompt, load_examples_v4
from core.kb import load_kb
from core.retrieval import retrieve
from core.router import Router

ROOT = Path(__file__).resolve().parent.parent
NOTEBOOK = ROOT / "notebooks" / "01_eval_info.ipynb"


def run_notebook_cells():
    """노트북 셀 1~4, 7 실행 (모델 불러오기 없음). 셀 5·8은 결과 파일·출력이 있어 뺀다."""
    nb = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    cells = ["".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code"]
    env = {"__name__": "__main__"}
    with contextlib.redirect_stdout(io.StringIO()):
        for i in (0, 1, 2, 3, 6):
            exec(cells[i], env)
    return env


NB = run_notebook_cells()
KB = load_kb()
ROUTER = Router(KB)


class PromptV4Test(unittest.TestCase):
    def test_examples_file_matches_notebook(self):
        shots = NB["few_shot_v4"]()
        examples = load_examples_v4()
        self.assertEqual([e["question"] for e in examples], [s["question"] for s in shots])
        self.assertEqual([e["answer"] for e in examples], [s["gold"] for s in shots])

    def _diff(self, method, filter_mode):
        diff = []
        for q in NB["questions"]:
            pool_names = {c["name"] for c in NB["pool_for"](q)}
            pool = [c for c in KB.characters if c["name"] in pool_names]
            evidence = retrieve(ROUTER.route(q["question"]), KB, pool, filter_mode=filter_mode)
            if build_prompt(q["question"], evidence, method) != NB["make_prompt"](q, method):
                diff.append(q["id"])
        return diff

    def test_same_prompt_as_notebook_for_all_questions(self):
        diff = self._diff("rag_v4", "any")
        self.assertEqual(diff, [], f"노트북과 다른 rag_v4 프롬프트 {len(diff)}개 (앞 5개): {diff[:5]}")

    def test_same_rag_v5_prompt_as_notebook(self):
        diff = self._diff("rag_v5", None)       # None = 챗봇 기본 (all)
        self.assertEqual(diff, [], f"노트북과 다른 rag_v5 프롬프트 {len(diff)}개 (앞 5개): {diff[:5]}")

    def test_rag_v5_only_changes_filter_evidence(self):
        changed = {q["type"] for q in NB["questions"] if NB["make_prompt"](q, "rag_v4") != NB["make_prompt"](q, "rag_v5")}
        self.assertEqual(changed, {"filter"})

    def test_chatbot_uses_rag_v5_by_default(self):
        self.assertEqual(LLMAnswerer(lambda prompt: "[]").method, "rag_v5")


if __name__ == "__main__":
    unittest.main()
