"""Plotly 그래프 함수 (와이어프레임 색 · 다크 배경). 값은 이미 계산된 것을 받고, go.Figure만 돌려준다.

- 툴팁의 점수·시간은 <b>굵게</b>, 툴팁 맨 아래에 stages.yaml의 개선점.
- 범례는 그래프 밖(ui.legend_html)에 HTML로 둔다 -> Plotly 범례는 끈다.
- 색이 비슷한 쌍(회색 두 개 등)은 막대·점마다 숫자 라벨을 붙여 색만으로 구분하지 않게 한다.
- y축 두 개를 한 그래프에 겹치지 않는다. 단위가 다르면 위아래 칸(y축 domain)으로 나눈다.
"""
import html

import plotly.graph_objects as go

from .loader import fmt
from .ui import COLOR

INK = "#B4B2A9"        # 축 글자
MUTED = "#6E6D68"      # 축 제목
GRID = "#2E2E2C"
LABEL = "#D3D1C7"      # 막대·점 위 숫자
HIGHLIGHT = "#AFA9EC"  # 마지막 단계 강조 점
FONT = '-apple-system, BlinkMacSystemFont, "Apple SD Gothic Neo", "Noto Sans KR", sans-serif'
CONFIG = {"displayModeBar": False}   # st.plotly_chart(config=...) 용


Y_LABEL_GAP = 8                         # y축 숫자 오른쪽(그래프 박스와의) 여백 (px)
Y_TITLE_PAD = 8                         # y축 제목이 왼쪽으로 더 가는 만큼 왼쪽 여백을 더 준다 (px)
Y_TITLE_GAP = 12                        # y축 숫자 ↔ y축 제목 간격 (title_standoff, px)
X_LABEL_GAP = 15                        # x축 범주명(단계 이름·숫자) 위 여백 (px)
X_TITLE_GAP = 15                        # x축 이름('개선 단계' 등) 위 여백 = 범주명과의 간격 (px)
MARGIN = dict(l=60, r=16, t=12, b=34 + X_LABEL_GAP + X_TITLE_GAP)   # 그래프마다 같게 -> 막대 너비가 같아진다 (b: x축 이름까지)
BARGAP = 0.55                           # 막대 묶음 사이 빈칸 비율 (클수록 막대가 좁다)


def _layout(fig, height):
    """공통 모양: 바탕은 투명(둥근 회색 패널이 비쳐 보임), 눈금선·눈금 숫자 없음 (값은 막대·점 라벨로)."""
    fig.update_layout(
        height=height, margin=MARGIN,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=FONT, size=12, color=INK), showlegend=False,
        hoverlabel=dict(bgcolor="#2C2C2A", bordercolor="#2C2C2A", font=dict(family=FONT, size=12, color=LABEL),
                        align="left", showarrow=False),
        bargap=BARGAP, bargroupgap=0.08,
    )
    # x축 범주명(단계 이름·숫자)은 그래프 박스에서 15px 띄운다
    fig.update_xaxes(showgrid=False, zeroline=False, linecolor="#3A3A38", tickfont=dict(size=12, color=INK), fixedrange=True,
                     ticklabelstandoff=X_LABEL_GAP)
    # y축 숫자는 그래프 박스에서 8px 띄운다 (숫자를 켜는 그래프에만 보임. 범주명 y축은 각 함수에서 따로 정함)
    fig.update_yaxes(showgrid=False, showticklabels=False, zeroline=False, showline=False, ticklabelstandoff=Y_LABEL_GAP,
                     tickfont=dict(size=11, color="#888780"), title_font=dict(size=11, color=MUTED), fixedrange=True)
    return fig


PLOT_W = 800          # 그래프 안쪽 너비 어림값 (둥근 박스 모서리 계산용, 화면이 좁아도 모서리가 조금 찌그러질 뿐)
BOX_BG = "#262624"    # 그래프 영역 박스 색 (패널 #202020보다 조금 밝게)


def round_box(fig, yref, h_px, w_px=PLOT_W, r_px=8, color=BOX_BG, xref="paper"):
    """그래프 영역 뒤에 둥근 박스를 깐다. xref='paper' 또는 'x domain' 등, yref='y domain' 등 (모두 0~1).
    Plotly 도형은 모서리 둥글기 설정이 없어서 SVG 경로(Q 곡선)로 그린다. w_px·h_px는 박스의 실제 크기(px) 어림값."""
    rx, ry = r_px / w_px, r_px / h_px
    path = (f"M {rx},0 L {1 - rx},0 Q 1,0 1,{ry} L 1,{1 - ry} Q 1,1 {1 - rx},1 "
            f"L {rx},1 Q 0,1 0,{1 - ry} L 0,{ry} Q 0,0 {rx},0 Z")
    fig.add_shape(type="path", path=path, xref=xref, yref=yref, layer="below",
                  fillcolor=color, line=dict(width=0))


# ---------- 툴팁 ----------
# 툴팁은 두 가지를 같이 만든다.
#  - customdata: 우리 HTML 툴팁 (ui.TIP_SCRIPT가 마우스 옆에 띄움. 테두리·구분선·위치 자동 조정)
#  - hovertext : Plotly 기본 툴팁 (스크립트가 안 돌 때만 보임. 스크립트가 돌면 CSS로 숨김)
# 툴팁의 첫 줄은 제목(단계 이름), footer는 구분선 아래 줄(개선점).

def tip(lines, footer=None):
    """Plotly 기본 툴팁 글 (예비용)."""
    return "<br>".join(list(lines) + ([footer] if footer else []))


def tip_html(lines, footer=None):
    """우리 HTML 툴팁 (와이어프레임 #tip): 제목 / 값 줄들 / 구분선 + 개선점. 숫자는 <b>로 흰색 굵게."""
    head, *rest = lines
    out = f'<div class="h">{head}</div>' + "".join(f"<div>{x}</div>" for x in rest)
    return out + (f'<div class="c">{footer}</div>' if footer else "")


def hover(parts_list):
    """trace에 넣을 툴팁 설정. parts_list = [(lines, footer), ...] 점마다 하나."""
    return dict(hovertext=[tip(*p) for p in parts_list], customdata=[tip_html(*p) for p in parts_list],
                hovertemplate="%{hovertext}<extra></extra>")


# ---------- ② 응답 시간 ----------

def time_tip_parts(r):
    """② 툴팁 내용 (lines, footer). 단계 이름·개선점은 사람이 쓴 글이라 이스케이프한다."""
    lines = [f"<b>{html.escape(str(r['stage']))}</b>",
             f"Macro F1 <b>{fmt(r['f1'])}</b> · 빈 답 <b>{fmt(r['empty'])}개</b>",
             f"평균 <b>{fmt(r['avg'])}초</b> · 중앙값 <b>{fmt(r['median'])}초</b> · 최대 <b>{fmt(r['max'])}초</b>"]
    return lines, (f"개선점: {html.escape(str(r['change']))}" if r.get("change") else None)


def time_tip(r):
    return tip(*time_tip_parts(r))


F1_DOMAIN = [0.58, 1.0]     # c2a 위 칸 (Macro F1)
TIME_DOMAIN = [0.0, 0.5]    # c2a 아래 칸 (응답 시간)
C2A_HEIGHT = 360


def f1_and_time(rows):
    """c2a: 위 칸 Macro F1 꺾은선, 아래 칸 평균·중앙값 응답 시간 막대.
    - x축 하나를 두 칸이 같이 쓴다 -> 어디에 마우스를 올려도 점선 하나가 두 칸을 지나고 툴팁은 하나만 뜬다
      (hovermode='x' + hoversubplots='axis', 툴팁은 꺾은선에만 달고 막대는 건너뜀).
    - 칸 구분은 선이 아니라 둥근 박스 두 개."""
    x = [r["stage"] for r in rows]
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=x, y=[r["f1"] for r in rows], yaxis="y", mode="lines+markers+text",
        line=dict(color=COLOR["all"], width=2.5), marker=dict(size=9, color=COLOR["all"], line=dict(color=BOX_BG, width=2)),
        text=[fmt(r["f1"]) for r in rows], textposition="top center", textfont=dict(size=11, color=LABEL),
        cliponaxis=False, **hover([time_tip_parts(r) for r in rows])))
    for key, color in (("avg", COLOR["avg"]), ("median", COLOR["median"])):
        fig.add_trace(go.Bar(
            x=x, y=[r[key] for r in rows], yaxis="y2", marker=dict(color=color, cornerradius=3),
            text=[fmt(r[key]) for r in rows], textposition="outside", textfont=dict(size=10, color=LABEL),
            hoverinfo="skip", cliponaxis=False))
    _layout(fig, C2A_HEIGHT)
    top = max(r["avg"] for r in rows)
    fig.update_layout(
        hovermode="x", hoversubplots="axis", hoverdistance=-1,   # 어디에 올려도 가장 가까운 단계
        meta={"spike": True},   # 세로 기준 점선은 ui.TIP_SCRIPT가 두 박스를 가로질러 직접 그린다 (Plotly 점선은 끔)
        xaxis=dict(anchor="y2", showline=False, showspikes=False, title_text="개선 단계",
                   title_font=dict(size=11, color=MUTED), title_standoff=X_TITLE_GAP),
        yaxis=dict(domain=F1_DOMAIN, title_text="Macro F1", range=[-0.1, 1.2]),
        yaxis2=dict(domain=TIME_DOMAIN, anchor="x", title_text="응답 시간 (초)", range=[0, top * 1.3]),
    )
    fig.update_yaxes(showgrid=False, showticklabels=False, zeroline=False, showline=False,
                     title_font=dict(size=11, color=MUTED), fixedrange=True)
    inner_h = C2A_HEIGHT - MARGIN["t"] - MARGIN["b"]
    round_box(fig, "y domain", inner_h * (F1_DOMAIN[1] - F1_DOMAIN[0]))
    round_box(fig, "y2 domain", inner_h * (TIME_DOMAIN[1] - TIME_DOMAIN[0]))
    return fig


def trend_line(xs, ys):
    """최소제곱 직선 (기울기, 절편)."""
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx if sxx else 0.0
    return slope, my - slope * mx


def empty_vs_time(rows, r_value, n_questions):
    """c2b: 빈 답 수 × 평균 응답 시간 산점도 + 추세선 + 상관계수."""
    xs = [r["empty"] for r in rows]
    ys = [r["avg"] for r in rows]
    last = len(rows) - 1
    fig = go.Figure()
    if len(rows) >= 2:
        slope, icpt = trend_line(xs, ys)
        x0, x1 = min(xs), max(xs)
        fig.add_trace(go.Scatter(x=[x0, x1], y=[slope * x0 + icpt, slope * x1 + icpt], mode="lines",
                                 line=dict(color="#5F5E5A", width=1, dash="dash"), hoverinfo="skip"))
    fig.add_trace(go.Scatter(
        x=xs, y=ys, mode="markers+text", text=[r["stage"] for r in rows], textposition="middle right",
        textfont=dict(size=12, color=[("#F1EFE8" if i == last else INK) for i in range(len(rows))]),
        marker=dict(size=[13 if i == last else 11 for i in range(len(rows))],
                    color=[HIGHLIGHT if i == last else COLOR["avg"] for i in range(len(rows))],
                    line=dict(color=BOX_BG, width=2)),
        cliponaxis=False, **hover([time_tip_parts(r) for r in rows])))
    _layout(fig, 280)
    fig.update_xaxes(showline=False)   # 테두리 선 대신 둥근 박스
    round_box(fig, "paper", 280 - MARGIN["t"] - MARGIN["b"], w_px=PLOT_W - 18)
    if r_value is not None:
        fig.add_annotation(xref="paper", yref="paper", x=0.99, y=0.97, xanchor="right", yanchor="top", showarrow=False,
                           text=f"r ≈ {fmt(r_value)} ({len(rows)}개 단계)", font=dict(size=11, color="#9C9A92"))
    # 가로축은 0에서 시작(그래프 맨 왼쪽), 세로 눈금선 없음. 가로 눈금선과 y 숫자는 남긴다 (점에 시간 라벨이 없어서)
    fig.update_xaxes(title_text=f"빈 답 (개, {n_questions}문항 중)", title_font=dict(size=11, color=MUTED), title_standoff=X_TITLE_GAP,
                     range=[0, n_questions], showgrid=False)
    fig.update_yaxes(title_text="평균 응답 시간 (초)", range=[min(ys) * 0.8, max(ys) * 1.12], title_standoff=12 + 8,
                     showgrid=True, gridcolor=GRID, gridwidth=0.5, showticklabels=True, ticksuffix="초")
    fig.update_layout(margin=dict(MARGIN, l=78 + Y_TITLE_PAD))   # y 숫자('2.5초')와 축 제목 사이 여백
    return fig


def time_by_type(rows, types=("lookup", "filter")):
    """c2c: 단계 × 질문 유형별 평균 응답 시간 묶음 막대."""
    from .ui import TYPE_LABEL
    x = [r["stage"] for r in rows]
    fig = go.Figure()
    for t in types:
        fig.add_trace(go.Bar(
            x=x, y=[r["type_avg"].get(t) for r in rows], marker=dict(color=COLOR[t], cornerradius=3),
            text=[fmt(r["type_avg"].get(t)) for r in rows], textposition="outside", textfont=dict(size=10, color=LABEL),
            cliponaxis=False, **hover([([f"<b>{html.escape(str(r['stage']))}</b> · {TYPE_LABEL[t]}",
                                         f"평균 <b>{fmt(r['type_avg'].get(t))}초</b>"], None) for r in rows])))
    _layout(fig, 250)
    top = max((r["type_avg"].get(t) or 0) for r in rows for t in types)
    fig.update_layout(barmode="group", margin=dict(MARGIN, b=24 + X_LABEL_GAP))   # x축 이름이 없어서 아래 여백을 줄임
    # y축: 제목 없이 '1초, 2초…' 숫자 + 가로 눈금선
    fig.update_yaxes(range=[0, top * 1.2], showticklabels=True, ticksuffix="초",
                     showgrid=True, gridcolor=GRID, gridwidth=0.5)
    return fig


# ---------- ③ 보조 지표 ----------
# 비율 세 개: 키, 이름, 색 (점은 모두 동그라미. 색이 비슷한 주황·초록은 툴팁의 이름·숫자로 구분)
AUX_SERIES = [("acc", "정답률", COLOR["all"]),
              ("ref", "거절 정확도", COLOR["unknown"]),
              ("hal", "환각률", COLOR["filter"])]
SINGLE_BAR_W = 0.21   # 막대 하나짜리 그래프의 막대 너비 (②의 묶음 막대 한 개 너비와 비슷하게)


def dot(color):
    """툴팁 안의 색 점 (ui.CSS #gd-tip .d)."""
    return f'<span class="d" style="background:{color}"></span>'


def _esc(value):
    return html.escape(str(value))


def aux_tip_parts(r):
    """c3a 툴팁: 비율 세 개 + 환각 건수 / 답한 문항, 개선점."""
    lines = [f"<b>{_esc(r['stage'])}</b>"]
    lines += [f"{dot(c)}{name} <b>{fmt(r[k])}</b>" for k, name, c in AUX_SERIES]
    lines.append(f"환각 <b>{fmt(r['hn'])}건</b> / 답한 문항 <b>{fmt(r['answered'])}개</b>")
    return lines, (f"개선점: {_esc(r['change'])}" if r.get("change") else None)


def aux_rates(rows):
    """c3a: 단계별 정답률 · 거절 정확도 · 환각률 꺾은선 (0~1, 같은 축). 점선·툴팁은 ②와 같은 방식."""
    x = [r["stage"] for r in rows]
    fig = go.Figure()
    for i, (k, name, color) in enumerate(AUX_SERIES):
        extra = hover([aux_tip_parts(r) for r in rows]) if i == 0 else dict(hoverinfo="skip")
        fig.add_trace(go.Scatter(
            x=x, y=[r[k] for r in rows], mode="lines+markers", name=name,
            line=dict(color=color, width=2.5),
            marker=dict(size=9, color=color, line=dict(color=BOX_BG, width=1.5)),
            cliponaxis=False, **extra))
    height = 290
    _layout(fig, height)
    fig.update_layout(hovermode="x", hoverdistance=-1, meta={"spike": True})
    fig.update_xaxes(showline=False, title_text="개선 단계", title_font=dict(size=11, color=MUTED),
                     title_standoff=X_TITLE_GAP)
    # 점에 숫자 라벨이 없어서 y 숫자(0, 0.5, 1)와 가로 눈금선을 남긴다
    fig.update_yaxes(title_text="비율 (0~1)", title_standoff=Y_TITLE_GAP, range=[-0.06, 1.08], tickvals=[0, 0.5, 1], showticklabels=True,
                     showgrid=True, gridcolor=GRID, gridwidth=0.5)
    fig.update_layout(margin=dict(MARGIN, l=MARGIN["l"] + Y_TITLE_PAD))   # y 숫자와 축 제목 사이 여백
    round_box(fig, "paper", height - MARGIN["t"] - MARGIN["b"])
    return fig


def answered_tip_parts(r):
    lines = [f"<b>{_esc(r['stage'])}</b>",
             f"답한 문항 <b>{fmt(r['answered'])}개</b> · 빈 답 <b>{fmt(r['n'] - r['answered'])}개</b>",
             f"{dot(COLOR['filter'])}환각 포함 <b>{fmt(r['hn'])}건</b>",
             f"{dot(COLOR['unknown'])}근거 안에서 답함 <b>{fmt(r['answered'] - r['hn'])}건</b>"]
    return lines, (f"개선점: {_esc(r['change'])}" if r.get("change") else None)


def answered_stack(rows):
    """c3b: 단계별 답한 문항 수 쌓은 막대 = 근거 안에서 답함(초록) + 환각 포함(주황). 위에 '환각 / 답한 문항'."""
    x = [r["stage"] for r in rows]
    tips = hover([answered_tip_parts(r) for r in rows])
    n = max(r["n"] for r in rows)
    fig = go.Figure()
    fig.add_trace(go.Bar(x=x, y=[r["answered"] - r["hn"] for r in rows], name="근거 안에서 답함", width=SINGLE_BAR_W,
                         marker=dict(color=COLOR["unknown"]), **tips))
    fig.add_trace(go.Bar(x=x, y=[r["hn"] for r in rows], name="환각 포함", width=SINGLE_BAR_W,
                         marker=dict(color=COLOR["filter"], cornerradius=3),
                         text=[f"{fmt(r['hn'])} / {fmt(r['answered'])}" for r in rows], textposition="outside",
                         textfont=dict(size=11, color=LABEL), cliponaxis=False, **tips))
    height = 270
    _layout(fig, height)
    fig.update_layout(barmode="stack", hovermode="x", hoverdistance=-1)
    fig.update_xaxes(showline=False, title_text="개선 단계", title_font=dict(size=11, color=MUTED),
                     title_standoff=X_TITLE_GAP)
    fig.update_yaxes(title_text="문항 수", title_standoff=Y_TITLE_GAP + 2, range=[0, n * 1.15], tickvals=[0, 20, 40, 60] if n == 60 else None,
                     showticklabels=True, showgrid=True, gridcolor=GRID, gridwidth=0.5)
    fig.update_layout(margin=dict(MARGIN, l=MARGIN["l"] + Y_TITLE_PAD))   # y 숫자와 축 제목 사이 여백
    round_box(fig, "paper", height - MARGIN["t"] - MARGIN["b"])
    return fig


def hal_tip_parts(r):
    from .ui import TYPE_LABEL
    lines = [f"<b>{_esc(r['stage'])}</b>",
             f"환각률 <b>{fmt(r['hal'])}</b> ({fmt(r['hn'])}건 / 답한 {fmt(r['answered'])}개)"]
    if r["types"] is None:
        lines.append("유형별 내역 없음")
    else:
        lines += [f"{dot(COLOR[t])}{TYPE_LABEL[t]} <b>{v}건</b>" for t, v in r["types"].items() if v and t in TYPE_LABEL]
        if r["types"].get("other"):
            lines.append(f"기타 <b>{r['types']['other']}건</b>")
    return lines, None


def hal_by_type(rows, types=("lookup", "filter", "unknown")):
    """c3c: 단계별 환각률 가로 막대. 막대 길이 = 환각률, 색 칸 = 질문 유형별 건수 비율.
    hallucinations 목록이 없는 단계(types=None)는 점선 테두리 '유형 구분 없음'."""
    from .ui import TYPE_LABEL
    y = [r["stage"] for r in rows]
    fig = go.Figure()
    for t in types:
        xs = []
        for r in rows:
            total = sum((r["types"] or {}).values())
            xs.append(r["hal"] * r["types"][t] / total if r["types"] and total else 0)
        fig.add_trace(go.Bar(y=y, x=xs, orientation="h", name=TYPE_LABEL[t], width=0.56,
                             marker=dict(color=COLOR[t], line=dict(color=BOX_BG, width=2)), hoverinfo="skip"))   # 칸 사이 2px 틈
    # 끝의 환각률 숫자 + 툴팁 (보이지 않는 점: 줄 어디에 올려도 그 단계 툴팁)
    fig.add_trace(go.Scatter(y=y, x=[r["hal"] for r in rows], mode="markers+text", marker=dict(size=1, opacity=0),
                             text=[f"  <b>{fmt(r['hal'])}</b>" for r in rows], textposition="middle right",
                             textfont=dict(size=12, color="#F1EFE8"), cliponaxis=False,
                             **hover([hal_tip_parts(r) for r in rows])))
    for i, r in enumerate(rows):
        if r["types"] is None:
            fig.add_shape(type="rect", x0=0, x1=r["hal"], y0=i - 0.28, y1=i + 0.28, xref="x", yref="y",
                          line=dict(color="#6E6D68", width=1, dash="dot"), fillcolor="rgba(0,0,0,0)")
    height = 64 + 38 * len(rows) + X_LABEL_GAP + X_TITLE_GAP
    _layout(fig, height)
    fig.update_layout(barmode="stack", hovermode="y", hoverdistance=-1, margin=dict(MARGIN, l=90, r=40))
    fig.update_xaxes(showline=False, range=[0, 1], tickvals=[0, 0.25, 0.5, 0.75, 1], showgrid=True,
                     gridcolor=GRID, gridwidth=0.5, title_text="환각률", title_font=dict(size=11, color=MUTED),
                     title_standoff=X_TITLE_GAP, tickfont=dict(size=11, color="#888780"))
    fig.update_yaxes(autorange="reversed", showticklabels=True, tickfont=dict(size=12, color=LABEL),
                     ticklabelstandoff=10)
    round_box(fig, "paper", height - MARGIN["t"] - MARGIN["b"], w_px=PLOT_W - 54)
    return fig


# ---------- ④ 모델 비교 ----------
# rows = [{size, gpu, precision, label('1.5B · L4 · fp16'), f1, lookup, filter, avg, median, t_lookup, t_filter,
#          precision_v, recall, ans_len, memory, color}]  (app.model_rows가 만든다)
F1_SERIES = [("f1", "전체", COLOR["all"]), ("lookup", "캐릭터 조회", COLOR["lookup"]), ("filter", "조건 검색", COLOR["filter"])]
PREC_COLOR, RECALL_COLOR = "#AFA9EC", "#5DCAA5"   # 와이어프레임 c4b


def _model_head(r):
    return f"<b>Qwen2.5-{_esc(r['size'])} · {_esc(r['gpu'])} · {_esc(r['precision'])}</b>"


def _size_ticks(rows):
    """x축 범주명: 모델 크기(굵게) + 그 아래 GPU 메모리(작게)."""
    out = []
    for r in rows:
        mem = f"<br><span style='font-size:10px;color:#888780'>메모리 {_esc(r['memory'])}</span>" if r.get("memory") else ""
        out.append(f"<b>{_esc(r['size'])}</b>{mem}")
    return out


def model_f1(rows):
    """c4a: 모델 크기별 묶음 막대 (전체 · 캐릭터 조회 · 조건 검색 Macro F1). rows는 기준 조합(L4·fp16)만."""
    x = [r["size"] for r in rows]
    tips = []
    for r in rows:
        lines = [_model_head(r)] + [f"{dot(c)}{name} <b>{fmt(r[k])}</b>" for k, name, c in F1_SERIES]
        mem = f" · GPU 메모리 <b>{_esc(r['memory'])}</b>" if r.get("memory") else ""
        lines.append(f"평균 응답 <b>{fmt(r['avg'])}초</b>{mem}")
        tips.append((lines, None))
    fig = go.Figure()
    for k, name, color in F1_SERIES:
        fig.add_trace(go.Bar(x=x, y=[r[k] for r in rows], name=name, marker=dict(color=color, cornerradius=3),
                             text=[fmt(r[k]) for r in rows], textposition="outside", textfont=dict(size=10, color=LABEL),
                             cliponaxis=False, **hover(tips)))
    height = 300
    _layout(fig, height)
    fig.update_layout(barmode="group", bargap=0.45, hovermode="x", hoverdistance=-1)
    fig.update_xaxes(showline=False, tickvals=x, ticktext=_size_ticks(rows), title_text="모델 (Qwen2.5)",
                     title_font=dict(size=11, color=MUTED), title_standoff=X_TITLE_GAP)
    fig.update_yaxes(title_text="Macro F1", title_standoff=Y_TITLE_GAP, range=[0, 1.15], tickvals=[0, 0.5, 1], showticklabels=True,
                     showgrid=True, gridcolor=GRID, gridwidth=0.5)
    fig.update_layout(margin=dict(MARGIN, b=MARGIN["b"] + 14, l=MARGIN["l"] + Y_TITLE_PAD))   # 메모리 줄 · y 숫자와 축 제목 사이
    round_box(fig, "paper", height - MARGIN["t"] - MARGIN["b"] - 14)
    return fig


def precision_recall(rows):
    """c4b: 왼쪽 = 정밀도↔재현율 아령(같은 줄의 두 점 + 사이 선), 오른쪽 = 조건 검색 평균 답 길이 막대.
    y축(모델) 하나를 두 칸이 같이 쓴다 -> 줄 어디에 올려도 그 모델 툴팁 하나."""
    y = [r["size"] for r in rows]
    tips = [([_model_head(r),
              f"{dot(PREC_COLOR)}정밀도 <b>{fmt(r['precision_v'])}</b> · {dot(RECALL_COLOR)}재현율 <b>{fmt(r['recall'])}</b>",
              f"조건 검색 평균 답 길이 <b>{fmt(r['ans_len'], 1)}명</b> · 조건 검색 Macro F1 <b>{fmt(r['filter'])}</b>"], None)
            for r in rows]
    fig = go.Figure()
    seg_x, seg_y = [], []
    for r in rows:
        seg_x += [r["precision_v"], r["recall"], None]
        seg_y += [r["size"], r["size"], None]
    fig.add_trace(go.Scatter(x=seg_x, y=seg_y, mode="lines", line=dict(color="#5F5E5A", width=3), hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=[r["precision_v"] for r in rows], y=y, mode="markers+text", name="정밀도",
                             marker=dict(size=13, color=PREC_COLOR, line=dict(color=BOX_BG, width=2)),
                             text=[fmt(r["precision_v"]) for r in rows], textposition="top center",
                             textfont=dict(size=11, color=PREC_COLOR),   # 숫자 색 = 점 색 (와이어프레임)
                             cliponaxis=False, **hover(tips)))
    fig.add_trace(go.Scatter(x=[r["recall"] for r in rows], y=y, mode="markers+text", name="재현율",
                             marker=dict(size=13, color=RECALL_COLOR, line=dict(color=BOX_BG, width=2)),
                             text=[fmt(r["recall"]) for r in rows], textposition="bottom center",
                             textfont=dict(size=11, color=RECALL_COLOR), cliponaxis=False, hoverinfo="skip"))
    top_len = max(r["ans_len"] or 0 for r in rows)
    fig.add_trace(go.Bar(x=[r["ans_len"] for r in rows], y=y, orientation="h", xaxis="x2", name="평균 답 길이",
                         width=0.36, marker=dict(color=COLOR["avg"], cornerradius=3),
                         text=[f"<b>{fmt(r['ans_len'], 1)}명</b>" for r in rows], textposition="outside",
                         textfont=dict(size=12, color="#F1EFE8"), cliponaxis=False, hoverinfo="skip"))
    height = 60 + 62 * len(rows) + X_LABEL_GAP
    _layout(fig, height)
    left = [0, 0.6]
    fig.update_layout(
        hovermode="y", hoversubplots="axis", hoverdistance=-1, margin=dict(MARGIN, l=60, t=34, b=30 + X_LABEL_GAP),
        xaxis=dict(domain=left, range=[-0.05, 1.05], tickvals=[0, 0.5, 1], showgrid=True, gridcolor=GRID, gridwidth=0.5,
                   showline=False, tickfont=dict(size=11, color="#888780")),
        xaxis2=dict(domain=[0.7, 1], anchor="y", range=[0, top_len * 1.3], showticklabels=False, showgrid=False,
                    showline=False, zeroline=False, fixedrange=True),
        yaxis=dict(autorange="reversed", showticklabels=True, tickfont=dict(size=13, color="#E4E2DA"),
                   ticklabelstandoff=12),
    )
    for x0, text in ((sum(left) / 2, "정밀도 ↔ 재현율 (60문항 전체)"), (0.85, "조건 검색 평균 답 길이")):
        fig.add_annotation(xref="paper", yref="paper", x=x0, y=1, yshift=22, showarrow=False, text=text,
                           font=dict(size=11, color=MUTED))
    plot_h = height - 34 - (30 + X_LABEL_GAP)
    round_box(fig, "paper", plot_h, w_px=(PLOT_W) * (left[1] - left[0]), xref="x domain")
    return fig


TIME_SERIES = [("filter_t", "조건 검색", COLOR["filter"]), ("avg", "전체 평균", COLOR["avg"]),
               ("lookup_t", "캐릭터 조회", COLOR["lookup"])]


def model_time(rows):
    """c4c: 모델 크기별 평균 응답 시간 꺾은선 (전체 평균 · 캐릭터 조회 · 조건 검색). 점마다 숫자 라벨."""
    x = [r["size"] for r in rows]
    tips = [([_model_head(r),
              f"전체 평균 <b>{fmt(r['avg'])}초</b> · 중앙값 <b>{fmt(r['median'])}초</b>",
              f"{dot(COLOR['lookup'])}캐릭터 조회 <b>{fmt(r['lookup_t'])}초</b>",
              f"{dot(COLOR['filter'])}조건 검색 <b>{fmt(r['filter_t'])}초</b> · 평균 답 길이 <b>{fmt(r['ans_len'], 1)}명</b>"],
             None) for r in rows]
    top = max(max(r[k] or 0 for k, _, _ in TIME_SERIES) for r in rows)
    fig = go.Figure()
    for i, (k, name, color) in enumerate(TIME_SERIES):
        if k == "avg":   # 전체 평균 라벨: 조건 검색 점과 가까우면 왼쪽에 (겹치지 않게)
            pos = ["middle left" if abs((r["filter_t"] or 0) - (r["avg"] or 0)) < top * 0.12 else "top center" for r in rows]
        else:
            pos = "bottom center" if k == "lookup_t" else "top center"
        fig.add_trace(go.Scatter(
            x=x, y=[r[k] for r in rows], mode="lines+markers+text", name=name,
            line=dict(color=color, width=2.5), marker=dict(size=9, color=color, line=dict(color=BOX_BG, width=1.5)),
            text=[f"{fmt(r[k])}초" for r in rows], textposition=pos,
            textfont=dict(size=10, color=LABEL if k == "avg" else color),   # 숫자 색 = 선 색 (회색 선만 밝게, 와이어프레임)
            cliponaxis=False, **(hover(tips) if i == 0 else dict(hoverinfo="skip"))))
    height = 330   # 1.5B 쪽 점 세 개가 가까워서 높이를 넉넉히 (라벨 겹침 방지)
    _layout(fig, height)
    fig.update_layout(hovermode="x", hoverdistance=-1, meta={"spike": True})
    fig.update_xaxes(showline=False, title_text="모델 (Qwen2.5)", title_font=dict(size=11, color=MUTED),
                     title_standoff=X_TITLE_GAP, tickfont=dict(size=13, color="#E4E2DA"),
                     range=[-0.35, len(rows) - 1 + 0.35])   # 양 끝 점이 박스 가장자리에 붙지 않게 여백
    fig.update_yaxes(range=[0, top * 1.2], showticklabels=True, ticksuffix="초", showgrid=True, gridcolor=GRID, gridwidth=0.5)
    round_box(fig, "paper", height - MARGIN["t"] - MARGIN["b"])
    return fig


def combo_bars(rows, key, unit="", tickvals=None, axis_title=""):
    """c4d·c4e: 모델·GPU·정밀도 조합별 가로 막대. 색 = 모델, T4는 흐리게(투명도 0.6). 끝에 값(굵게)."""
    y = [r["label"] for r in rows]
    tips = [([_model_head(r), f"Macro F1 <b>{fmt(r['f1'])}</b> · 평균 응답 <b>{fmt(r['avg'])}초</b>"], None) for r in rows]
    top = max(r[key] or 0 for r in rows)
    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=y, x=[r[key] for r in rows], orientation="h", width=0.6,
        marker=dict(color=[r["color"] for r in rows], opacity=[0.6 if r["gpu"] == "T4" else 1 for r in rows],
                    cornerradius=3),
        text=[f"  <b>{fmt(r[key])}{unit}</b>" for r in rows], textposition="outside",
        textfont=dict(size=12, color="#F1EFE8"), cliponaxis=False, **hover(tips)))
    height = 70 + 36 * len(rows) + X_LABEL_GAP + X_TITLE_GAP
    _layout(fig, height)
    fig.update_layout(hovermode="y", hoverdistance=-1, margin=dict(MARGIN, l=140, r=60))
    # 범위: 가장 긴 막대 + 끝의 값 라벨까지 들어가게. 눈금은 숫자만 (단위는 막대 끝 값에만)
    fig.update_xaxes(showline=False, range=[0, max(tickvals[-1] if tickvals else 0, top) * 1.15], tickvals=tickvals,
                     showgrid=True, gridcolor=GRID, gridwidth=0.5, tickfont=dict(size=11, color="#888780"),
                     title_text=axis_title, title_font=dict(size=11, color=MUTED), title_standoff=X_TITLE_GAP)
    fig.update_yaxes(autorange="reversed", showticklabels=True, tickfont=dict(size=12, color=LABEL), ticklabelstandoff=10)
    round_box(fig, "paper", height - MARGIN["t"] - MARGIN["b"], w_px=PLOT_W - 120)
    return fig


# ---------- ① 성능 변화 ----------
# 선 네 개: 키, 이름, 색. 툴팁은 이 순서, 그리기는 거꾸로 (전체가 맨 위에 보이게)
PERF_SERIES = [("f1", "전체", COLOR["all"]), ("lookup", "캐릭터 조회", COLOR["lookup"]),
               ("filter", "조건 검색", COLOR["filter"]), ("unknown", "데이터 없음", COLOR["unknown"])]


def perf_tip_parts(r):
    lines = [f"<b>{_esc(r['stage'])}</b>"] + [f"{dot(c)}{name} <b>{fmt(r[k])}</b>" for k, name, c in PERF_SERIES]
    return lines, (f"개선점: {_esc(r['change'])}" if r.get("change") else None)


def perf_lines(rows):
    """c1a: 단계별 Macro F1 꺾은선 (전체 + 질문 유형 3개). 점선·툴팁은 ②·③과 같은 방식."""
    x = [r["stage"] for r in rows]
    fig = go.Figure()
    for k, name, color in reversed(PERF_SERIES):
        extra = hover([perf_tip_parts(r) for r in rows]) if k == "f1" else dict(hoverinfo="skip")
        fig.add_trace(go.Scatter(
            x=x, y=[r[k] for r in rows], mode="lines+markers", name=name,
            line=dict(color=color, width=2.5), marker=dict(size=9, color=color, line=dict(color=BOX_BG, width=1.5)),
            cliponaxis=False, **extra))
    height = 300
    _layout(fig, height)
    fig.update_layout(hovermode="x", hoverdistance=-1, meta={"spike": True})
    fig.update_xaxes(showline=False, title_text="개선 단계", title_font=dict(size=11, color=MUTED),
                     title_standoff=X_TITLE_GAP)
    # 점에 숫자 라벨이 없어서 y 숫자와 가로 눈금선을 남긴다 (③ c3a와 같음)
    fig.update_yaxes(title_text="Macro F1", title_standoff=Y_TITLE_GAP, range=[-0.06, 1.08], tickvals=[0, 0.25, 0.5, 0.75, 1], showticklabels=True,
                     showgrid=True, gridcolor=GRID, gridwidth=0.5)
    fig.update_layout(margin=dict(MARGIN, l=MARGIN["l"] + Y_TITLE_PAD + 7))   # '0.75'가 길어서 7px 더
    round_box(fig, "paper", height - MARGIN["t"] - MARGIN["b"])
    return fig
