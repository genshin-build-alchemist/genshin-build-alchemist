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
    """머리글과 줄 목록 -> 마크다운 표 글자 (| 단계 | F1 | ... 모양). 깃허브·노션에 그대로 붙여 넣을 수 있다."""
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]
    return "\n".join(lines)


def type_cells(data, key):
    """유형별(조회 / 조건 / 없음) 값 3칸을 화면용 글자로. 예: key="macro_f1" -> 유형별 점수 3개."""
    return [fmt(metric(data, key, t)) for t in loader.TYPES]


def official(result):
    """official(공식 평가) 폴더 요약: 단계별 점수 표 + 마지막 단계의 '데이터 없음' 오답 목록 (① 탭 글 쓰기용)."""
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
    """dev 폴더 요약: 단계별 응답 시간 표 + 빈 답 수와 평균 시간의 상관계수 (② 탭 글 쓰기용)."""
    rows = []
    for r in result["runs"]:
        d = r["data"]
        rows.append([r["key"], fmt(metric(d, "macro_f1")), fmt(metric(d, "empty_answers")),
                     fmt(metric(d, "avg_seconds")), fmt(loader.median_seconds(d)), fmt(metric(d, "max_seconds")),
                     *type_cells(d, "avg_seconds")])
    empties = [metric(r["data"], "empty_answers") for r in result["runs"]]
    avgs = [metric(r["data"], "avg_seconds") for r in result["runs"]]
    r_value = loader.pearson_r(empties, avgs) if None not in empties + avgs else None   # 값이 하나라도 비면 계산하지 않음
    return "\n".join([
        table(["단계", "Macro F1", "빈 답", "평균(초)", "중앙값", "최대", "조회 평균", "조건 평균", "없음 평균"], rows),
        "", f"빈 답 수 ↔ 평균 응답 시간 상관계수 r = {fmt(r_value)} ({len(result['runs'])}개 단계)"])


def aux(result):
    """aux 폴더 요약: 정답률·거절 정확도·환각률과 환각 유형 (③ 탭 글 쓰기용)."""
    rows = []
    for r in result["runs"]:
        d = r["data"]
        by_type = loader.hallucinations_by_type(d)
        types = " / ".join(str(by_type[t]) for t in loader.TYPES) if by_type else "유형 구분 없음"
        rows.append([r["key"], fmt(metric(d, "accuracy")), fmt(metric(d, "refusal_accuracy")),
                     fmt(metric(d, "hallucination_rate")),
                     f"{metric(d, 'hallucinated_questions')} / {metric(d, 'answered')}", types])
    return table(["단계", "정답률", "거절 정확도", "환각률", "환각 / 응답 문항", "환각 유형 (조회/조건/없음)"], rows)


def model_compare(result):
    """model_compare 폴더 요약: 단계 · 모델 · GPU · 정밀도 조합별 점수와 속도 (④ 탭 글 쓰기용).
    정밀도·재현율은 c4b 그래프와 같은 조건 검색 기준, GPU 메모리는 config.gpu_memory_gb."""
    rows = []
    for r in result["runs"]:
        d, m = r["data"], r["model"]
        rows.append([r["method"], m["size"], f"{m['gpu']} · {m['precision']}", fmt(metric(d, "macro_f1")),
                     *type_cells(d, "macro_f1")[:2],
                     fmt(metric(d, "micro_precision", "filter")), fmt(metric(d, "micro_recall", "filter")),
                     fmt(loader.avg_answer_len(d, "filter"), 1), fmt(metric(d, "avg_seconds")), fmt(loader.median_seconds(d)),
                     *type_cells(d, "avg_seconds")[:2], fmt((d.get("config") or {}).get("gpu_memory_gb"))])
    return table(["단계", "모델", "GPU · 정밀도", "Macro F1", "조회", "조건", "조건 정밀도", "조건 재현율", "조건 답 길이",
                  "평균(초)", "중앙값", "조회 평균", "조건 평균", "GPU 메모리(GB)"], rows)


# 폴더 이름 -> 그 폴더를 요약하는 함수 (위 4개). report 가 폴더에 맞는 함수를 골라 부른다
FORMATTERS = {"official": official, "dev": dev, "aux": aux, "model_compare": model_compare}


def report(folder, result):
    """폴더 하나의 전체 출력: 검증 경고 -> 안 쓰는 파일 -> yaml에 붙여 넣을 based_on -> 요약표."""
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
    """명령줄에서 받은 폴더 이름들(argv)을 요약해 출력한다. 없으면 4개 폴더 전부.
    돌려주는 값은 종료 코드: 0 = 정상, 2 = 모르는 폴더 이름."""
    folders = argv or list(loader.FOLDERS)
    bad = [f for f in folders if f not in loader.FOLDERS]
    if bad:
        print(f"모르는 폴더: {', '.join(bad)} (가능: {', '.join(loader.FOLDERS)})")
        return 2
    order = text.stage_order()   # content/stages.yaml의 order
    results = loader.load_all(order=order)   # aux의 측정 시각은 공식 결과에서 채워지므로 폴더를 함께 읽는다
    print("\n\n".join(report(f, results[f]) for f in folders))
    return 0


# 이 파일을 직접 실행할 때만 동작 (다른 파일이 import 할 때는 실행 안 됨). argv[1:] = 파일 이름 뒤의 단어들
if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
