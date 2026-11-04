"""사람이 만든 질문의 정답을 데이터에서 채운다.

질문 문장은 해석하지 않는다. 작성자가 적은 target(무엇을 물었는지)만 보고 data/characters_ko.json에서 답을 찾는다.
그래서 챗봇 라우터와 독립적이다 (라우터가 질문을 잘못 알아들어도 정답이 오염되지 않는다).

target 형식
  캐릭터 1명 조회 : '알베도/원소'            (항목: 원소, 무기, 성급, 지역)
  조건 검색       : '지역=몬드, 성급=5성'     (쉼표로 조건을 이어 씀, 모든 조건을 만족하는 캐릭터)
  데이터에 없음   : 빈칸                     (정답은 빈 배열 [])

실행: python3 -m core.human_questions 입력.csv [출력.csv]
  입력 CSV 칸: question, target, note (answer 칸은 있어도 되고 없어도 됨)
  출력 CSV 칸: question, answer, target, note, check  (노트북은 question/answer만 읽는다)
  check 칸이 '오류:'로 시작하는 줄은 target을 고친 뒤 다시 실행한다. '확인:'은 의도가 맞는지만 본다.
"""
import csv
import difflib
import re
import sys
from pathlib import Path

from core.kb import load_kb

FIELD_KO = {"원소": "element", "속성": "element", "무기": "weapon", "성급": "rarity", "등급": "rarity",
            "지역": "region", "출신": "region"}
OUT_FIELDS = ["question", "answer", "target", "note", "check"]


def _norm_value(field, value):
    """표기 차이만 맞춘다: '5', '5성급' -> '5성' / '불원소', '불 속성' -> '불' / '몬드 출신' -> '몬드'."""
    v = value.strip()
    if field == "rarity":
        m = re.fullmatch(r"([45])\s*(성|성급)?", v)
        return f"{m.group(1)}성" if m else v
    if field == "element":
        return re.sub(r"\s*(원소|속성)$", "", v)
    if field == "region":
        return re.sub(r"\s*출신$", "", v)
    return v


def _suggest(word, choices):
    close = difflib.get_close_matches(word, list(choices), n=3, cutoff=0.4)
    return f" (혹시: {', '.join(close)})" if close else ""


def answer_for_target(target, kb):
    """target -> (정답 목록 또는 None, 메시지 또는 None).

    정답이 None이면 오류(target을 고쳐야 함). 정답이 있는데 메시지도 있으면 확인용 안내.
    """
    target = (target or "").strip()
    if not target:
        return [], None                                   # 데이터에 없는 질문
    values = {f: sorted({c[f] for c in kb.characters if c[f]}) for f in ("element", "weapon", "rarity", "region")}

    if "=" in target:                                     # 조건 검색
        conds = {}
        for part in re.split(r"[,，]", target):
            if not part.strip():
                continue
            if "=" not in part:
                return None, f"조건은 '항목=값' 형식이어야 함: '{part.strip()}'"
            key, value = (x.strip() for x in part.split("=", 1))
            field = FIELD_KO.get(key)
            if not field:
                return None, f"모르는 항목 '{key}' (원소/무기/성급/지역 중 하나)"
            value = _norm_value(field, value)
            if value not in values[field]:
                return None, f"{key}에 '{value}' 값이 없음{_suggest(value, values[field])}"
            conds[field] = value
        names = sorted(c["name"] for c in kb.characters if all(c[f] == v for f, v in conds.items()))
        if not names:
            return [], "조건을 모두 만족하는 캐릭터가 없어서 정답을 [] 로 둠"
        return names, None

    if "/" in target:                                     # 캐릭터 1명 조회
        name, key = (x.strip() for x in target.rsplit("/", 1))
        field = FIELD_KO.get(key)
        if not field:
            return None, f"모르는 항목 '{key}' (원소/무기/성급/지역 중 하나)"
        char = kb.char_by_name.get(name)
        if not char:
            return None, f"캐릭터 '{name}' 없음{_suggest(name, kb.char_by_name)}"
        if not char[field]:
            return [], f"{name}의 {key} 정보가 데이터에 없어서 정답을 [] 로 둠"
        return [char[field]], None

    return None, "target 형식을 모르겠음 ('이름/항목' 또는 '항목=값, 항목=값', 데이터에 없으면 빈칸)"


def fill_rows(rows, kb):
    """CSV 행 목록 -> (정답을 채운 행 목록, 오류 개수). 빈 질문 행은 건너뛴다."""
    out, errors = [], 0
    for row in rows:
        question = (row.get("question") or "").strip()
        if not question:
            continue
        target = (row.get("target") or "").strip()
        answer, message = answer_for_target(target, kb)
        check = ""
        if answer is None:
            errors += 1
            check = "오류: " + message
        else:
            manual = {a.strip() for a in (row.get("answer") or "").split("|") if a.strip()}
            if manual and target and manual != set(answer):
                message = f"직접 적은 답({'|'.join(sorted(manual))})이 데이터와 달라서 데이터 기준으로 채움"
            if message:
                check = "확인: " + message
        out.append({"question": question, "answer": "|".join(answer or []), "target": target,
                    "note": (row.get("note") or "").strip(), "check": check})
    return out, errors


def fill_csv(src, dst=None, kb=None):
    """CSV 파일 -> 정답을 채운 CSV 파일. 반환: (출력 경로, 행 목록, 오류 개수)."""
    kb = kb or load_kb()
    src = Path(src)
    dst = Path(dst) if dst else src.with_name(src.stem + "_filled.csv")
    with open(src, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    out, errors = fill_rows(rows, kb)
    with open(dst, "w", encoding="utf-8-sig", newline="") as f:   # utf-8-sig: 엑셀에서 한글이 안 깨지게
        writer = csv.DictWriter(f, fieldnames=OUT_FIELDS)
        writer.writeheader()
        writer.writerows(out)
    return dst, out, errors


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 1
    dst, out, errors = fill_csv(argv[1], argv[2] if len(argv) > 2 else None)
    print(f"{len(out)}문항 -> {dst}")
    for i, row in enumerate(out, 2):                       # 2행부터 (1행은 제목)
        if row["check"]:
            print(f"  {i}행 '{row['question']}': {row['check']}")
    print("오류 없음" if errors == 0 else f"오류 {errors}줄: target을 고친 뒤 다시 실행하세요.")
    return 0 if errors == 0 else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
