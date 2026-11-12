"""화면 공통 부품: 다크 CSS, 머리말, 조건 칩, 숫자 카드, 요약 상자, 💡 상자, 결과 표, 실험 기록 상자.

- 모양은 docs/dashboard/genshin_dashboard_wireframe.html을 따른다.
- 부품 함수는 HTML 문자열만 돌려준다 (테스트하기 쉽게). 화면에 그리는 것은 show() 하나.
- 우리 HTML은 항상 <div class="gd">로 감싸고, CSS도 .gd 아래에만 적용한다 (Streamlit 기본 스타일과 섞이지 않게).
- yaml 글은 text.rich()로 이스케이프 + **굵게** 처리, JSON 값은 html.escape로 이스케이프한다.
"""
import html

from . import text

# 질문 유형 표시 이름과 색 (와이어프레임)
TYPE_LABEL = {"lookup": "캐릭터 조회", "filter": "조건 검색", "unknown": "데이터 없음"}
COLOR = {"all": "#7F77DD", "lookup": "#85B7EB", "filter": "#F0997B", "unknown": "#97C459",
         "good": "#97C459", "bad": "#F0997B", "avg": "#888780", "median": "#5F5E5A"}

CSS = """
<style>
/* 페이지 바탕 (Streamlit 기본 화면을 다크로) */
.stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {background:#111110;}
/* 위 여백: Streamlit 상단바(약 3.75rem)에 제목이 가리지 않게 */
[data-testid="stMainBlockContainer"], .block-container {max-width:980px; padding-top:5.5rem;}
.stApp, .stApp p, .stApp li, .stApp label, .stApp summary, .stApp [data-testid="stMarkdownContainer"] {color:#C2C0B6;}
.stApp [data-testid="stExpander"] details {border:0.5px solid #3A3A38; border-radius:8px; background:transparent;}
.stApp [data-testid="stExpander"] summary p {font-size:14px; color:#E4E2DA;}
/* 대시보드 전체 상자 (와이어프레임 .dk) · 그래프 패널 (.panel): key를 붙인 st.container에 칠한다 */
.st-key-dk {background:#1A1A19; border-radius:12px; padding:24px;}
[class*="st-key-panel_"] {background:#202020; border-radius:8px; padding:18px 18px 16px; gap:0.5rem;}
[class*="st-key-panel_"] .stPlotlyChart, [class*="st-key-panel_"] .js-plotly-plot .main-svg {background:transparent !important;}

/* 우리 툴팁 (와이어프레임 #tip): TIP_SCRIPT가 마우스 옆에 띄운다. 스크립트가 돌면 body에 gd-tip-on이 붙고
   Plotly 기본 툴팁·x축 단계 이름 상자는 숨긴다 (스크립트가 안 돌면 Plotly 기본 툴팁이 그대로 보임) */
#gd-tip {position:fixed; display:none; z-index:100000; pointer-events:none; white-space:nowrap;
  background:#2C2C2A; border:1px solid #5F5E5A; border-radius:8px; padding:10px 14px; box-shadow:0 4px 14px rgba(0,0,0,.5);
  font-family:-apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Noto Sans KR",sans-serif; font-size:12px; line-height:1.8; color:#9C9A92;}
#gd-tip b {color:#FFFFFF; font-weight:600;}
#gd-tip .h, #gd-tip .h b {color:#F1EFE8; font-weight:600; margin-bottom:2px;}
#gd-tip .d {display:inline-block; width:8px; height:8px; border-radius:50%; margin-right:6px;}
#gd-tip .c {color:#B4B2A9; border-top:1px solid #444441; margin-top:6px; padding-top:6px;}
.gd-tip-on .js-plotly-plot .hoverlayer .hovertext, .js-plotly-plot .hoverlayer .axistext {display:none;}
/* 툴팁이 떠 있는 동안 커서는 '?' 모양 */
.js-plotly-plot.gd-hovering .draglayer .drag {cursor:help !important;}
/* 세로 기준 점선 (TIP_SCRIPT가 그림): 점 3px · 빈칸 3px */
.gd-spike {position:absolute; width:1px; pointer-events:none; display:none; z-index:2;
  background:repeating-linear-gradient(to bottom, #8A8880 0 3px, transparent 3px 6px);}

/* 탭 (와이어프레임 .tabs / .tb-btn): 버튼으로 만든 탭. 고른 탭은 selected_css()가 따로 칠한다 */
.st-key-tabbar {gap:6px !important; margin-top:10px; padding-bottom:16px; border-bottom:0.5px solid #3A3A38;}
/* 버튼 안 글자: 높이를 고정하고 flex로 세로 가운데, 글자 문단의 기본 여백 제거, 색은 버튼 색을 따름 */
.st-key-tabbar button, [class*="st-key-chips_"] button {display:inline-flex; align-items:center; justify-content:center; box-shadow:none;}
.st-key-tabbar button *, [class*="st-key-chips_"] button * {color:inherit !important; margin:0 !important; padding:0; line-height:1 !important;}
/* 버튼 안 글자 상자(div)도 버튼 높이만큼 늘리고 가운데 (안 하면 글자가 위로 붙는다) */
.st-key-tabbar button div, [class*="st-key-chips_"] button div {display:flex; align-items:center; justify-content:center; height:100%;}
.st-key-tabbar button {height:32px; min-height:32px; padding:0 14px; border-radius:8px; border:0.5px solid #444441;
  background:transparent; color:#888780;}
.st-key-tabbar button:hover {color:#D3D1C7; border-color:#444441; background:transparent;}
.st-key-tabbar button:focus:not(:active), .st-key-tabbar button:active {color:#888780; border-color:#444441; background:transparent;}
.st-key-tabbar button p {font-size:13px;}
/* 단계 선택 칩 (와이어프레임 .chips / .chip) */
[class*="st-key-chips_"] {gap:4px !important; margin:22px 0 -6px; align-items:center;}   /* 아래 '주요 발견'과 간격 좁게 */
[class*="st-key-chips_"] button {height:24px; min-height:24px; padding:0 11px; border-radius:14px; border:0.5px solid #444441;
  background:transparent; color:#888780;}
[class*="st-key-chips_"] button:hover, [class*="st-key-chips_"] button:focus:not(:active), [class*="st-key-chips_"] button:active {color:#D3D1C7; border-color:#444441; background:transparent;}
[class*="st-key-chips_"] button p {font-size:12px;}
[class*="st-key-chips_"] button:disabled {opacity:.4; color:#888780; background:transparent; border-color:#444441;}
/* '단계 선택' 글자: 마크다운 기본 여백(-1rem 등)을 없애고 칩 높이(24px)에 맞춰 세로 가운데 */
[class*="st-key-chips_"] > div {height:24px; display:flex; align-items:center;}   /* 글자·칩 칸 높이를 같게 */
[class*="st-key-chips_"] .stMarkdown,[class*="st-key-chips_"] [data-testid="stMarkdownContainer"] {margin:0 !important; padding:0 !important; height:24px;}
[class*="st-key-chips_"] .gd {margin:0; display:flex; align-items:center; height:24px;}
.gd .chips-label {font-size:11px; color:#888780; margin-right:4px; line-height:24px;}

/* 와이어프레임 부품 (.gd 아래에서만) */
/* Streamlit 마크다운은 아래 여백을 -1rem 당겨 쓴다 -> 우리 상자는 1rem을 돌려줘서 아래 요소에 가려지지 않게 */
.gd {font-family:-apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Noto Sans KR","Malgun Gothic",sans-serif; color:#C2C0B6; margin-bottom:1rem;}
.gd ul {margin-bottom:0;} .gd li:last-child {margin-bottom:0 !important;}
.gd table {margin:0 !important;}   /* Streamlit 표 기본 아래 여백 제거 -> 상자 위아래 여백이 같아진다 */
.gd .ttl {font-size:24px; font-weight:600; color:#F1EFE8; margin:0; line-height:1.3;}
.gd .mrow {display:flex; align-items:center; gap:10px; flex-wrap:wrap; margin-top:10px;}
.gd .meta {font-size:12px; color:#888780;}
.gd .cond {display:inline-block; font-size:11px; color:#FAC775; background:#3A2E14; border-radius:12px; padding:3px 10px;}
.gd .chk {display:flex; flex-direction:column; gap:4px; margin-top:12px;}
.gd .chk span {font-size:12px; border-radius:6px; padding:4px 10px;}
.gd .chk .red {color:#F7C1C1; background:#4A1F1F;}
.gd .chk .yellow {color:#FAC775; background:#3A2E14;}
.gd .chk .gray {color:#9C9A92; background:#262624;}
.gd .notice {font-size:12px; color:#9C9A92; background:#262624; border-radius:6px; padding:6px 10px; margin:10px 0 0;}
.gd .sum {margin:20px 0 6px; padding:14px 16px; background:#2A2A28; border-radius:8px; font-size:14px; color:#E4E2DA; line-height:2.0;}
.gd .sum b {color:#FFFFFF; font-weight:600;}   /* 요약 상자의 숫자는 굵게 쓰지 않는다 (yaml summary에 굵게 표시를 안 씀) */
.gd .kh {display:flex; justify-content:flex-end; font-size:11px; color:#6E6D68; margin-bottom:8px;}
.gd .kp {display:grid; gap:8px; margin-bottom:24px;}
.gd .k {background:#232322; border-radius:8px; padding:12px 14px; border-left:4px solid #444441; min-width:0;}
.gd .kl {font-size:13px; font-weight:600; color:#D3D1C7;}
.gd .kn {font-size:24px; font-weight:600; color:#F1EFE8; margin:4px 0 2px;}
.gd .kn small {font-size:13px; color:#B4B2A9; font-weight:400; margin-left:2px;}
.gd .kc {font-size:11px; color:#888780;}
.gd .km {font-size:22px; font-weight:600; color:#F1EFE8; margin:8px 0 4px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;}
.gd .km .md {font-size:18px; margin-right:6px;}
.gd .kv {font-size:13px; color:#888780;}
.gd .dl {font-size:11px;} .gd .good {color:#97C459;} .gd .bad {color:#F0997B;}
.gd .q {font-size:15px; font-weight:600; color:#F1EFE8; margin:0 0 8px;}
.gd .qs {font-size:12px; color:#888780; font-weight:400;}
.gd .qs::before {content:"|"; margin:0 8px; color:#5F5E5A;}
.gd .hint {font-size:11px; color:#6E6D68; margin:2px 0 0;}
.gd .rs {display:flex; gap:4px; align-items:flex-start; margin:14px 0 4px; padding:14px 16px; background:#262624; border:0.5px solid #3A3A38; border-radius:8px;}
.gd .rs .em {flex:0 0 auto; width:28px; height:28px; border-radius:50%; background:#333331; display:flex; align-items:center; justify-content:center; font-size:15px;}
.gd .rs ul {margin:0; padding-left:14px; font-size:13px; line-height:1.9; color:#D3D1C7;}
.gd .rs li {margin-bottom:3px;} .gd .rs li b {color:#F1EFE8; font-weight:600;}
.gd code {font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-size:12px; background:#333331; padding:1px 5px; border-radius:4px; color:#F1EFE8;}
.gd .inf {display:inline-flex; align-items:center; justify-content:center; width:13px; height:13px; border-radius:50%; border:0.5px solid #6E6D68; color:#888780; font-size:9px; margin-left:4px; cursor:help; vertical-align:middle;}
.gd .inf:hover {border-color:#B4B2A9; color:#D3D1C7;}
/* 범례·안내: 그래프 패널 왼쪽 선에 맞춘다 (여백 없음) */
.gd .lg {display:flex; gap:16px; font-size:11px; color:#B4B2A9; flex-wrap:wrap; margin:0; padding:0; align-items:center; line-height:1.8;}
/* 그래프 아래 범례·안내 묶음: 위(그래프와의 사이)는 좁게, 아래(💡 상자와의 사이)는 넓게 */
.gd .under {margin-top:-6px; padding:20px 0px;}
.gd .box {margin-top:10px; background:#232322; border-radius:8px; padding:14px 16px; font-size:13px; color:#D3D1C7;}
.gd .box>span {display:block; font-size:11px; color:#888780; margin-bottom:8px;}
/* 불릿(•)을 상자 이름의 첫 글자와 같은 세로선에 둔다: 기본 불릿 대신 직접 그린다 */
.gd .box ul {margin:0; padding-left:0; list-style:none; line-height:1.85;}
.gd .box li {position:relative; padding-left:14px; margin:0 0 3px;}
.gd .box li::before {content:"•"; position:absolute; left:0; top:0; color:#888780;}
.gd .box li b {color:#F1EFE8; font-weight:600;} .gd .box ul ul {margin-top:2px;}
.gd .box .sub {color:#9C9A92; font-size:12px;}
/* 실험 조건 표: 칸마다 아래 선, 첫 줄은 위 선도 */
.gd .kvt {width:100%; border-collapse:collapse; font-size:13px; table-layout:fixed;}
.gd .kvt td {padding:7px 8px; border:none; border-bottom:0.5px solid #3A3A38; vertical-align:top; color:#D3D1C7; line-height:1.6;}
.gd .kvt tr:first-child td {border-top:0.5px solid #3A3A38;}
.gd .kvt td:first-child {width:110px; color:#888780;}
.gd .res {margin-top:10px; background:#262624; border:0.5px solid #444441; border-radius:8px; padding:14px 14px 10px;}
.gd .res>span {display:block; font-size:13px; font-weight:600; color:#F1EFE8; margin-bottom:10px;}
.gd .rt {width:100%; border-collapse:separate; border-spacing:0; font-size:13px; table-layout:fixed;}
.gd .rt th {padding:9px 10px; text-align:left; font-weight:600; font-size:12px; color:#D3D1C7; background:#333331; border:none;}
.gd .rt th:first-child {border-radius:6px 0 0 6px;} .gd .rt th:last-child {border-radius:0 6px 6px 0;}
.gd .rt td {padding:10px; border:none; border-bottom:0.5px solid #333331; color:#D3D1C7; vertical-align:top;}
.gd .rt td:first-child {color:#F1EFE8; font-weight:600;}
.gd .rt tr:last-child td {border-bottom:none;}
.gd .rt tr.hl td {background:#2E2B45; color:#F1EFE8;}
.gd .rt tr.hl td:first-child {border-radius:6px 0 0 6px;} .gd .rt tr.hl td:last-child {border-radius:0 6px 6px 0;}
.gd .defs {font-size:12px; color:#9C9A92; margin-top:10px; line-height:1.8;}
</style>
"""


# 그래프 툴팁 스크립트 (app.py가 st.html(..., unsafe_allow_javascript=True)로 한 번 넣는다. 우리가 쓴 코드만 들어간다)
# - Plotly 'plotly_hover' 이벤트에서 점의 customdata(charts.tip_html)를 받아 #gd-tip에 넣고 마우스 옆에 띄운다
# - 위치: 기본은 커서 오른쪽 아래, 오른쪽·아래에 자리가 없으면 왼쪽·위로 뒤집는다 (화면 밖으로 안 나감)
# - layout.meta.spike가 있는 그래프는 그림 영역 전체 높이로 세로 점선을 그린다 (c2a: 두 박스를 가로지름)
TIP_SCRIPT = """<script>
(() => {
  if (window.__gdTip) return;
  window.__gdTip = true;
  document.body.classList.add('gd-tip-on');
  const tip = document.createElement('div');
  tip.id = 'gd-tip';
  document.body.appendChild(tip);
  let mx = 0, my = 0, cur = null;

  function place() {
    if (!cur || tip.style.display !== 'block') return;
    const g = cur.getBoundingClientRect(), w = tip.offsetWidth, h = tip.offsetHeight, gap = 16;
    const isInf = cur.classList.contains('inf');
    const right = (isInf ? window.innerWidth : Math.min(window.innerWidth, g.right + 40)) - 8;
    let x = mx + gap;
    if (x + w > right) x = mx - gap - w;
    x = Math.max(8, x);
    let y = my + gap;
    if (y + h > window.innerHeight - 8) y = my - gap - h;
    y = Math.max(8, y);
    tip.style.left = x + 'px';
    tip.style.top = y + 'px';
  }
  function spikeOf(gd) {
    let s = gd.querySelector(':scope > .gd-spike');
    if (!s) {
      s = document.createElement('div');
      s.className = 'gd-spike';
      gd.appendChild(s);
      if (getComputedStyle(gd).position === 'static') gd.style.position = 'relative';
    }
    return s;
  }
  function hide() {
    tip.style.display = 'none';
    if (cur) {
      cur.classList.remove('gd-hovering');
      const s = cur.querySelector(':scope > .gd-spike');
      if (s) s.style.display = 'none';
    }
    cur = null;
  }
  function show(gd, e) {
    const pt = (e.points || []).find(p => typeof p.customdata === 'string');
    if (!pt) return;
    if (cur && cur !== gd) hide();
    cur = gd;
    gd.classList.add('gd-hovering');
    tip.innerHTML = pt.customdata;
    tip.style.display = 'block';
    if (e.event && e.event.clientX !== undefined) { mx = e.event.clientX; my = e.event.clientY; }
    place();
    const meta = gd.layout && gd.layout.meta;
    const size = gd._fullLayout && gd._fullLayout._size;
    if (meta && meta.spike && size) {
      let x = null;
      if (pt.xaxis && pt.xaxis.d2l) x = pt.xaxis._offset + pt.xaxis.l2p(pt.xaxis.d2l(pt.x));
      else if (pt.bbox) x = (pt.bbox.x0 + pt.bbox.x1) / 2;
      if (x !== null && isFinite(x)) {
        const s = spikeOf(gd);
        s.style.left = Math.round(x) + 'px';
        s.style.top = size.t + 'px';
        s.style.height = size.h + 'px';
        s.style.display = 'block';
      }
    }
  }
  function bind(gd) {
    if (typeof gd.on !== 'function') return;
    const ev = gd._ev || 'none';
    if (gd.__gdTipEv === ev) return;
    gd.__gdTipEv = ev;
    gd.on('plotly_hover', e => show(gd, e));
    gd.on('plotly_unhover', () => { if (cur === gd) hide(); });
  }
  document.addEventListener('mouseover', e => {
    if (!e.target.closest) return;
    const gd = e.target.closest('.js-plotly-plot');
    if (gd) bind(gd);
    // 범례 ⓘ: data-tip 글을 같은 툴팁 상자에 (글자로만 넣어서 HTML로 해석되지 않게)
    const inf = e.target.closest('.inf[data-tip]');
    if (inf && cur !== inf) {
      hide();
      cur = inf;
      tip.textContent = inf.getAttribute('data-tip');
      tip.style.display = 'block';
      mx = e.clientX; my = e.clientY;
      place();
    }
  }, true);
  document.addEventListener('mousemove', e => {
    mx = e.clientX; my = e.clientY;
    if (cur && !cur.contains(e.target)) hide(); else place();
  }, true);
  window.addEventListener('scroll', hide, true);
})();
</script>"""


def esc(value):
    """JSON 값 등 사람이 쓰지 않은 글자는 그대로 이스케이프."""
    return html.escape(str(value), quote=True)


def wrap(inner):
    return f'<div class="gd">{inner}</div>'


def show(inner, width="auto"):
    """HTML 조각을 화면에 그린다 (Streamlit은 여기서만 부른다)."""
    import streamlit as st
    if inner:
        st.markdown(wrap(inner), unsafe_allow_html=True, width=width)


def selected_css(*keys):
    """고른 탭·칩 버튼만 '켜진' 모양으로 칠하는 CSS (st-key-{key}는 Streamlit이 key마다 붙이는 클래스)."""
    on = "background:#F1EFE8 !important; border-color:#F1EFE8 !important; color:#1A1A19 !important;"
    rules = "".join(f".st-key-{k} button, .st-key-{k} button:hover, .st-key-{k} button:focus:not(:active) {{{on}}}"
                    f" .st-key-{k} button * {{color:#1A1A19 !important; font-weight:600;}}" for k in keys if k)
    return f"<style>{rules}</style>"


# ---------- 머리말 ----------

def header_html(title, meta, cond=None):
    """제목 + '평가셋 info_v2 · 데이터 7.2' + 그 오른쪽에 지금 탭의 노란 조건 칩."""
    return (f'<p class="ttl">{esc(title)}</p><div class="mrow"><span class="meta">{esc(meta)}</span>'
            f'{cond_html(cond)}</div>')


def checks_html(checks):
    """검증 결과 (그 탭의 데이터 폴더만). 문제가 없으면 빈 글자. checks = [{'level', 'msg'}]"""
    if not checks:
        return ""
    icon = {"red": "⛔", "yellow": "⚠️", "gray": "⚠️"}
    order = {"red": 0, "yellow": 1, "gray": 2}
    rows = sorted(checks, key=lambda c: order.get(c["level"], 3))
    return '<div class="chk">' + "".join(
        f'<span class="{c["level"]}">{icon.get(c["level"], "")} {esc(c["msg"])}</span>' for c in rows) + "</div>"


def cond_html(cond):
    return f'<span class="cond">{text.rich(cond)}</span>' if cond else ""


def notice_html(msg):
    return f'<div class="notice">ℹ️ {esc(msg)}</div>' if msg else ""


# ---------- 요약 · 카드 ----------

def summary_html(lines):
    """탭 상단 요약 상자 (.sum)."""
    if not lines:
        return ""
    return '<div class="sum">' + "<br>".join(text.rich(x) for x in lines) + "</div>"


def delta(current, base, higher_is_better=True, unit="", digits=3):
    """baseline 대비 변화 -> (글자, 좋아졌나). 예: ('▲ 0.489초', False). 변화가 없으면 ('― 0', None).
    화면에 보이는 값(소수 3자리 반올림)끼리 뺀다: 1.482 - 1.1 = 0.382 (원래 값 1.4815로 빼면 0.381이 되어 어긋남)."""
    from .loader import fmt, round_half_up
    if current is None or base is None:
        return None
    if isinstance(current, int) and isinstance(base, int):
        diff = current - base   # 개수는 정수 그대로 (7.0개가 아니라 7개)
    else:
        diff = round_half_up(round_half_up(current, digits) - round_half_up(base, digits), digits)
    if abs(diff) < 10 ** -(digits + 1):
        return (f"― 0{unit}", None)
    arrow = "▲" if diff > 0 else "▼"
    return (f"{arrow} {fmt(abs(diff), digits)}{unit}", (diff > 0) == higher_is_better)


def cards_html(cards, note=None):
    """숫자 카드 줄 (.kp). card = {label, value, unit, caption, delta: (글자, 좋아졌나), color}
    ④ 1위 카드는 {label, medal: '1.5B · 3B', value_text: '0.862점(F1)'}."""
    parts = []
    if note:
        parts.append(f'<div class="kh">{note}</div>')
    items = []
    for c in cards:
        style = f' style="border-left-color:{c["color"]}"' if c.get("color") else ""
        body = f'<div class="kl">{esc(c["label"])}</div>'
        if "medal" in c:
            body += (f'<div class="km"><span class="md">🥇</span>{esc(c["medal"])}</div>'
                     f'<div class="kv">{esc(c["value_text"])}</div>')
        else:
            unit = f'<small>{esc(c["unit"])}</small>' if c.get("unit") else ""
            body += f'<div class="kn">{esc(c["value"])}{unit}</div>'
            if c.get("caption"):
                body += f'<div class="kc">{esc(c["caption"])}</div>'
            if c.get("delta"):
                label, good = c["delta"]
                cls = "" if good is None else (" good" if good else " bad")
                body += f'<div class="dl{cls}">{esc(label)}</div>'
        items.append(f'<div class="k"{style}>{body}</div>')
    parts.append(f'<div class="kp" style="grid-template-columns:repeat({len(cards)},minmax(0,1fr))">'
                 + "".join(items) + "</div>")
    return "".join(parts)


def delta_note_html(stage, base):
    """카드 위 안내: 'rag_v4 기준 · baseline 대비 변화 ( 좋아짐 / 나빠짐)'"""
    return (f'{esc(stage)} 기준 · {esc(base)} 대비 변화 (<span class="good">&nbsp;좋아짐&nbsp;</span>/'
            f'<span class="bad">&nbsp;나빠짐</span>)')


# ---------- 그래프 둘레 ----------

def chart_title_html(chart):
    """그래프 제목 (.q) + 부제 (.qs). chart = yaml의 charts.cXX"""
    if not chart:
        return ""
    sub = f'<span class="qs">{text.rich(chart["subtitle"])}</span>' if chart.get("subtitle") else ""
    return f'<p class="q">{text.rich(chart.get("title", ""))}{sub}</p>'


def hint_html(chart):
    return f'<div class="hint">{text.rich(chart["hint"])}</div>' if chart and chart.get("hint") else ""


def insight_html(lines):
    """💡 요약 상자 (.rs). 그래프 아래에 둔다."""
    if not lines:
        return ""
    return ('<div class="rs"><div class="em">💡</div><ul>'
            + "".join(f"<li>{text.rich(x)}</li>" for x in lines) + "</ul></div>")


def legend_html(items, note=None):
    """범례. items = [(이름, 색, 모양 'line'|'square'|'dot'|'dashed', 툴팁 또는 None)], note = 끝에 붙는 회색 설명."""
    shape_css = {"line": "width:16px;height:3px;border-radius:2px",
                 "square": "width:10px;height:10px;border-radius:2px",
                 "dot": "width:10px;height:10px;border-radius:50%",
                 "dashed": "width:10px;height:10px;border-radius:2px;border:1px dashed #6E6D68;box-sizing:border-box"}
    out = []
    for name, color, shape, tip in items:
        mark = (f'<span style="display:inline-block;{shape_css[shape]};background:{color};'
                f'vertical-align:middle;margin-right:5px"></span>')
        info = f'<span class="inf" data-tip="{esc(tip)}">i</span>' if tip else ""   # 툴팁은 TIP_SCRIPT가 띄움
        out.append(f"<span>{mark}{esc(name)}{info}</span>")
    if note:
        out.append(f'<span style="color:#6E6D68">{esc(note)}</span>')
    return '<div class="lg">' + "".join(out) + "</div>"


# ---------- 실험 기록 (st.expander 안) ----------

def result_table_html(header, rows, highlight=None, title="📊 결과", defs=None, widths=None):
    """'📊 결과' 상자 (.res) 안의 표. rows의 칸은 이미 화면용 글자. highlight = 강조할 행 번호."""
    widths = widths or {}
    th = ""
    for i, h in enumerate(header):
        style = ' style="width:%s"' % widths[i] if i in widths else ""
        th += f"<th{style}>{esc(h)}</th>"
    trs = ""
    marked = set(highlight) if isinstance(highlight, (list, tuple, set)) else {highlight}   # 여러 줄 강조 가능
    for i, row in enumerate(rows):
        cls = ' class="hl"' if i in marked else ""
        trs += f"<tr{cls}>" + "".join(f"<td>{esc(c)}</td>" for c in row) + "</tr>"
    extra = f'<div class="defs">{"<br>".join("· " + text.rich(d) for d in defs)}</div>' if defs else ""
    return f'<div class="res"><span>{esc(title)}</span><table class="rt"><tr>{th}</tr>{trs}</table>{extra}</div>'


def _item_html(item):
    """주요 발견 한 줄: {title, desc, sub, items} 또는 글자."""
    if isinstance(item, str):
        return f"<li>{text.rich(item)}</li>"
    body = f'<b>{text.rich(item.get("title", ""))}</b>'
    if item.get("desc"):
        body += f' → {text.rich(item["desc"])}' if item.get("title") else text.rich(item["desc"])
    if item.get("sub"):
        body += f'<br><span class="sub">{text.rich(item["sub"])}</span>'
    if item.get("items"):
        body += "<ul>" + "".join(f"<li>{text.rich(x)}</li>" for x in item["items"]) + "</ul>"
    return f"<li>{body}</li>"


def box_html(label, items):
    """실험 기록 안의 상자 (.box): 요약 / 주요 발견 / 다음 과제 / 팀 결정 사항. items가 글자면 한 줄."""
    if not items:
        return ""
    if isinstance(items, str):
        return f'<div class="box"><span>{esc(label)}</span>{text.rich(items)}</div>'
    return f'<div class="box"><span>{esc(label)}</span><ul>' + "".join(_item_html(i) for i in items) + "</ul></div>"


def kv_table_html(label, rows):
    """실험 조건 표 (.kvt). rows = [(이름, 값)], 값은 yaml 글처럼 처리 (줄바꿈·굵게)."""
    trs = "".join(f"<tr><td>{esc(k)}</td><td>{text.rich(v)}</td></tr>" for k, v in rows)
    return f'<div class="box"><span>{esc(label)}</span><table class="kvt">{trs}</table></div>'
