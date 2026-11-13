"""원신 챗봇 성능 개선 비교 대시보드 (FR-E4). 실행: streamlit run dashboard/app.py

- 숫자는 data/의 결과 JSON에서, 글은 content/*.yaml에서 읽는다 (README 3장).
- 경로는 모두 이 파일 위치 기준이라 로컬·Streamlit Community Cloud에서 똑같이 동작한다 (README 5-2).
- 결과 JSON은 읽기만 한다.
"""
import sys
from pathlib import Path

import streamlit as st

BASE = Path(__file__).resolve().parent
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

from lib import charts, loader, text, ui  # noqa: E402
from lib.loader import fmt, metric  # noqa: E402

TITLE = "원신 챗봇 성능 개선 비교 대시보드"

# 탭: 이름, 글(yaml), 데이터 폴더, 그래프 순서
TABS = [
    {"label": "① 성능 변화", "content": "performance", "folder": "official", "charts": ["c1a"]},
    {"label": "② 응답 시간", "content": "response_time", "folder": "dev", "charts": ["c2a", "c2b", "c2c"]},
    {"label": "③ 보조 지표", "content": "aux", "folder": "aux", "charts": ["c3a", "c3b", "c3c"]},
    {"label": "④ 모델 비교", "content": "model_compare", "folder": "model_compare",
     "charts": ["c4a", "c4b", "c4c", "c4d", "c4e"]},
]

# 실험 기록 상자 이름 (와이어프레임)
RECORD_BOXES = {
    "performance": [("findings", "요약"), ("next", "다음 과제")],
    "response_time": [("findings", "주요 발견"), ("next", "다음 과제")],
    "aux": [("findings", "주요 발견"), ("next", "다음 과제")],
    "model_compare": [("findings", "주요 발견"), ("problems", "현재 문제점 및 개선 방향"),
                      ("decisions", "팀 결정 사항"), ("next", "다음 과제")],
}


# ---------- 탭 공통 ----------

def tab_bar(selected):
    """와이어프레임 모양의 탭 버튼 줄. 누르면 session_state['tab']이 바뀌고 화면이 다시 그려진다."""
    def pick(i):
        st.session_state["tab"] = i

    st.markdown(ui.selected_css(f"tab_{selected}"), unsafe_allow_html=True)
    with st.container(key="tabbar", horizontal=True):
        for i, spec in enumerate(TABS):
            st.button(spec["label"], key=f"tab_{i}", on_click=pick, args=(i,))


def tab_top(content, folder_result):
    """그 탭 데이터의 검증 경고 · based_on 회색 안내 · 상단 요약."""
    ui.show(ui.checks_html(folder_result["checks"])
            + ui.notice_html(text.based_on_status(content, folder_result))
            + ui.summary_html(content.get("summary")))


def chart_panel(content, chart_id, fig=None, legend=None, note=None):
    """그래프 패널: 제목 → 그래프 → 범례 → 안내 → 💡 요약(그래프 아래). fig가 없으면 자리만 표시.
    범례·안내는 그래프 박스(그림 영역) 왼쪽 선에 맞춘다 = 그래프 왼쪽 여백만큼 들여쓰기."""
    chart = (content.get("charts") or {}).get(chart_id, {})
    with st.container(key=f"panel_{chart_id}"):   # 회색 패널은 CSS .st-key-panel_*
        ui.show(ui.chart_title_html(chart))
        if fig is not None:
            st.plotly_chart(fig, theme=None, config=charts.CONFIG, key=f"chart_{chart_id}")
        else:
            st.caption(f"그래프 자리 ({chart_id}) · 탭별 단계에서 그려요")
        indent = fig.layout.margin.l if fig is not None and fig.layout.margin.l is not None else 0
        under = (ui.legend_html(legend, note=note) if legend else "") + ui.hint_html(chart)
        ui.show((f'<div class="under" style="margin-left:{indent}px">{under}</div>' if under else "")
                + ui.insight_html(chart.get("insights")))


def stage_findings(content, key):
    """② 단계 선택 칩: findings가 단계별(dict)이면 고른 단계의 주요 발견을 보여 준다.
    planned_stages는 흐리게(누를 수 없게) '(예정)'으로 보인다."""
    findings = content.get("findings") or {}
    stages = list(findings)
    planned = [s for s in content.get("planned_stages") or [] if s not in findings]
    if not stages:
        return
    state = f"pick_{key}"
    picked = st.session_state.get(state)
    if picked not in findings:
        picked = stages[-1]

    def pick(stage):
        st.session_state[state] = stage

    st.markdown(ui.selected_css(f"chip_{key}_{picked}"), unsafe_allow_html=True)
    with st.container(key=f"chips_{key}", horizontal=True, vertical_alignment="center"):
        ui.show('<span class="chips-label">단계 선택</span>', width="content")
        for s in stages:
            st.button(s, key=f"chip_{key}_{s}", on_click=pick, args=(s,))
        for s in planned:
            st.button(f"{s} (예정)", key=f"chip_{key}_{s}", disabled=True)
    ui.show(ui.box_html("주요 발견", findings[picked]))


def record_boxes(spec, content):
    """실험 기록 안의 yaml 글 상자들."""
    for field, label in RECORD_BOXES[spec["content"]]:
        value = content.get(field)
        if field == "findings" and isinstance(value, dict):
            stage_findings(content, key=f"stage_{spec['content']}")
        else:
            ui.show(ui.box_html(label, value))


def _joined(values):
    return ", ".join(f"`{v}`" for v in sorted({str(v) for v in values if v is not None}))


def conditions_box(content, folder_result):
    """② 실험 조건: yaml의 수동 값 + JSON에서 읽는 값 (코드 · 평가셋 · 모델 · 생성 설정 · 문항)."""
    manual = content.get("manual") or {}
    rows = [tuple(r) for r in manual.get("conditions") or []]
    runs = [r["data"] for r in folder_result["runs"]]
    if runs:
        datasets = {d.get("dataset_version") for d in runs}
        eval_sets = {str(v).removesuffix("-dev") for v in datasets}
        model = _joined(d.get("model") for d in runs)
        tokens = _joined(f"max_new_tokens={(d.get('config') or {}).get('max_new_tokens')}" for d in runs)
        ns = sorted({(d.get("metrics") or {}).get("n") for d in runs}, key=str)
        rows += [
            ("코드", f"{_joined((d.get('config') or {}).get('code_version') for d in runs)}"
                     " (결과 JSON의 `config.code_version`)"),
            ("평가셋", f"{_joined(eval_sets)} (결과 JSON의 `dataset_version`: {_joined(datasets)})"),
            ("모델", model + (f", {manual['model_note']}" if manual.get("model_note") else "")),
            ("생성 설정", tokens + (f", {manual['generation_note']}" if manual.get("generation_note") else "")),
            ("문항", f"DEV {', '.join(map(str, ns))}문항"
                     + (f" ({manual['questions_note']})" if manual.get("questions_note") else "")),
        ]
    if rows:
        ui.show(ui.kv_table_html("실험 조건", rows))


def render_placeholder(spec, content, folder_result, stages):
    """아직 만들지 않은 탭: 글과 그래프 자리만."""
    tab_top(content, folder_result)
    for chart_id in spec["charts"]:
        chart_panel(content, chart_id)
    with st.expander("실험 기록 보기"):
        st.caption("📊 결과 표는 탭별 단계에서 붙여요")
        record_boxes(spec, content)


# ---------- ② 응답 시간 ----------

def time_rows(folder_result, stages):
    """dev 결과 -> 단계별 값 (카드 · 그래프 · 표가 같은 값을 쓴다)."""
    rows = []
    for run in folder_result["runs"]:
        d = run["data"]
        rows.append({
            "stage": run["key"], "change": (stages.get(run["key"]) or {}).get("change"),
            "f1": metric(d, "macro_f1"), "empty": metric(d, "empty_answers"),
            "avg": metric(d, "avg_seconds"), "median": loader.median_seconds(d), "max": metric(d, "max_seconds"),
            "type_avg": {t: metric(d, "avg_seconds", t) for t in loader.TYPES},
            "n": metric(d, "n"),
        })
    return rows


def render_response_time(spec, content, folder_result, stages):
    tab_top(content, folder_result)
    rows = time_rows(folder_result, stages)
    if not rows:
        st.info("dev 폴더에 쓸 수 있는 결과 파일이 없어요.")
        return
    first, last = rows[0], rows[-1]

    # 숫자 카드: 마지막 단계 기준, 첫 단계 대비 변화 (시간·빈 답은 줄어야 좋아짐)
    cards = []
    for label, key, unit, higher in (("평균", "avg", "초", False), ("중앙값", "median", "초", False),
                                     ("최대", "max", "초", False), ("Macro F1", "f1", "", True),
                                     ("빈 답", "empty", "개", False)):
        cards.append({"label": label, "value": fmt(last[key]), "unit": unit,
                      "delta": ui.delta(last[key], first[key], higher_is_better=higher, unit=unit)})
    ui.show(ui.cards_html(cards, note=ui.delta_note_html(last["stage"], first["stage"])))

    gray = [("평균", ui.COLOR["avg"], "square", None), ("중앙값", ui.COLOR["median"], "square", None)]
    types = [(ui.TYPE_LABEL[t], ui.COLOR[t], "square", None) for t in ("lookup", "filter")]
    r_value = loader.pearson_r([r["empty"] for r in rows], [r["avg"] for r in rows])
    chart_panel(content, "c2a", charts.f1_and_time(rows), legend=gray)
    chart_panel(content, "c2b", charts.empty_vs_time(rows, r_value, first["n"]))
    chart_panel(content, "c2c", charts.time_by_type(rows), legend=types)

    with st.expander("실험 기록 보기"):
        conditions_box(content, folder_result)
        table = [[r["stage"], f"{fmt(r['avg'])}초", f"{fmt(r['median'])}초", f"{fmt(r['max'])}초",
                  fmt(r["f1"]), f"{fmt(r['empty'])}개"] for r in rows]
        ui.show(ui.result_table_html(["단계", "평균", "중앙값", "최대", "Macro F1", "빈 답"], table,
                                     highlight=len(rows) - 1, widths={0: "90px"}))
        record_boxes(spec, content)


# ---------- ③ 보조 지표 ----------

def aux_rows(folder_result, stages):
    """aux 결과 -> 단계별 값 (카드 · 그래프 · 표가 같은 값을 쓴다)."""
    rows = []
    for run in folder_result["runs"]:
        d = run["data"]
        rows.append({
            "stage": run["key"], "change": (stages.get(run["key"]) or {}).get("change"),
            "acc": metric(d, "accuracy"), "ref": metric(d, "refusal_accuracy"), "hal": metric(d, "hallucination_rate"),
            "answered": metric(d, "answered"), "hn": metric(d, "hallucinated_questions"), "n": metric(d, "n"),
            "types": loader.hallucinations_by_type(d),   # 목록이 없으면 None -> '유형 구분 없음'
        })
    return rows


AUX_DEF_KEY = {"acc": "accuracy", "ref": "refusal_accuracy", "hal": "hallucination_rate"}   # aux.yaml definitions


def render_aux(spec, content, folder_result, stages):
    tab_top(content, folder_result)
    rows = aux_rows(folder_result, stages)
    if not rows:
        st.info("aux 폴더에 쓸 수 있는 결과 파일이 없어요.")
        return
    first, last = rows[0], rows[-1]
    defs = content.get("definitions") or {}

    cards = []
    for key, label, higher in (("acc", "정답률", True), ("ref", "거절 정확도", True), ("hal", "환각률", False)):
        cards.append({"label": label, "value": fmt(last[key]), "unit": "",
                      "delta": ui.delta(last[key], first[key], higher_is_better=higher)})
    ui.show(ui.cards_html(cards, note=ui.delta_note_html(last["stage"], first["stage"])))

    rate_legend = [(name, color, "line", defs.get(AUX_DEF_KEY[k])) for k, name, color in charts.AUX_SERIES]
    stack_legend = [("근거 안에서 답함", ui.COLOR["unknown"], "square", None), ("환각 포함", ui.COLOR["filter"], "square", None)]
    type_legend = [(ui.TYPE_LABEL[t], ui.COLOR[t], "square", None) for t in loader.TYPES]
    if any(r["types"] is None for r in rows):
        type_legend.append(("유형 구분 없음", "transparent", "dashed", None))
    chart_panel(content, "c3a", charts.aux_rates(rows), legend=rate_legend)
    chart_panel(content, "c3b", charts.answered_stack(rows), legend=stack_legend,
                note=f"· 막대 전체 = 답한 문항 수 ({first['n']}문항 중, 빈 답 제외)")
    chart_panel(content, "c3c", charts.hal_by_type(rows), legend=type_legend)

    with st.expander("실험 기록 보기"):
        table = [[r["stage"], fmt(r["acc"]), fmt(r["ref"]), fmt(r["hal"]), f"{fmt(r['hn'])} / {fmt(r['answered'])}"]
                 for r in rows]
        def_lines = [f"{name}: {defs[AUX_DEF_KEY[k]]}" for k, name, _ in charts.AUX_SERIES if defs.get(AUX_DEF_KEY[k])]
        ui.show(ui.result_table_html(["단계", "정답률", "거절 정확도", "환각률", "환각 / 답한 문항"], table,
                                     highlight=len(rows) - 1, widths={0: "90px"}, defs=def_lines))
        record_boxes(spec, content)


# ---------- ④ 모델 비교 ----------

def model_rows(folder_result, content):
    """model_compare 결과 -> 조합별 값 (key 순서 = 모델 크기 → GPU → 정밀도)."""
    manual = content.get("manual") or {}
    memory = manual.get("gpu_memory") or {}
    colors = {k: (v or {}).get("color") for k, v in (content.get("models") or {}).items()}
    rows = []
    for run in folder_result["runs"]:
        d, m = run["data"], run["model"]
        if not m:
            continue
        rows.append({
            "size": m["size"], "gpu": m["gpu"], "precision": m["precision"], "label": loader.model_label(run),
            "f1": metric(d, "macro_f1"), "lookup": metric(d, "macro_f1", "lookup"), "filter": metric(d, "macro_f1", "filter"),
            "avg": metric(d, "avg_seconds"), "median": loader.median_seconds(d),
            "lookup_t": metric(d, "avg_seconds", "lookup"), "filter_t": metric(d, "avg_seconds", "filter"),
            "precision_v": metric(d, "micro_precision"), "recall": metric(d, "micro_recall"),
            "ans_len": loader.avg_answer_len(d, "filter"),
            "memory": memory.get(m["size"]), "color": colors.get(m["size"]) or ui.COLOR["avg"],
        })
    return rows


def render_model_compare(spec, content, folder_result, stages):
    tab_top(content, folder_result)
    rows = model_rows(folder_result, content)
    if not rows:
        st.info("model_compare 폴더에 쓸 수 있는 결과 파일이 없어요.")
        return
    setup = content.get("baseline_setup") or {"gpu": "L4", "precision": "fp16"}
    base = [r for r in rows if r["gpu"] == str(setup.get("gpu")).upper() and r["precision"] == str(setup.get("precision")).lower()]

    # 1위 카드 (기준 조합 안에서, 소수 3자리로 같으면 공동 1위)
    cards = []
    for label, key, higher, unit in (("Macro F1", "f1", True, "점(F1)"), ("조건 검색", "filter", True, "점(F1)"),
                                     ("캐릭터 조회", "lookup", True, "점(F1)"), ("평균 응답", "avg", False, "초")):
        names, value = loader.best_of([(r["size"], r[key]) for r in base], higher=higher)
        if names:
            cards.append({"label": label, "medal": " · ".join(names), "value_text": f"{fmt(value)}{unit}"})
    if cards:
        ui.show(ui.cards_html(cards))

    tips = (content.get("charts") or {}).get("c4b", {}).get("tips") or {}
    f1_legend = [(name, color, "square", None) for _, name, color in charts.F1_SERIES]
    pr_legend = [("정밀도", charts.PREC_COLOR, "dot", tips.get("precision")),
                 ("재현율", charts.RECALL_COLOR, "dot", tips.get("recall")),
                 ("평균 답 길이", ui.COLOR["avg"], "square", tips.get("answer_len"))]
    time_legend = [("전체 평균", ui.COLOR["avg"], "line", None), ("캐릭터 조회", ui.COLOR["lookup"], "line", None),
                   ("조건 검색", ui.COLOR["filter"], "line", None)]
    if base:
        chart_panel(content, "c4a", charts.model_f1(base), legend=f1_legend)
        chart_panel(content, "c4b", charts.precision_recall(base), legend=pr_legend)
        chart_panel(content, "c4c", charts.model_time(base), legend=time_legend)
    chart_panel(content, "c4d", charts.combo_bars(rows, "f1", tickvals=[0, 0.25, 0.5, 0.75, 1], axis_title="Macro F1"))
    top_t = max(r["avg"] or 0 for r in rows)
    t_ticks = list(range(0, int(top_t) + 2, 2 if top_t > 6 else 1))
    chart_panel(content, "c4e", charts.combo_bars(rows, "avg", unit="초", tickvals=t_ticks, axis_title="평균 응답 시간"))

    with st.expander("실험 기록 보기"):
        pick = str(content.get("highlight_model") or "")
        table = [[r["size"], f"{r['gpu']} · {r['precision']}", fmt(r["f1"]), fmt(r["lookup"]), fmt(r["filter"]),
                  f"{fmt(r['avg'])}초"] for r in rows]
        ui.show(ui.result_table_html(["모델", "GPU · 정밀도", "Macro F1", "캐릭터 조회", "조건 검색", "평균 응답"], table,
                                     highlight=[i for i, r in enumerate(rows) if r["size"] == pick], widths={0: "70px"}))
        record_boxes(spec, content)


# ---------- ① 성능 변화 ----------

def perf_rows(folder_result, stages):
    """official 결과 -> 단계별 Macro F1 (전체 + 유형별) + 유형별 문항 수."""
    rows = []
    for run in folder_result["runs"]:
        d = run["data"]
        row = {"stage": run["key"], "change": (stages.get(run["key"]) or {}).get("change"),
               "f1": metric(d, "macro_f1"), "n": metric(d, "n")}
        for t in loader.TYPES:
            row[t] = metric(d, "macro_f1", t)
            row[f"n_{t}"] = ((d.get("by_type") or {}).get(t) or {}).get("n")
        rows.append(row)
    return rows


def render_performance(spec, content, folder_result, stages):
    tab_top(content, folder_result)
    rows = perf_rows(folder_result, stages)
    if not rows:
        st.info("official 폴더에 쓸 수 있는 결과 파일이 없어요.")
        return
    last = rows[-1]

    # 숫자 카드: 마지막 단계의 전체 · 유형별 점수 + 문항 수 (와이어프레임: 왼쪽 색 테두리)
    cards = [{"label": name, "value": fmt(last[k]), "color": color,
              "caption": f"{fmt(last['n'] if k == 'f1' else last[f'n_{k}'])}문항"} for k, name, color in charts.PERF_SERIES]
    ui.show(ui.cards_html(cards))

    legend = [(name, color, "line", None) for _, name, color in charts.PERF_SERIES]
    chart_panel(content, "c1a", charts.perf_lines(rows), legend=legend)

    with st.expander("실험 기록 보기"):
        table = [[r["stage"]] + [str((stages.get(r["stage"]) or {}).get(f) or "—") for f in ("change", "learned", "problem")]
                 for r in rows]
        ui.show(ui.result_table_html(["단계", "개선점", "알게 된 것", "문제점"], table,
                                     highlight=len(rows) - 1, widths={0: "90px"}))
        record_boxes(spec, content)


RENDERERS = {"performance": render_performance, "response_time": render_response_time, "aux": render_aux,
             "model_compare": render_model_compare}


def render_tab(spec, content, folder_result, stages):
    RENDERERS.get(spec["content"], render_placeholder)(spec, content, folder_result, stages)


# ---------- 화면 ----------

def main():
    st.set_page_config(page_title=TITLE, page_icon="📊", layout="centered")
    st.markdown(ui.CSS, unsafe_allow_html=True)
    st.html(ui.TIP_SCRIPT, unsafe_allow_javascript=True)   # 마우스를 따라다니는 그래프 툴팁 (lib/ui.py)

    order = text.stage_order()
    results = loader.load_all(order=order)
    contents = {t["content"]: text.load_content(t["content"]) for t in TABS}
    stages = text.load_content("stages").get("stages") or {}

    versions = sorted({str(r["data"].get("dataset_version")) for r in results["official"]["runs"]})
    data_version = (contents["performance"].get("header") or {}).get("data_version")
    meta = f"평가셋 {', '.join(versions) or '결과 없음'}" + (f" · {data_version}" if data_version else "")

    selected = st.session_state.get("tab", 0)
    spec = TABS[selected]
    content = contents[spec["content"]]
    with st.container(key="dk"):   # 대시보드 전체 상자 (와이어프레임 .dk)
        ui.show(ui.header_html(TITLE, meta, cond=content.get("cond")))   # 조건 칩은 지금 탭 것
        tab_bar(selected)
        render_tab(spec, content, results[spec["folder"]], stages)


main()
