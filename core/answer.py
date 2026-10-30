"""답 만들기. 답변기는 두 가지이고, 둘 다 '목록'을 돌려준다 (F1 채점과 같은 형식).

- MockAnswerer : 근거에서 규칙으로 답을 뽑는다. GPU 없이 FastAPI·대시보드를 개발할 때,
                 그리고 'RAG로 낼 수 있는 점수 상한'을 잴 때 쓴다.
- LLMAnswerer  : 오픈소스 LLM(예: 코랩의 Qwen2.5-3B)에 프롬프트를 보내 답을 받는다.
                 generate_fn(prompt) -> 문자열 하나만 넘겨 주면 된다.
"""
import json
import re

from core.kb import slot_label

RULES = ("규칙:\n"
         "- 질문에서 묻는 값(또는 이름)만 JSON 배열로 출력하세요. 예: [\"A\", \"B\"]\n"
         "- 설명이나 다른 말은 쓰지 마세요.\n"
         "- 해당하는 항목을 빠짐없이 모두 적으세요.\n"
         "- 근거에 없는 내용이면 빈 배열 []을 출력하세요.")
RAG_NOTE = "(위 근거에 있는 내용만 사용하세요.)"


def build_prompt(question, evidence, method="rag"):
    """method: baseline(질문만) / rag(규칙 + 근거)."""
    if method == "baseline":
        return f"{question}\nJSON 배열로만 답하세요."
    context = "\n".join(f"- {e['text']}" for e in evidence) or "(관련 근거 없음)"
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
    def __init__(self, generate_fn, name="llm", method="rag"):
        self.generate_fn = generate_fn
        self.name = name
        self.method = method
        self.last_raw = ""          # 마지막 모델 원문 (오답 분석용)

    def answer(self, question, rr, evidence):
        self.last_raw = self.generate_fn(build_prompt(question, evidence, self.method))
        return parse_list_answer(self.last_raw)
