"""답 만들기. 답변기는 두 가지이고, 둘 다 '목록'을 돌려준다 (F1 채점과 같은 형식).

- MockAnswerer : 근거에서 규칙으로 답을 뽑는다. GPU 없이 FastAPI·대시보드를 개발할 때,
                 그리고 'RAG로 낼 수 있는 점수 상한'을 잴 때 쓴다.
- LLMAnswerer  : 오픈소스 LLM(예: 코랩의 Qwen2.5-3B)에 프롬프트를 보내 답을 받는다.
                 generate_fn(prompt) -> 문자열 하나만 넘겨 주면 된다.
"""
import json
import re
from pathlib import Path

from core.kb import slot_label

# TODO(C) 프롬프트 개선. 비교는 노트북 셀 10-1(DEV 60문항)로만 한다. 끝나면 [ ] -> [x]
#  기준점: dev_rag_v3 macro F1 0.486 (lookup 0.550, filter 0.199, 빈 답 24개)
#  1. [x] DEV 오답 보기: 셀 11에서 show_failures("dev_rag_v3", "lookup"), show_failures("dev_rag_v3", "filter")
#  2. [x] 빈 답 줄이기: 근거가 있는데 [] 로 답한 문항 (빈 답 24개 중 unknown 4개를 빼면 약 20개)
#         -> rag_v4: DEV 빈 답 24 -> 5 (4개는 unknown 정답), lookup 0.550 -> 1.000
#  3. [ ] filter 정밀도 올리기: 조건에 안 맞는 이름까지 답함 (micro P 0.24)
#         -> rag_v4에서도 미해결 (DEV filter 0.199 -> 0.302, 평가 0.309 -> 0.288). 근거 문서가 평균 29개
#  4. [x] 새 프롬프트(rag_v4 ...)는 노트북 셀 7의 METHODS와 make_prompt()에 추가 -> 셀 10-1의 DEV_METHODS에 넣어 비교
#         -> rag_v4: DEV macro F1 0.486 -> 0.814
#  5. [x] DEV에서 가장 좋은 1개만 셀 10에서 평가 115문항으로 한 번 돌리기 (평가 결과를 보고 다시 고치지 않는다)
#         -> rag_v4: 평가 115문항 macro F1 0.563 -> 0.845 (results/info14_rag_v4.json)
#  6. [x] 고른 프롬프트를 아래 build_prompt()에 옮기기 (챗봇 API도 같은 프롬프트를 쓰게)
#         -> method="rag_v4", LLMAnswerer 기본값도 rag_v4
#  7. [ ] (강사님 답변 후) LoRA: 노트북 셀 13의 학습 질문으로 02_finetune_data, 03_lora_train
#  규칙: 평가 115문항, 사람 질문, style_questions_v1.csv 결과는 프롬프트 고를 때 보지 않는다

RULES = ("규칙:\n"
         "- 질문에서 묻는 값(또는 이름)만 JSON 배열로 출력하세요. 예: [\"A\", \"B\"]\n"
         "- 설명이나 다른 말은 쓰지 마세요.\n"
         "- 해당하는 항목을 빠짐없이 모두 적으세요.\n"
         "- 근거에 없는 내용이면 빈 배열 []을 출력하세요.")
RAG_NOTE = "(위 근거에 있는 내용만 사용하세요.)"

# rag_v4: 평가 노트북(01_eval_info.ipynb 셀 7)에서 고른 프롬프트. 글자 하나까지 같아야 점수가 그대로 옮겨진다.
RULES_V4 = ("규칙:\n"
            "- 질문에서 묻는 값(또는 캐릭터 이름)만 JSON 배열로 출력하세요. 예: [\"A\", \"B\"]\n"
            "- 설명이나 다른 말은 쓰지 마세요.\n"
            "- 해당하는 항목을 빠짐없이 모두 적으세요.\n"
            "- 모르는 캐릭터이거나 해당하는 항목이 없으면 빈 배열 []을 출력하세요.\n"
            "- 근거의 '5성', '4성'이 성급이고, '지역'이 출신 지역입니다.\n"
            "- 조건이 여러 개인 질문은 조건을 모두 만족하는 캐릭터만 고르세요.")
RAG_NOTE_V4 = "(위 근거에 있는 내용만 사용하세요. 근거에 없는 캐릭터면 []을 출력하세요.)"
EXAMPLES_V4_PATH = Path(__file__).with_name("rag_v4_examples.json")


def load_examples_v4():
    """rag_v4 예시 5개 (질문, 정답, 근거 문장). 노트북의 few_shot_v4()와 같은 내용."""
    with open(EXAMPLES_V4_PATH, encoding="utf-8") as f:
        return json.load(f)["examples"]


def context_text(lines):
    return "\n".join(f"- {line}" for line in lines) or "(관련 근거 없음)"


def examples_block_v4():
    blocks = []
    for ex in load_examples_v4():
        answer = json.dumps(ex["answer"], ensure_ascii=False)
        blocks.append(f"[예시 근거]\n{context_text(ex['evidence'])}\n예시 질문: {ex['question']}\n예시 답: {answer}")
    return "\n\n".join(blocks)


def build_prompt(question, evidence, method="rag_v4"):
    """method: baseline(질문만) / rag(규칙 + 근거) / rag_v4(규칙 + 근거가 붙은 예시 5개 + 근거, 기본값)."""
    if method == "baseline":
        return f"{question}\nJSON 배열로만 답하세요."
    context = context_text([e["text"] for e in evidence])
    if method == "rag_v4":
        return "\n\n".join([RULES_V4, examples_block_v4(),
                            f"[근거]\n{context}\n{RAG_NOTE_V4}",
                            f"[질문]\n{question}\n답:"])
    return f"{RULES}\n\n[근거]\n{context}\n{RAG_NOTE}\n\n[질문]\n{question}\n답:"


def parse_list_answer(text):
    """모델 글에서 목록을 뽑는다. JSON 배열이면 그대로, 아니면 쉼표/줄바꿈으로 나눈다."""
    m = re.search(r"\[.*?\]", text, re.S)
    if m:
        try:
            return [str(x).strip() for x in json.loads(m.group(0)) if str(x).strip()]
        except json.JSONDecodeError:
            pass
    parts = re.split(r"[,\n、]", text)
    return [re.sub(r"^[\-\*\d\.\s]+", "", p).strip() for p in parts if p.strip()]


class MockAnswerer:
    name = "mock-rule"

    def answer(self, question, rr, evidence):
        data = [e["data"] for e in evidence]
        if rr.route == "lookup":
            c = data[0]
            if rr.asked_field:
                return [c[rr.asked_field]] if c[rr.asked_field] else []
            return [v for v in (c["element"], c["weapon"], c["rarity"], c["region"]) if v]

        if rr.route == "filter":
            return [c["name"] for c in data if all(c[f] == v for f, v in rr.conditions.items())]

        if rr.route == "patch":
            records = [e["data"] for e in evidence if e["kind"] == "patch"]
            if rr.character:   # 한 캐릭터의 바뀐 부분
                parts = set()
                for r in records:
                    if r["change_type"] == "modified":
                        parts |= {lbl for lbl in (slot_label(c["field"]) for c in r["changes"]) if lbl}
                return sorted(parts)
            if any(w in question for w in ("신규", "새로", "추가")):
                return [r["entity_name"] for r in records
                        if r["change_type"] == "added" and r["folder"] == "characters"]
            return sorted({r["entity_name"] for r in records
                           if r["change_type"] == "modified" and r["folder"] in ("talents", "constellations")})

        if rr.route == "build":
            card = next(e["data"] for e in evidence if e["kind"] == "build_card")
            if "무기" in question and "성유물" not in question:
                return list(card.get("weapons", []))
            if any(w in question for w in ("주옵", "주스탯")):
                return [v for v in (card.get("main_stats") or {}).values() if v]
            if "성유물" in question:
                return list(card.get("artifact_sets", []))
            return list(card.get("weapons", [])) + list(card.get("artifact_sets", []))
        return []


class LLMAnswerer:
    def __init__(self, generate_fn, name="llm", method="rag_v4"):
        self.generate_fn = generate_fn
        self.name = name
        self.method = method
        self.last_raw = ""          # 마지막 모델 원문 (오답 분석용)

    def answer(self, question, rr, evidence):
        self.last_raw = self.generate_fn(build_prompt(question, evidence, self.method))
        return parse_list_answer(self.last_raw)
