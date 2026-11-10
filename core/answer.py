"""답 만들기. 답변기는 두 가지이고, 둘 다 '목록'을 돌려준다 (F1 채점과 같은 형식).

- MockAnswerer : 근거에서 규칙으로 답을 뽑는다. GPU 없이 FastAPI·대시보드를 개발할 때,
                 그리고 'RAG로 낼 수 있는 점수 상한'을 잴 때 쓴다.
- LLMAnswerer  : 오픈소스 LLM(예: 코랩의 Qwen2.5-3B)에 프롬프트를 보내 답을 받는다.
                 generate_fn(prompt) -> 문자열 하나만 넘겨 주면 된다.

답 모양은 경로마다 다르다
- 이름·값 목록 (lookup, filter, build): rag_v4 프롬프트. 예: ["바람"], ["알베도", "진"]
- 짧은 문장 목록 (patch, item)         : 문장 답 프롬프트(build_text_prompt). 예: ["고유 특성 2: ..."]
"""
import difflib
import json
import re
from pathlib import Path

from core.kb import slot_label

# TODO(C) 프롬프트 개선. 비교는 노트북 셀 10-1(DEV 60문항)로만 한다. 끝나면 [ ] -> [x]
#  기준점: dev_rag_v3 macro F1 0.486 (lookup 0.550, filter 0.199, 빈 답 24개)
#  1. [x] DEV 오답 보기: 셀 11에서 show_failures("dev_rag_v3", "lookup"), show_failures("dev_rag_v3", "filter")
#  2. [x] 빈 답 줄이기: 근거가 있는데 [] 로 답한 문항 (빈 답 24개 중 unknown 4개를 빼면 약 20개)
#         -> rag_v4: DEV 빈 답 24 -> 5 (4개는 unknown 정답), lookup 0.550 -> 1.000
#  3. [-] filter 정밀도 올리기: 조건에 안 맞는 이름까지 답함 (micro P 0.24)
#         -> rag_v4에서도 미해결 (DEV filter 0.199 -> 0.302, 평가 0.309 -> 0.288). 근거 문서가 평균 29개
#         -> 프롬프트가 아니라 검색 문제라 B로 넘김 (TODO(B) 3번: 조건을 모두 만족하는 캐릭터만 근거로)
#  4. [x] 새 프롬프트(rag_v4 ...)는 노트북 셀 7의 METHODS와 make_prompt()에 추가 -> 셀 10-1의 DEV_METHODS에 넣어 비교
#         -> rag_v4: DEV macro F1 0.486 -> 0.814
#  5. [x] DEV에서 가장 좋은 1개만 셀 10에서 평가 115문항으로 한 번 돌리기 (평가 결과를 보고 다시 고치지 않는다)
#         -> rag_v4: 평가 115문항 macro F1 0.563 -> 0.845 (results/info14_rag_v4.json)
#  6. [x] 고른 프롬프트를 아래 build_prompt()에 옮기기 (챗봇 API도 같은 프롬프트를 쓰게)
#         -> method="rag_v4", LLMAnswerer 기본값도 rag_v4
#  7. [-] LoRA: 하지 않기로 함 (팀 결정)
#  ── 다음 할 일 ──
#  8. [ ] 일본어 섞임 후처리: 모델 답의 이름을 근거에 있는 이름 중 가장 비슷한 것으로 맞추기 ("라이デン 쇼군" -> "라이덴 쇼군")
#         노트북 파싱 단계에 넣어 DEV로 먼저 확인 -> 효과 있으면 아래 parse_list_answer() 다음 단계로 챗봇에도 적용
#  9. [ ] 모델 비교 (02_model_compare): rag_v4 프롬프트 고정, 모델만 바꿔 DEV로 macro F1·평균 응답 시간 비교
#         예: Qwen2.5-1.5B(빠름) / Qwen2.5-7B 4bit(정확) / 한국어 모델 1개. 결과는 드라이브 results/ JSON
#         -> 보고서에 '왜 Qwen2.5-3B를 골랐는지' 근거로 쓴다
#  10. [ ] B가 조건 검색을 고치면 rag_v5(rag_v4 프롬프트 + 새 검색)를 DEV로 확인 -> 좋으면 평가 115문항 한 번
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


# ── 문장 답 모드 (patch, item) ─────────────────────────────────
# rag_v4는 이름·값만 뽑는 프롬프트라 "뭐 바뀌었어?", "효과 뭐야?" 같은 질문에 빈 답을 낸다.
# 이 경로들은 근거를 요약한 짧은 문장 목록으로 답한다. 목록 형식은 그대로라 API·화면은 바뀌지 않는다.
TEXT_ROUTES = ("patch", "item")
TEXT_MAX_NEW_TOKENS = 320          # 문장 5개까지 (이름 목록용 160으로는 잘린다)
TEXT_TOTAL_CHARS = 3600            # 근거 전체 글자 수 상한. 근거가 적으면 1개당 더 길게 넣는다
TEXT_LINE_CHARS = 300              # 근거 한 줄 상한 (스킬 설명 한 줄이 600자를 넘기도 한다)
TEXT_RULES = ("규칙:\n"
              "- 아래 근거만 보고 질문에 답하세요. 근거에 없는 내용은 쓰지 마세요.\n"
              "- 답은 JSON 배열로 출력하고, 각 항목은 짧은 한국어 문장 하나로 쓰세요. 예: [\"A: B로 바뀌었다\"]\n"
              "- 항목은 최대 5개입니다. 근거가 많으면 질문과 가장 관련 있는 것부터 쓰세요.\n"
              "- 이름, 숫자, 퍼센트는 근거에 적힌 그대로 쓰세요.\n"
              "- 바뀐 내용은 '→' 앞(전)과 뒤(후)를 비교해서 무엇이 달라졌는지만 쓰세요. 근거 문장을 그대로 베끼지 마세요.\n"
              "- 각 항목 앞에 바뀐 부분 이름을 붙이세요. 예: 원소 폭발, 명의 자리 1, 재련 1단계\n"
              "- 근거가 한 줄 요약 목록이면 신규 캐릭터, 신규 무기, 수정된 것처럼 종류별로 묶어 쓰세요.\n"
              "- 근거에 질문의 답이 없으면 빈 배열 []을 출력하세요.\n"
              "- 문장 안에 큰따옴표(\")는 쓰지 마세요.")
TEXT_EXAMPLES_PATH = Path(__file__).with_name("text_examples.json")
QUOTED_ITEM = re.compile(r'"((?:[^"\\]|\\.)*)"|"([^"]+)$')   # "문장" 또는 끝에서 잘린 "문장…
BULLET = re.compile(r"^\s*(?:[-*•]|\d+[.)](?!\d))\s*")       # "- ", "1. ", "2) " (7.1은 건드리지 않음)


def load_text_examples():
    with open(TEXT_EXAMPLES_PATH, encoding="utf-8") as f:
        return json.load(f)["examples"]


def _cut(text, limit):
    return text if len(text) <= limit else text[:limit] + " …(생략)"


def _clip(text, limit):
    """근거 1개 줄이기: 긴 줄은 줄마다 자르고(뒤쪽 줄이 통째로 잘려 나가지 않게), 전체도 limit까지."""
    lines = [_cut(line, TEXT_LINE_CHARS) for line in str(text).split("\n")]
    return _cut("\n".join(lines), limit)


def build_text_prompt(question, evidence):
    """문장 답 프롬프트: 규칙 + 예시 4개 + 근거 + 질문."""
    blocks = [TEXT_RULES]
    for ex in load_text_examples():
        answer = json.dumps(ex["answer"], ensure_ascii=False)
        blocks.append(f"[예시 근거]\n{context_text(ex['evidence'])}\n예시 질문: {ex['question']}\n예시 답: {answer}")
    per = max(500, min(1800, TEXT_TOTAL_CHARS // max(len(evidence), 1)))   # 근거 1개당 글자 수
    context = context_text([_clip(e["text"], per) for e in evidence])
    blocks.append(f"[근거]\n{context}\n(위 근거에 있는 내용만 사용하세요.)")
    blocks.append(f"[질문]\n{question}\n답:")
    return "\n\n".join(blocks)


def parse_text_answer(text):
    """모델 글 -> 문장 목록. 문장 안의 쉼표에서 자르지 않는다 (parse_list_answer와 다른 점)."""
    start, end = text.find("["), text.rfind("]")
    if start != -1 and end > start:
        try:
            items = json.loads(text[start:end + 1])
            if isinstance(items, list):
                flat = []
                for x in items:   # [["문장1"], ["문장2"]]처럼 겹친 배열은 펼친다
                    flat.extend(x if isinstance(x, list) else [x])
                return [str(x).strip() for x in flat if str(x).strip()][:5]
        except json.JSONDecodeError:
            pass
    if start != -1:     # 대괄호 안쪽만 (닫는 ]가 없으면 끝까지: 답이 길이 제한에서 잘린 경우)
        text = text[start + 1:end] if end > start else text[start + 1:]
        # 따옴표로 감싼 문장을 하나씩 꺼낸다. 한 줄에 여러 개가 붙어 있거나 마지막 문장이 잘려도 나뉜다
        quoted = [a or b for a, b in QUOTED_ITEM.findall(text)]
        if quoted:
            return [q.strip() for q in quoted if q.strip()][:5]
    # 따옴표도 없으면 줄 단위로 나눈다. 글머리표("-", "1.")만 지우고 "7.1" 같은 버전 숫자는 남긴다
    lines = [BULLET.sub("", line).strip().strip("\"',").strip() for line in text.splitlines()]
    return [line for line in lines if line][:5]


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
            if rr.character:   # 한 캐릭터의 바뀐 부분. 버전을 안 말했으면(전체 버전 검색) 버전을 앞에 붙인다
                many = rr.version is None
                parts = []
                for r in records:
                    if r["change_type"] == "added" and r["folder"] == "characters":
                        labels = ["신규 캐릭터"]
                    elif r["change_type"] == "modified":
                        labels = sorted({lbl for lbl in (slot_label(c["field"]) for c in r["changes"]) if lbl})
                    else:
                        labels = []
                    for lbl in labels:
                        item = f"{r['version']} {lbl}" if many else lbl
                        if item not in parts:
                            parts.append(item)
                return parts if many else sorted(parts)
            if rr.patch_added:   # 신규: 물은 종류가 없으면 캐릭터·무기
                folders = (rr.patch_folder,) if rr.patch_folder else ("characters", "weapons")
                return list(dict.fromkeys(r["entity_name"] for r in records
                                          if r["change_type"] == "added" and r["folder"] in folders))
            folders = (rr.patch_folder,) if rr.patch_folder else ("talents", "constellations")
            return sorted({r["entity_name"] for r in records
                           if r["change_type"] == "modified" and r["folder"] in folders})

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


# 후처리: 모델이 쓴 이름·값을 근거에 있는 정확한 글자로 맞춘다 (평가 노트북 셀 10-2도 이 함수를 쓴다)
#  - '라이デン 쇼군' -> '라이덴 쇼군', '쿠피시노부' -> '쿠키 시노부' (비슷한 정도가 cutoff 이상이면 바꿈)
#  - 근거에 없는 이름('베티')은 버린다. 잘못 바꾼 경우 0건 (DEV 4건, 평가 9건)
#  - DEV macro F1 0.814 -> 0.816, 평가 0.8453 -> 0.8455 (cutoff 0.6, DEV로 정함)
#  - 캐릭터 근거(lookup, filter)에만 쓴다. 패치·빌드 근거는 문장 모양이 달라 그대로 둔다
POST_CUTOFF = 0.6
POST_ROUTES = ("lookup", "filter")
EVIDENCE_LABELS = ("원소 ", "무기 ", "지역 ")


def canonical(text):
    """표기 차이만 맞춘다: '불 원소'->'불', '5'/'5성급'/'★5'->'5성', '몬드 출신'->'몬드'. (노트북 셀 3과 같다)"""
    t = str(text).strip().strip("\"'「」").strip()
    t = re.sub(r"\s*(원소|출신|지역)$", "", t)
    m = re.fullmatch(r"[★☆]?\s*(\d)\s*(성급|성|star)?", t, re.I)
    if m:
        return f"{m.group(1)}성"
    return t.lower()


def evidence_words(texts):
    """근거 문장 'A: 원소 X / 무기 Y / 5성 / 지역 Z'에서 답이 될 수 있는 낱말(A, X, Y, 5성, Z)을 뽑는다."""
    words = []
    for text in texts:
        name, _, rest = text.partition(": ")
        words.append(name)
        for part in rest.split(" / "):
            for label in EVIDENCE_LABELS:
                if part.startswith(label):
                    part = part[len(label):]
            words.append(part)
    return [w for w in words if w and w != "정보 없음"]


def clean_answer(pred, texts, cutoff=POST_CUTOFF):
    allowed = {canonical(w): w for w in evidence_words(texts)}
    cleaned = []
    for item in pred:
        key = canonical(item)
        if key not in allowed:
            close = difflib.get_close_matches(key, list(allowed), n=1, cutoff=cutoff)
            key = close[0] if close else None
        if key is not None and allowed[key] not in cleaned:
            cleaned.append(allowed[key])
    return cleaned


class LLMAnswerer:
    sentence_routes = TEXT_ROUTES   # 이 경로의 답은 문장 목록 (pipeline이 한 줄에 하나씩 보여 준다)

    def __init__(self, generate_fn, name="llm", method="rag_v4", postprocess=True):
        self.generate_fn = generate_fn
        self.name = name
        self.method = method
        self.postprocess = postprocess
        self.last_raw = ""          # 마지막 모델 원문 (오답 분석용)

    def _generate(self, prompt, **options):
        """generate_fn이 받을 수 있는 옵션(max_new_tokens, stop_strings)만 넘긴다 (노트북의 옛 generate(prompt)와도 호환)."""
        tries = [options, {k: v for k, v in options.items() if k != "stop_strings"}, {}]
        for i, kwargs in enumerate(tries):
            try:
                return self.generate_fn(prompt, **kwargs)
            except TypeError:
                if not kwargs or i == len(tries) - 1:
                    raise

    def answer(self, question, rr, evidence):
        if rr.route in TEXT_ROUTES:     # 패치·아이템: 문장 답
            # ']'에서 멈추지 않는다: 모델이 [["문장1"], ["문장2"]]처럼 배열을 겹쳐 쓰면 첫 문장에서 잘렸다 (11/10 코랩 확인)
            self.last_raw = self._generate(build_text_prompt(question, evidence),
                                           max_new_tokens=TEXT_MAX_NEW_TOKENS, stop_strings=None)
            return parse_text_answer(self.last_raw)
        self.last_raw = self._generate(build_prompt(question, evidence, self.method))
        pred = parse_list_answer(self.last_raw)
        if self.postprocess and rr.route in POST_ROUTES:
            pred = clean_answer(pred, [e["text"] for e in evidence if e["kind"] == "character"])
        return pred

