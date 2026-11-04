"""질문 CSV로 라우터(경로 판별)를 점검한다. 모델을 부르지 않아서 GPU 없이 몇 초면 끝난다.

입력 CSV: question, target, note  (사람 질문·말투 변형 평가셋과 같은 형식)
  target '알베도/원소'          -> 경로 lookup, 캐릭터 알베도, 물은 항목 원소
  target '지역=몬드, 성급=5성'   -> 경로 filter, 조건 {지역: 몬드, 성급: 5성}
  target 빈칸                   -> 경로 unknown
note가 '짧은 반말 (id)'처럼 시작하면 괄호 앞 부분(말투)별로 정확도를 나눠 보여 준다.

실행
  python3 -m core.route_check data/eval/style_questions_dev.csv          # 라우터 고칠 때 (학습용 캐릭터)
  python3 -m core.route_check data/eval/style_questions_v1.csv           # 고친 뒤 한 번 확인 (평가용 캐릭터)
  python3 -m core.route_check 파일.csv --show 20                          # 틀린 질문 20개 보기
"""
import argparse
import csv
import re
import sys
from collections import Counter, defaultdict

from core.human_questions import FIELD_KO, _norm_value
from core.kb import load_kb
from core.router import Router


def expected_route(target):
    """target -> (경로, 캐릭터, 항목, 조건)."""
    target = (target or "").strip()
    if not target:
        return "unknown", None, None, {}
    if "=" in target:
        conds = {}
        for part in re.split(r"[,，]", target):
            if "=" in part:
                key, value = (x.strip() for x in part.split("=", 1))
                field = FIELD_KO.get(key)
                conds[field] = _norm_value(field, value)
        return "filter", None, None, conds
    name, key = (x.strip() for x in target.rsplit("/", 1))
    return "lookup", name, FIELD_KO.get(key), {}


def check_row(router, question, target):
    """한 질문 -> (경로·대상이 맞았는지, 물은 항목까지 맞았는지, 라우터 결과)."""
    route, name, field, conds = expected_route(target)
    rr = router.route(question)
    if route == "lookup":
        ok = rr.route == "lookup" and rr.character == name
        return ok, ok and rr.asked_field == field, rr
    if route == "filter":
        ok = rr.route == "filter" and rr.conditions == conds
        return ok, ok, rr
    ok = rr.route == "unknown"
    return ok, ok, rr


def style_of(note):
    note = (note or "").strip()
    return note.split(" (")[0] if note else "(말투 없음)"


def run(path, router, show=5):
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = [r for r in csv.DictReader(f) if (r.get("question") or "").strip()]
    total, by_style, field_ok, misses = Counter(), defaultdict(Counter), Counter(), []
    for r in rows:
        ok, ok_field, rr = check_row(router, r["question"], r.get("target"))
        style = style_of(r.get("note"))
        total[ok] += 1
        by_style[style][ok] += 1
        field_ok[ok_field] += 1
        if not ok:
            misses.append((style, r["question"], r.get("target"), f"{rr.route}/{rr.character or '-'}"))
    n = len(rows)
    print(f"{path}: {n}문항")
    print(f"  경로·대상 정확도 {total[True]}/{n} ({total[True] / n:.1%}),  물은 항목까지 {field_ok[True]}/{n} ({field_ok[True] / n:.1%})")
    for style, c in sorted(by_style.items()):
        m = c[True] + c[False]
        print(f"  - {style:<10} {c[True]}/{m} ({c[True] / m:.1%})")
    if misses and show:
        print(f"  틀린 질문 (앞 {min(show, len(misses))}개 / 전체 {len(misses)}개):")
        for style, q, target, got in misses[:show]:
            print(f"    [{style}] {q}  기대 {target or '(데이터에 없음)'}  ->  라우터 {got}")
    return {"n": n, "correct": total[True], "field_correct": field_ok[True],
            "by_style": {s: dict(c) for s, c in by_style.items()}, "misses": misses}


def main(argv=None):
    parser = argparse.ArgumentParser(description="질문 CSV로 라우터 정확도 점검")
    parser.add_argument("csv", nargs="+", help="question,target,note 형식 CSV")
    parser.add_argument("--show", type=int, default=5, help="틀린 질문을 몇 개 보여 줄지")
    args = parser.parse_args(argv)
    router = Router(load_kb())
    for path in args.csv:
        run(path, router, args.show)
    return 0


if __name__ == "__main__":
    sys.exit(main())
