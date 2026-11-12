"""주요 수치 요약표: content/*.yaml 글을 다시 쓸 때 참고한다 (dashboard/README.md 3-3).

실행 (저장소 어디서든):
  python dashboard/summary.py               # 네 폴더 전부
  python dashboard/summary.py official dev  # 고른 폴더만 (official / dev / aux / model_compare)

출력: 폴더마다 검증 결과, yaml에 붙여 넣을 based_on, 소수 3자리 마크다운 표.
결과 JSON은 읽기만 한다.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))   # dashboard/ 를 import 경로에 (어디서 실행해도)

from lib import loader, text  # noqa: E402
from lib.loader import fmt, metric  # noqa: E402

TYPE_KO = {"lookup": "조회", "filter": "조건", "unknown": "없음"}


def table(header, rows):
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]
    return "\n".join(lines)


def type_cells(data, key):
    return [fmt(metric(data, key, t)) for t in loader.TYPES]


def official(result):
    rows = []
    for r in result["runs"]:
        d = r["data"]
        wrong = [len(loader.wrong_questions(d, t)) for t in loader.TYPES]
        rows.append([r["key"], fmt(metric(d, "macro_f1")), *type_cells(d, "macro_f1"),
                     " / ".join(map(str, wrong)), fmt(metric(d, "micro_precision")), fmt(metric(d, "micro_recall")),
                     fmt(metric(d, "empty_answers")), fmt(loader.avg_answer_len(d)), fmt(loader.avg_gold_len(d))])
    n = metric(result["runs"][0]["data"], "n") if result["runs"] else "-"
    counts = " / ".join(str(metric(result["runs"][0]["data"], "n", t)) for t in loader.TYPES) if result["runs"] else "-"
    out = [f"문항 {n}개 (조회 / 조건 / 없음 = {counts})", "",
           table(["단계", "Macro F1", "조회", "조건", "없음", "오답 수 (조회/조건/없음)", "micro P", "micro R",
                  "빈 답", "조건 답 길이", "조건 정답 수"], rows)]
    if result["runs"]:
        last = result["runs"][-1]
        wrong = loader.wrong_questions(last["data"], "unknown")
        out += ["", f"데이터 없음 오답 ({last['key']}, {len(wrong)}개)"]
        out += [f"- {w['question']} → {w['pred']}" for w in wrong] or ["- 없음"]
    return "\n".join(out)


def dev(result):
    rows = []
    for r in result["runs"]:
        d = r["data"]
        rows.append([r["key"], fmt(metric(d, "macro_f1")), fmt(metric(d, "empty_answers")),
                     fmt(metric(d, "avg_seconds")), fmt(loader.median_seconds(d)), fmt(metric(d, "max_seconds")),
                     *type_cells(d, "avg_seconds")])
    empties = [metric(r["data"], "empty_answers") for r in result["runs"]]
    avgs = [metric(r["data"], "avg_seconds") for r in result["runs"]]
    r_value = loader.pearson_r(empties, avgs) if None not in empties + avgs else None
    return "\n".join([
        table(["단계", "Macro F1", "빈 답", "평균(초)", "중앙값", "최대", "조회 평균", "조건 평균", "없음 평균"], rows),
        "", f"빈 답 수 ↔ 평균 응답 시간 상관계수 r = {fmt(r_value)} ({len(result['runs'])}개 단계)"])


def aux(result):
    rows = []
    for r in result["runs"]:
        d = r["data"]
        by_type = loader.hallucinations_by_type(d)
        types = " / ".join(str(by_type[t]) for t in loader.TYPES) if by_type else "유형 구분 없음"
        rows.append([r["key"], fmt(metric(d, "accuracy")), fmt(metric(d, "refusal_accuracy")),
                     fmt(metric(d, "hallucination_rate")),
                     f"{metric(d, 'hallucinated_questions')} / {metric(d, 'answered')}", types])
    return table(["단계", "정답률", "거절 정확도", "환각률", "환각 / 답한 문항", "환각 유형 (조회/조건/없음)"], rows)


def model_compare(result):
    rows = []
    for r in result["runs"]:
        d, m = r["data"], r["model"]
        rows.append([m["size"], f"{m['gpu']} · {m['precision']}", fmt(metric(d, "macro_f1")),
                     *type_cells(d, "macro_f1")[:2], fmt(metric(d, "micro_precision")), fmt(metric(d, "micro_recall")),
                     fmt(loader.avg_answer_len(d)), fmt(metric(d, "avg_seconds")), fmt(loader.median_seconds(d)),
                     *type_cells(d, "avg_seconds")[:2]])
    return table(["모델", "GPU · 정밀도", "Macro F1", "조회", "조건", "정밀도", "재현율", "조건 답 길이",
                  "평균(초)", "중앙값", "조회 평균", "조건 평균"], rows)


FORMATTERS = {"official": official, "dev": dev, "aux": aux, "model_compare": model_compare}


def report(folder, result):
    lines = [f"## {folder}", ""]
    if result["checks"]:
        lines += [f"- [{c['level']}] {c['msg']}" for c in result["checks"]] + [""]
    if result["excluded"]:
        lines += [f"(안 쓰는 파일 {len(result['excluded'])}개: " +
                  ", ".join(f"{e['file']} - {e['reason']}" for e in result["excluded"]) + ")", ""]
    if not result["runs"]:
        return "\n".join(lines + ["쓸 수 있는 결과 파일이 없어요."])
    lines += ["```yaml", "based_on:", f"  folder: {folder}", f'  created_at: "{result["latest_created_at"]}"', "```", ""]
    lines.append(FORMATTERS[folder](result))
    return "\n".join(lines)


def main(argv):
    folders = argv or list(loader.FOLDERS)
    bad = [f for f in folders if f not in loader.FOLDERS]
    if bad:
        print(f"모르는 폴더: {', '.join(bad)} (가능: {', '.join(loader.FOLDERS)})")
        return 2
    order = text.stage_order()   # content/stages.yaml의 order
    print("\n\n".join(report(f, loader.load_folder(f, order=order)) for f in folders))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
