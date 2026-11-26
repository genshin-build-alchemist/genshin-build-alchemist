"""원신 챗봇 성능 개선 비교 대시보드 (FR-E4). 실행: streamlit run dashboard/app.py

- 숫자는 data/의 결과 JSON에서, 글은 content/*.yaml에서 읽는다 (README 3장).
- 화면 왼쪽 '실험 단계' 버튼으로 단계를 고르면, 각 탭은 그 단계까지의 결과를 그리고 카드는 직전 단계와 비교한다.
- 경로는 모두 이 파일 위치 기준이라 로컬·Streamlit Community Cloud에서 똑같이 동작한다 (README 5-2).
- 결과 JSON은 읽기만 한다.
"""
import sys
from pathlib import Path

import streamlit as st

BASE = Path(__file__).resolve().parent     # dashboard/ 폴더. 여기를 import 경로에 넣어야 `from lib import ...`가 된다
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

from lib import charts, loader, text, ui  # noqa: E402
from lib.loader import fix, fmt, metric, pct  # noqa: E402

TITLE = "원신 챗봇 성능 개선 대시보드"

# 탭: 이름, 글(yaml), 데이터 폴더, 실험 단계 버튼을 쓰는지
TABS = [
    {"label": "성능 변화", "content": "performance", "folder": "official", "pick": True},
    {"label": "응답 시간", "content": "response_time", "folder": "dev", "pick": True},   # DEV 60문항 (한 런타임에서 측정)
    {"label": "보조 지표", "content": "aux", "folder": "aux", "pick": True},
    {"label": "모델 비교", "content": "model_compare", "folder": "model_compare", "pick": True},
]


# ---------- 공통 ----------

def tab_bar(selected):
    """탭 버튼 줄. 누르면 session_state['tab']이 바뀌고 화면이 다시 그려진다."""
    def pick(i):
        """버튼을 누르면 Streamlit이 부르는 함수(on_click): 고른 탭 번호를 기억한다."""
        st.session_state["tab"] = i

    st.markdown(ui.selected_css(f"tab_{selected}"), unsafe_allow_html=True)   # 지금 탭 버튼만 선택된 색으로
    with st.container(key="tabbar", horizontal=True):
        for i, spec in enumerate(TABS):
            st.button(spec["label"], key=f"tab_{i}", on_click=pick, args=(i,))


def stage_fab(picks, selected):
    """화면 왼쪽 '실험 단계' 버튼 (최신 단계가 맨 위). 고른 단계는 session_state['stage']에 기억한다."""
    def pick(stage):
        """단계 버튼을 누르면 고른 단계를 기억한다."""
        st.session_state["stage"] = stage

    st.markdown(ui.selected_css(f"fab_{selected}"), unsafe_allow_html=True)
    with st.container(key="fab"):
        ui.show('<span class="fab-l">실험 단계</span>')
        for s in reversed(picks):
            st.button(s, key=f"fab_{s}", on_click=pick, args=(s,))


def runs_upto(folder_result, stage):
    """폴더의 결과 중 stage까지 (stage가 없으면 None = 이 단계 결과 파일 없음)."""
    runs = folder_result["runs"]
    keys = [r["key"] for r in runs]
    return runs[:keys.index(stage) + 1] if stage in keys else None


def by_stage(content, stage):
    """yaml by_stage에서 고른 단계의 글 (없으면 빈 dict)."""
    return (content.get("by_stage") or {}).get(stage) or {}


def tab_head(ctx, content, run, stage, cards=None, words=None, metric_label=None, summary=None):
    """탭 머리말 + 검증 경고 + 요약 상자. cards가 있으면 상승/동일/하락 줄을 카드 변화에서 만든다."""
    d = run["data"]
    badges = [f"{loader.short_date(d.get('created_at'))} 측정", loader.data_badge(d, ctx["data_version"])]
    change = (ctx["stages"].get(stage) or {}).get("change")
    sec = by_stage(content, stage)
    if cards is not None:
        top = ui.status_summary_html(cards, words, answer=sec.get("answer"), metric_label=metric_label)
    else:
        top = ui.summary_html(summary)
    ui.show(ui.tab_header_html(content.get("question"), badges, stage, change)
            + ui.checks_html(ctx["folder"]["checks"])
            + ui.notice_html(text.based_on_status(content, ctx["folder"])) + top)


def chart_panel(content, chart_id, fig=None, legend=None, note=None, insights=None, override=None):
    """그래프 패널: 제목 → 그래프 → 범례 → 안내 → 💡 요약(그래프 아래).
    범례·안내는 그래프 박스(그림 영역) 왼쪽 선에 맞춘다 = 그래프 왼쪽 여백만큼 들여쓰기.
    override = 단계마다 다른 제목·부제·💡 (yaml by_stage.<단계>.charts.<id>)."""
    chart = {**((content.get("charts") or {}).get(chart_id) or {}), **(override or {})}
    key = f"panel_{chart_id}" + ("_accent" if chart.get("accent") else "")   # accent: 예외 강조 배경 (CSS *_accent)
    with st.container(key=key):   # 회색 패널은 CSS .st-key-panel_*
        ui.show(ui.chart_title_html(chart))
        if fig is not None:
            st.plotly_chart(fig, theme=None, config=charts.CONFIG, key=f"chart_{chart_id}")
        indent = fig.layout.margin.l if fig is not None and fig.layout.margin.l is not None else 0
        under = (ui.legend_html(legend, note=note) if legend else "") + ui.hint_html(chart)
        ui.show((f'<div class="under" style="margin-left:{indent}px">{under}</div>' if under else "")
                + ui.insight_html(insights if insights is not None else chart.get("insights")))


def compare_cards(spec, cur, prev):
    """카드 목록: spec = [(이름, 키, 단위, 클수록 좋은가, 표시 함수, delta 옵션)] -> 카드 dict 목록 (직전 단계 대비).
    어느 단계와 비교했는지는 카드 밖 아래 한 줄로 (ui.compare_note_html)."""
    out = []
    for label, key, unit, higher, show, opt in spec:
        out.append({"label": label, "value": show(cur[key]), "unit": unit,
                    "delta": ui.delta(cur[key], prev[key], higher_is_better=higher, **opt) if prev else None})
    return out


def compare_note(cur, prev):
    """카드 아래 '… 기준 · … 대비 변화' 한 줄 (직전 단계가 없으면 빈 글자)."""
    return ui.compare_note_html(cur["stage"], prev["stage"]) if prev else ""


# ---------- 성능 변화 ----------

def perf_rows(runs, stages):
    """official 결과 -> 단계별 Macro F1 (전체 + 유형별)."""
    rows = []
    for run in runs:
        d = run["data"]
        row = {"stage": run["key"], "change": (stages.get(run["key"]) or {}).get("change"), "f1": metric(d, "macro_f1")}
        for t in loader.TYPES:
            row[t] = metric(d, "macro_f1", t)
        rows.append(row)
    return rows


@st.dialog("단계별 프롬프트", width="large")
def prompt_dialog(key, ctx, f1):
    """'⧉ 프롬프트 보기'를 누르면 뜨는 모달: 프롬프트 전문(추가·변경 줄 표시) + 이 단계에서 바뀐 점."""
    ui.show(ui.prompt_view_html(key, ctx["order"], ctx["stages"], f1=f1, question=ctx["prompt_question"]))


def prompt_section(stage_keys, ctx, f1):
    """실험 기록 > 단계별 프롬프트 표: 단계 · 바뀐 점 · Macro F1 · 프롬프트 변경([⧉ 프롬프트 보기], 누르면 모달).
    표 상자(st-key-ptab) 안에 머리줄과 행을 같은 비율의 st.columns로 그려서 칸 위치를 맞춘다."""
    widths = [1.0, 3.6, 1.45, 1.25]
    with st.container(key="ptab"):
        ui.show(ui.prompt_title_html())
        with st.container(key="phead"):
            for col, head in zip(st.columns(widths, vertical_alignment="center"), ui.PROMPT_HEAD):
                with col:
                    ui.show(f'<span class="ph">{ui.esc(head)}</span>')
        for key in stage_keys:
            with st.container(key=f"prow_{key}"):
                cols = st.columns(widths, vertical_alignment="center")
                for col, cell in zip(cols, ui.prompt_cells(key, ctx["order"], ctx["stages"], f1)):
                    with col:
                        ui.show(cell)
                with cols[-1]:
                    if st.button(ui.PROMPT_BTN, key=f"pbtn_{key}"):
                        prompt_dialog(key, ctx, f1)


def render_performance(spec, content, ctx):
    """성능 변화: 카드 4개(직전 단계 대비) -> 단계별 F1 꺾은선 -> 실험 기록(프롬프트 · 오답 · 다음 과제)."""
    stage, runs = ctx["stage"], runs_upto(ctx["folder"], ctx["stage"])
    rows = perf_rows(runs, ctx["stages"])
    cur, prev = rows[-1], (rows[-2] if len(rows) > 1 else None)
    card_spec = [(name, k, "", True, fix, {}) for k, name, _ in charts.PERF_SERIES]
    cards = compare_cards(card_spec, cur, prev)
    for c, (_, _, color) in zip(cards, charts.PERF_SERIES):
        c["color"] = color
    tab_head(ctx, content, runs[-1], stage, cards, ui.STATUS_WORDS["performance"], metric_label="Macro F1")
    ui.show(ui.cards_html(cards, foot=compare_note(cur, prev)))

    sec = by_stage(content, stage)
    legend = [(name, color, "line", None) for _, name, color in charts.PERF_SERIES]
    chart_panel(content, "c1a", charts.perf_lines(rows), legend=legend, insights=(sec.get("insights") or {}).get("c1a"))

    with st.expander("실험 기록 보기"):
        ui.show(ui.box_html("측정 기준", content.get("measure")))
        prompt_section([r["stage"] for r in rows], ctx, {r["stage"]: r["f1"] for r in rows})
        d = runs[-1]["data"]
        table = []
        for t in loader.TYPES:
            c = loader.exact_counts(d, t)
            table.append([ui.TYPE_LABEL[t], str(c["n"]), str(c["correct"]), str(c["wrong"]),
                          " / ".join(c["examples"]) or "없음"])
        ui.show(ui.result_table_html(["질문 유형", "문항 수", "완전 정답", "오답", "오답 문항 예시"], table,
                                     title="주요 발견 및 세부 정보", widths={0: "92px", 1: "64px", 2: "72px", 3: "52px"},
                                     num=(1, 2, 3), note=sec.get("findings_note")))
        if sec.get("problems"):
            ui.show(ui.result_table_html(["질문 유형", "문제점", "다음 과제"], [list(p) for p in sec["problems"]],
                                         title="문제점 및 다음 과제", widths={0: "92px"}, cls="lh15"))


# ---------- 응답 시간 ----------

def time_rows(runs, stages):
    """official 결과 -> 단계별 값 (카드 · 그래프 · 표가 같은 값을 쓴다)."""
    rows = []
    for run in runs:
        d = run["data"]
        rows.append({
            "stage": run["key"], "change": (stages.get(run["key"]) or {}).get("change"),
            "f1": metric(d, "macro_f1"), "empty": metric(d, "empty_answers"),
            "avg": metric(d, "avg_seconds"), "median": loader.median_seconds(d), "max": metric(d, "max_seconds"),
            "type_avg": {t: metric(d, "avg_seconds", t) for t in loader.TYPES},
            "n": metric(d, "n"),
        })
    return rows


def render_response_time(spec, content, ctx):
    """응답 시간: 속도 카드 3개 + 참고 카드 2개 -> 그래프 3개 -> 실험 기록(측정 기준 · 단계별 결과 · 느린 응답)."""
    stage, runs = ctx["stage"], runs_upto(ctx["folder"], ctx["stage"])
    rows = time_rows(runs, ctx["stages"])
    cur, prev = rows[-1], (rows[-2] if len(rows) > 1 else None)
    s_unit = {"unit": "초"}     # 변화량 글자에도 '초'
    speed = compare_cards([("평균", "avg", "초", False, fix, s_unit), ("중앙값", "median", "초", False, fix, s_unit),
                           ("최대", "max", "초", False, fix, s_unit)], cur, prev)
    ref = compare_cards([("Macro F1", "f1", "", True, fix, {}), ("빈 응답", "empty", "개", False, fmt, {"unit": "개"})],
                        cur, prev)
    tab_head(ctx, content, runs[-1], stage, speed, ui.STATUS_WORDS["response_time"])
    ui.show(ui.cards_html(speed, ref=ref, foot=compare_note(cur, prev)))

    sec = by_stage(content, stage)
    ins = sec.get("insights") or {}
    gray = [("평균", ui.COLOR["avg"], "square", None), ("중앙값", ui.COLOR["median"], "square", None)]
    types = [(ui.TYPE_LABEL[t], ui.COLOR[t], "square", None) for t in loader.TYPES]
    r_value = loader.pearson_r([r["empty"] for r in rows], [r["avg"] for r in rows])
    chart_panel(content, "c2a", charts.f1_and_time(rows), legend=gray, insights=ins.get("c2a"))
    chart_panel(content, "c2b", charts.empty_vs_time(rows, r_value, rows[0]["n"]), insights=ins.get("c2b"))
    chart_panel(content, "c2c", charts.time_by_type(rows), legend=types, insights=ins.get("c2c"))

    with st.expander("실험 기록 보기"):
        measure = [s for part in (content.get("measure"), sec.get("measure_extra"))     # 문장마다 불릿 한 줄
                   for s in (part if isinstance(part, list) else ui.sentences(part))]
        ui.show(ui.box_html("측정 기준", measure))
        table = [[r["stage"], fix(r["avg"]), fix(r["median"]), fix(r["max"]), fix(r["f1"]), fmt(r["empty"])] for r in rows]
        ui.show(ui.result_table_html(["단계", "평균(초)", "중앙값(초)", "최대(초)", "Macro F1", "빈 응답 수"], table,
                                     title="단계별 결과", highlight=len(rows) - 1, widths={0: "110px"}, num=(1, 2, 3, 4, 5)))
        slow = [[s["question"], f"{fix(s['seconds'])}초", str(s["pred_n"]), str(s["gold_n"])]
                for s in loader.slowest(runs[-1]["data"])]
        ui.show(ui.result_table_html(["실제 질문", "응답 시간", "답변에 포함한 항목", "정답 항목"], slow,
                                     title="느린 응답 사례", widths={1: "86px", 2: "130px", 3: "76px"}, num=(1, 2, 3),
                                     note=sec.get("slow_note")))
        if sec.get("next"):
            ui.show(ui.box_html("다음 과제", sec["next"]))


# ---------- 보조 지표 ----------

def aux_rows(runs, stages):
    """aux 결과 -> 단계별 값 (카드 · 그래프 · 표가 같은 값을 쓴다)."""
    rows = []
    for run in runs:
        d = run["data"]
        rows.append({
            "stage": run["key"], "change": (stages.get(run["key"]) or {}).get("change"),
            "acc": metric(d, "accuracy"), "ref": metric(d, "refusal_accuracy"), "hal": metric(d, "hallucination_rate"),
            "answered": metric(d, "answered"), "hn": metric(d, "hallucinated_questions"), "n": metric(d, "n"),
            "types": loader.hallucinations_by_type(d),   # 목록이 없으면 None -> '유형 구분 없음'
        })
    return rows


AUX_DEF_KEY = {"acc": "accuracy", "ref": "refusal_accuracy", "hal": "hallucination_rate"}   # aux.yaml definitions


def render_aux(spec, content, ctx):
    """보조 지표: 카드 3개(정답률 · 거절 정확도 · 환각률, 직전 단계 대비) -> 그래프 3개 -> 실험 기록."""
    stage, runs = ctx["stage"], runs_upto(ctx["folder"], ctx["stage"])
    rows = aux_rows(runs, ctx["stages"])
    cur, prev = rows[-1], (rows[-2] if len(rows) > 1 else None)
    defs = content.get("definitions") or {}
    opt = {"digits": 1, "scale": 100, "unit": "%p"}
    cards = compare_cards([("정답률", "acc", "", True, pct, opt), ("거절 정확도", "ref", "", True, pct, opt),
                           ("환각률", "hal", "", False, pct, opt)], cur, prev)
    tab_head(ctx, content, runs[-1], stage, cards, ui.STATUS_WORDS["aux"])
    ui.show(ui.cards_html(cards, foot=compare_note(cur, prev)))

    sec = by_stage(content, stage)
    ins = sec.get("insights") or {}
    rate_legend = [(name, color, "line", defs.get(AUX_DEF_KEY[k])) for k, name, color in charts.AUX_SERIES]
    stack_legend = [("근거 안에서 답함", ui.COLOR["unknown"], "square", None), ("환각 포함", ui.COLOR["filter"], "square", None)]
    type_legend = [(ui.TYPE_LABEL[t], ui.COLOR[t], "square", None) for t in loader.TYPES]
    if any(r["types"] is None for r in rows):     # 환각 목록이 없는 단계가 있으면 범례에 '유형 구분 없음' 추가
        type_legend.append(("유형 구분 없음", "transparent", "dashed", None))
    chart_panel(content, "c3a", charts.aux_rates(rows), legend=rate_legend, insights=ins.get("c3a"))
    chart_panel(content, "c3b", charts.answered_stack(rows), legend=stack_legend,
                note=f"· 막대 전체 = 응답 문항 수 ({rows[0]['n']}문항 중, 빈 응답 제외)", insights=ins.get("c3b"))
    chart_panel(content, "c3c", charts.hal_by_type(rows), legend=type_legend, insights=ins.get("c3c"))

    with st.expander("실험 기록 보기"):
        notes = content.get("definition_notes") or {}     # 기준 아래 작은 회색 글 (예: 환각 예시)
        crit = [[name, (defs.get(AUX_DEF_KEY[k], "—"), notes.get(AUX_DEF_KEY[k]))] for k, name, _ in charts.AUX_SERIES]
        ui.show(ui.result_table_html(["지표", "측정 기준"], crit, title="측정 기준", widths={0: "110px"}))
        table = [[r["stage"], pct(r["acc"]), pct(r["ref"]), pct(r["hal"]), f"{fmt(r['hn'])} / {fmt(r['answered'])}"]
                 for r in rows]
        ui.show(ui.result_table_html(["단계", "정답률", "거절 정확도", "환각률", "환각 문항 / 응답 문항"], table,
                                     title="단계별 결과", highlight=len(rows) - 1, widths={0: "110px"}, num=(1, 2, 3, 4)))
        if sec.get("findings"):
            lead = f'<div class="lead">{text.rich(sec["findings_lead"])}</div>' if sec.get("findings_lead") else ""
            ui.show(f'<div class="box"><span>주요 발견 및 세부 정보</span>{lead}<ul>'
                    + "".join(f"<li>{text.rich(x)}</li>" for x in sec["findings"]) + "</ul></div>")


# ---------- 모델 비교 ----------

def gpu_memory_text(runs, size):
    """그 모델 크기의 GPU 메모리 (결과 JSON config.gpu_memory_gb): '5.75GB', 조합마다 다르면 '5.45~14.19GB'."""
    vals = sorted({(r["data"].get("config") or {}).get("gpu_memory_gb") for r in runs if r["model"]["size"] == size} - {None})
    if not vals:
        return None
    return f"{fmt(vals[0])}GB" if len(vals) == 1 else f"{fmt(vals[0])}~{fmt(vals[-1])}GB"


def model_rows(runs, content):
    """model_compare 결과(고른 단계만) -> 조합별 값 (순서 = 모델 크기 → GPU → 정밀도).
    memory = 그 조합의 GPU 메모리(config.gpu_memory_gb), memory_size = 크기별 범위 (그래프 x축 아래)."""
    colors = {k: (v or {}).get("color") for k, v in (content.get("models") or {}).items()}
    rows = []
    for run in runs:
        d, m = run["data"], run["model"]
        if not m:
            continue
        mem = (d.get("config") or {}).get("gpu_memory_gb")
        rows.append({
            "size": m["size"], "gpu": m["gpu"], "precision": m["precision"], "label": loader.model_label(run),
            "f1": metric(d, "macro_f1"), "lookup": metric(d, "macro_f1", "lookup"), "filter": metric(d, "macro_f1", "filter"),
            "avg": metric(d, "avg_seconds"), "median": loader.median_seconds(d),
            "lookup_t": metric(d, "avg_seconds", "lookup"), "filter_t": metric(d, "avg_seconds", "filter"),
            "precision_v": metric(d, "micro_precision"), "recall": metric(d, "micro_recall"),
            "f_prec": metric(d, "micro_precision", "filter"), "f_recall": metric(d, "micro_recall", "filter"),
            "ans_len": loader.avg_answer_len(d, "filter"),
            "memory": f"{fmt(mem)}GB" if mem is not None else None, "memory_size": gpu_memory_text(runs, m["size"]),
            "color": colors.get(m["size"]) or ui.COLOR["avg"],
        })
    return rows


MODEL_BOXES = [("findings", "주요 발견"), ("problems", "현재 문제점 및 개선 방향"), ("decisions", "팀 결정 사항"),
               ("next", "다음 과제")]


def render_model_compare(spec, content, ctx):
    """모델 비교: 고른 실험 단계(method)의 결과만 -> 1위 카드 4개 -> 그래프 5개(chart_order) -> 실험 기록.
    그 단계의 결과 파일이 없으면 '아직 없어요' 안내. 글은 yaml by_stage.<단계>."""
    folder_result, stage = ctx["folder"], ctx["stage"]
    have = [s for s in ctx["order"] if any(r["method"] == s for r in folder_result["runs"])]
    runs = [r for r in folder_result["runs"] if r["method"] == stage]
    if not runs:
        ui.show(ui.tab_header_html(content.get("question"), [], stage, (ctx["stages"].get(stage) or {}).get("change"))
                + ui.empty_html(stage, have[-1] if have else "다른 단계"))
        return
    sec = by_stage(content, stage)
    latest = max(runs, key=lambda r: r["data"].get("created_at", ""))
    tab_head(ctx, content, latest, stage, summary=sec.get("summary") or content.get("summary"))
    rows = model_rows(runs, content)
    setup = content.get("baseline_setup") or {"gpu": "L4", "precision": "fp16"}
    # 크기별 그래프용 행(복사본): x축 아래 메모리 = 그 크기의 조합 전체 범위 (표의 행은 조합별 값 그대로)
    base = [dict(r, memory=r["memory_size"]) for r in rows
            if r["gpu"] == str(setup.get("gpu")).upper() and r["precision"] == str(setup.get("precision")).lower()]
    # 속도 기준: 보통은 전체 평균. 조건 검색을 모델 없이 답한 단계(rag_v5_data)는 캐릭터 조회 평균 (yaml speed)
    speed = sec.get("speed") or {}
    t_key, t_label = speed.get("key", "avg"), speed.get("label", "평균 응답 시간")
    t_axis = speed.get("axis", "평균 응답 시간")

    # 1위 카드 (기준 조합 안에서, 소수 3자리로 같으면 공동 1위)
    cards = []
    for label, key, higher, unit in (("Macro F1", "f1", True, "점(F1)"), ("조건 검색", "filter", True, "점(F1)"),
                                     ("캐릭터 조회", "lookup", True, "점(F1)"), (t_label, t_key, False, "초")):
        names, value = loader.best_of([(r["size"], r[key]) for r in base], higher=higher)
        if names:
            cards.append({"label": label, "medal": " · ".join(names), "value_text": f"{fmt(value)}{unit}"})
    if cards:
        ui.show(ui.cards_html(cards))

    over = sec.get("charts") or {}
    tips = (content.get("charts") or {}).get("c4b", {}).get("tips") or {}
    top_t = max(r[t_key] or 0 for r in rows)
    t_ticks = list(range(0, int(top_t) + 2, 2 if top_t > 6 else 1))   # 6초가 넘으면 2초 간격
    time_keys = [t_key] if t_key != "avg" else None
    time_legend = [(name, ui.COLOR[c], "line", None) for k, name, c in
                   (("avg", "전체 평균", "avg"), ("lookup_t", "캐릭터 조회", "lookup"), ("filter_t", "조건 검색", "filter"))
                   if time_keys is None or k in time_keys]
    panels = {
        "c4a": lambda: (charts.model_f1(base), [(name, color, "square", None) for _, name, color in charts.F1_SERIES]),
        "c4b": lambda: (charts.precision_recall(base),
                        [("정밀도", charts.PREC_COLOR, "dot", tips.get("precision")),
                         ("재현율", charts.RECALL_COLOR, "dot", tips.get("recall")),
                         ("조건 검색 Macro F1", ui.COLOR["filter"], "square", tips.get("filter_f1"))]),
        "c4c": lambda: (charts.model_time(base, keys=time_keys), time_legend),
        "c4d": lambda: (charts.combo_bars(rows, "f1", tickvals=[0, 0.25, 0.5, 0.75, 1], axis_title="Macro F1",
                                          time_key=t_key, time_label=t_label), None),
        "c4e": lambda: (charts.combo_bars(rows, t_key, unit="초", tickvals=t_ticks, axis_title=t_axis,
                                          time_key=t_key, time_label=t_label), None),
    }
    for chart_id in sec.get("chart_order") or content.get("chart_order") or list(panels):   # 단계마다 다를 수 있음
        if chart_id in ("c4a", "c4b", "c4c") and not base:
            continue
        fig, legend = panels[chart_id]()
        chart_panel(content, chart_id, fig, legend=legend, override=over.get(chart_id))

    with st.expander("실험 기록 보기"):
        pick = str(content.get("highlight_model") or "")
        table = [[r["size"], f"{r['gpu']} · {r['precision']}", fmt(r["f1"]), fmt(r["lookup"]), fmt(r["filter"]),
                  f"{fmt(r[t_key])}초", r["memory"] or "—"] for r in rows]
        ui.show(ui.result_table_html(["모델", "GPU · 정밀도", "Macro F1", "캐릭터 조회", "조건 검색", t_label, "GPU 메모리"],
                                     table, highlight=[i for i, r in enumerate(rows) if r["size"] == pick],
                                     widths={0: "64px", 1: "100px"}, num=(2, 3, 4, 5, 6)))
        for field, label in MODEL_BOXES:
            ui.show(ui.box_html(label, sec.get(field)))


# 탭(content 이름) -> 그 탭을 그리는 함수
RENDERERS = {"performance": render_performance, "response_time": render_response_time, "aux": render_aux,
             "model_compare": render_model_compare}


def render_tab(spec, content, ctx):
    """탭에 맞는 그리기 함수를 부른다. 고른 단계의 결과 파일이 없으면 안내만 (모델 비교는 함수 안에서 처리)."""
    if spec["content"] != "model_compare" and runs_upto(ctx["folder"], ctx["stage"]) is None:
        ui.show(ui.tab_header_html(content.get("question"), [], ctx["stage"])
                + ui.empty_html(ctx["stage"], "다른 단계"))
        return
    RENDERERS[spec["content"]](spec, content, ctx)


# ---------- 화면 ----------

def main():
    """대시보드 전체 순서: 화면 설정 -> 데이터·글 읽기 -> 머리말 -> 탭 버튼 -> 실험 단계 버튼 -> 고른 탭 그리기.
    Streamlit은 버튼을 누를 때마다 이 함수를 처음부터 다시 실행한다 (고른 탭·단계는 session_state에 기억)."""
    st.set_page_config(page_title=TITLE, page_icon="📊", layout="centered")
    st.markdown(ui.CSS, unsafe_allow_html=True)
    st.html(ui.TIP_SCRIPT, unsafe_allow_javascript=True)          # 마우스를 따라다니는 그래프 툴팁
    st.html(ui.STREAMLIT_SCRIPT, unsafe_allow_javascript=True)    # 실험 단계 버튼 위치 · 그래프 움직임

    stages_yaml = text.load_content("stages")
    order = list(stages_yaml.get("order") or loader.DEFAULT_ORDER)
    stages = stages_yaml.get("stages") or {}
    results = loader.load_all(order=order)                                      # 4개 폴더 JSON 읽기 + 검증
    contents = {t["content"]: text.load_content(t["content"]) for t in TABS}    # 탭별 설명 글 (yaml)

    official_keys = [r["key"] for r in results["official"]["runs"]]
    picks = [s for s in (stages_yaml.get("pick") or official_keys[-1:]) if s in official_keys] or official_keys[-1:]
    stage = st.session_state.get("stage")
    if stage not in picks:                         # 처음 열면 가장 최근 단계
        stage = picks[-1] if picks else None

    selected = st.session_state.get("tab", 0)      # 고른 탭 번호 (처음엔 0 = 성능 변화)
    spec = TABS[selected]
    folder = results[spec["folder"]]
    if not spec["pick"]:                           # 버튼을 쓰지 않는 탭: 그 폴더의 마지막 단계
        stage = folder["runs"][-1]["key"] if folder["runs"] else stage
    ctx = {"stage": stage, "order": order, "stages": stages, "folder": folder,
           "data_version": (contents["performance"].get("header") or {}).get("data_version"),
           "prompt_question": stages_yaml.get("prompt_question")}

    with st.container(key="dk"):   # 대시보드 전체 상자 (와이어프레임 .dk)
        ui.show(ui.header_html(TITLE))
        tab_bar(selected)
        if spec["pick"] and picks:
            stage_fab(picks, stage)
        if not folder["runs"]:
            st.info(f"{spec['folder']} 폴더에 쓸 수 있는 결과 파일이 없어요.")
        else:
            render_tab(spec, contents[spec["content"]], ctx)


main()
