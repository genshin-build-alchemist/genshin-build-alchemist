"""화면 공통 부품: 다크 CSS, 머리말, 조건 칩, 숫자 카드, 요약 상자, 💡 상자, 결과 표, 실험 기록 상자.

- 모양은 docs/dashboard/genshin_dashboard_wireframe.html을 따른다.
- 부품 함수는 HTML 문자열만 돌려준다 (테스트하기 쉽게). 화면에 그리는 것은 show() 하나.
- 우리 HTML은 항상 <div class="gd">로 감싸고, CSS도 .gd 아래에만 적용한다 (Streamlit 기본 스타일과 섞이지 않게).
- yaml 글은 text.rich()로 이스케이프 + **굵게** 처리, JSON 값은 html.escape로 이스케이프한다.
"""
import html
import re

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
[class*="st-key-panel_"][class*="_accent"] {background:#2A2520; box-shadow:inset 0 0 0 1px #5A4630;}   /* 예외 강조 */
[class*="st-key-panel_"][class*="_accent"] p.q {color:#FAC775;}   /* 예외 강조 그래프 제목 (부제 .qs는 그대로) */
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
.gd .sum ul {margin:0; padding-left:0; list-style:none;}            /* 모델 비교 요약: 문장마다 불릿 */
.gd .sum li {position:relative; padding-left:16px; margin:0;}
.gd .sum li::before {content:"•"; position:absolute; left:2px; top:0; color:#888780;}
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
/* 💡 상자: 전구 오른쪽 15px. 항목마다 굵은 소제목 한 줄 + 문장마다 불릿 한 줄 */
.gd .rs {display:flex; gap:15px; align-items:flex-start; margin:14px 0 4px; padding:14px 16px; background:#262624; border:0.5px solid #3A3A38; border-radius:8px;}
.gd .rs .em {flex:0 0 auto; width:28px; height:28px; border-radius:50%; background:#333331; display:flex; align-items:center; justify-content:center; font-size:15px;}
.gd .rs .rb {flex:1; min-width:0; padding-top:3px;}
.gd .rs .ig + .ig {margin-top:10px;}
.gd .rs .it {font-size:13px; font-weight:600; color:#F1EFE8; line-height:1.7; margin-bottom:2px;}
.gd .rs ul {margin:0; padding-left:0; list-style:none; font-size:13px; line-height:1.85; color:#D3D1C7;}
.gd .rs li {position:relative; padding-left:14px; margin-bottom:1px;}
.gd .rs li::before {content:"•"; position:absolute; left:2px; top:0; color:#888780;}
.gd .rs li b {color:#F1EFE8; font-weight:600;}
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
.gd .res.lh15 .rt td {line-height:1.5;}   /* 글이 긴 표 (문제점 및 다음 과제) */
.gd .rt td .csub {margin-top:4px; font-size:11.5px; font-weight:400; color:#888780; line-height:1.5;}   /* 칸 아래 작은 회색 글 */
.gd .rt tr.hl td {background:#2E2B45; color:#F1EFE8;}
.gd .rt tr.hl td:first-child {border-radius:6px 0 0 6px;} .gd .rt tr.hl td:last-child {border-radius:0 6px 6px 0;}
.gd .defs {font-size:12px; color:#9C9A92; margin-top:10px; line-height:1.8;}

/* ---------- 머리말: 대시보드 이름(가장 크게) · 탭 질문 · [단계 이름 | 주황 배지 | 날짜·데이터 배지] 한 줄 ---------- */
.gd .brand {font-size:30px; font-weight:700; color:#F1EFE8; margin:0; line-height:1.3; letter-spacing:-.3px;}
.gd .qt {font-size:22px; font-weight:600; color:#F1EFE8; line-height:1.4; margin:24px 0 0; padding-bottom:30px;}
.gd .qt b {color:inherit; font-weight:inherit;}
.gd .srow {display:flex; align-items:center; gap:10px; flex-wrap:wrap;}
.gd .sn {font-size:17px; font-weight:600; color:#F1EFE8; line-height:1.4;}   /* 중제목: 'rag_v5_data 실험 결과' */
.gd .ob {display:inline-block; font-size:11px; color:#B4B2A9; background:#2C2C2A; border:0.5px solid #444441; border-radius:12px; padding:3px 10px;}
.gd .bdg {display:flex; gap:6px; flex-wrap:wrap; margin-left:auto;}
.gd .bd {font-size:11px; color:#9C9A92; background:#262624; border:0.5px solid #3A3A38; border-radius:12px; padding:3px 10px; white-space:nowrap;}
/* 요약 상자: 상승(초록) · 동일(파랑) · 하락(주황) = 색 + 글자, 마지막 줄은 한 줄 결론 */
.gd .sum .sl {display:flex; align-items:baseline; gap:10px; line-height:1.9;}
.gd .tag {flex:0 0 auto; min-width:52px; text-align:center; font-size:12px; font-weight:600; border-radius:10px; padding:0 9px; line-height:22px;}
.gd .tag.good {color:#97C459; background:rgba(151,196,89,.13);}
.gd .tag.same {color:#85B7EB; background:rgba(133,183,235,.13);}
.gd .tag.bad {color:#F0997B; background:rgba(240,153,123,.13);}
.gd .sum .sk {font-size:12px; color:#888780; padding-right:10px;}
.gd .sum .none {color:#6E6D68;}
.gd .sum .ans {display:flex; align-items:flex-start; border-top:0.5px solid #444441; margin-top:10px; padding-top:10px; color:#F1EFE8; line-height:1.7;}
.gd .sum .ans .ai {flex:0 0 auto; padding-right:15px;}   /* 💡 오른쪽 15px */

/* 숫자 카드: 변화량은 ▲ ▼ = + 색 (은은한 빛). 비교 단계는 카드 밖 아래 한 줄 (.kfoot, 흐리게) */
.gd .dl {font-size:12px; font-weight:600; margin-top:2px;}
.gd .dl.good {color:#97C459; text-shadow:0 0 10px rgba(151,196,89,.45);}
.gd .dl.bad {color:#F0997B; text-shadow:0 0 10px rgba(240,153,123,.45);}
.gd .dl.same {color:#85B7EB; text-shadow:0 0 10px rgba(133,183,235,.45);}
.gd .kfoot {font-size:11px; color:#6E6D68; text-align:right; margin:-16px 0 24px;}
.gd .kfoot .good, .gd .kfoot .bad {opacity:.75;}
/* 응답 시간: 속도 카드 3개 | 참고 카드 2개 (작고 흐리게) */
.gd .kp2 {display:flex; gap:14px; align-items:stretch; margin-bottom:24px;}
.gd .kp2 .kp {margin:0; flex:3;}
.gd .kref {flex:1.7; display:flex; flex-direction:column; gap:6px; border-left:0.5px solid #3A3A38; padding-left:14px;}
.gd .kref>span {font-size:11px; color:#6E6D68;}
.gd .kref .kp {flex:1; margin:0;}
.gd .k.ref {background:#1E1E1D; opacity:.78; padding:10px 12px;}
.gd .k.ref .kl {font-size:12px; color:#B4B2A9;} .gd .k.ref .kn {font-size:18px;}

/* 실험 기록 안의 표 상자 제목 · 설명 */
.gd .res .note {font-size:12px; color:#9C9A92; margin-top:10px; line-height:1.8;}
.gd .res .note.tip {display:flex; align-items:flex-start;}       /* 표 아래 설명: 앞에 💡 */
.gd .res .note.tip .ai {flex:0 0 auto; padding-right:15px;}
.gd .rt td.num, .gd .rt th.num {text-align:right; font-variant-numeric:tabular-nums;}
.gd .rt td.q {color:#D3D1C7; font-weight:400;}
.gd .lead {font-size:12px; color:#B4B2A9; background:#2A2A28; border-radius:6px; padding:6px 10px; margin-bottom:10px;}

/* 프롬프트 보기: 단계 칩 아래, 왼쪽 = 프롬프트 1개(추가된 줄은 + 표시 · 보라 배경), 오른쪽 = 바뀐 점 */
.gd .pv {display:flex; gap:12px; align-items:flex-start;}
.gd .pv-main {flex:1; min-width:0; background:#1C1C1B; border:0.5px solid #3A3A38; border-radius:8px; overflow:hidden;}
.gd .pv-head {display:flex; justify-content:space-between; align-items:center; gap:8px; font-size:12px; color:#9C9A92; padding:8px 12px; border-bottom:0.5px solid #333331; background:#232322;}
.gd .pv-head b {color:#F1EFE8; font-weight:600;}
.gd .pv-key {display:inline-flex; align-items:center; gap:6px; font-size:11px; color:#AFA9EC;}
.gd .pv-key i {font-style:normal; display:inline-block; width:14px; height:14px; line-height:14px; text-align:center; border-radius:3px; background:rgba(127,119,221,.28); font-weight:700;}
.gd .pv-code {font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-size:12px; line-height:1.75; padding:8px 0; max-height:520px; overflow:auto;}
.gd .ln {display:flex; padding-right:12px; white-space:pre-wrap; word-break:break-all; color:#C2C0B6;}
.gd .ln .g {flex:0 0 26px; text-align:center; color:#4A4A47; user-select:none;}
.gd .ln.add {background:rgba(127,119,221,.17); color:#EEEDFE;}
.gd .ln.add .g {color:#AFA9EC; font-weight:700;}
.gd .fold {margin:3px 0;}
.gd .fold summary {list-style:none; cursor:pointer; display:inline-block; margin-left:26px; font-family:-apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Noto Sans KR",sans-serif;
  font-size:11px; color:#9C9A92; background:#262624; border:0.5px dashed #4A4A47; border-radius:6px; padding:2px 10px;}
.gd .fold summary::-webkit-details-marker {display:none;}
.gd .fold summary:hover {color:#D3D1C7; border-color:#6E6D68;}
.gd .fold.add summary {color:#AFA9EC; border-color:#5B54A8; background:rgba(127,119,221,.10);}
.gd .fold .cl {display:none;} .gd .fold[open] .cl {display:inline;} .gd .fold[open] .op {display:none;}
.gd .pv-side {flex:0 0 232px; background:#232322; border-radius:8px; padding:12px 14px; font-size:13px; color:#D3D1C7; line-height:1.7;}
.gd .pv-side>span {display:block; font-size:11px; color:#888780; margin:12px 0 4px;}
.gd .pv-side>span:first-child {margin-top:0;}
.gd .pv-side b {color:#F1EFE8; font-weight:600;}
.gd .pv-side .pn {font-size:12px; color:#B4B2A9; margin-top:6px;}
.gd .pv-side .rv {font-size:15px; font-weight:600; color:#F1EFE8; font-variant-numeric:tabular-nums;}

/* 단계별 프롬프트 표 + '⧉ 프롬프트 보기' 버튼 (누르면 모달) */
.gd .ptab .rt td {vertical-align:middle;}
.gd .ptab .rt .dl {display:inline; margin-left:6px; font-size:11px;}
.gd .pbtn {all:unset; cursor:pointer; display:inline-flex; align-items:center; gap:6px; font-size:12px; color:#D3D1C7;
  border:0.5px solid #5F5E5A; border-radius:7px; padding:5px 10px; white-space:nowrap; box-sizing:border-box;}
.gd .pbtn:hover {color:#F1EFE8; border-color:#AFA9EC; background:rgba(127,119,221,.14);}
.gd .pbtn .pi {color:#AFA9EC; font-size:13px;}
/* Streamlit 화면의 표: 줄마다 st.columns + 버튼 (st-key-prow_*) */
.st-key-ptab {margin-top:10px; background:#262624; border:0.5px solid #444441; border-radius:8px; padding:14px 14px 10px; gap:0 !important;}
.st-key-ptab .gd .pt-t {display:block; font-size:13px; font-weight:600; color:#F1EFE8; margin-bottom:4px;}
.st-key-ptab .gd .pt-n {font-size:12px; color:#9C9A92; margin-bottom:10px;}
.st-key-phead {background:#333331; border-radius:6px; padding:9px 10px;}
.st-key-phead .gd .ph {font-size:12px; font-weight:600; color:#D3D1C7;}
[class*="st-key-prow_"] {border-bottom:0.5px solid #333331; padding:6px 10px;}
[class*="st-key-prow_"] .gd {margin:0; font-size:13px; color:#D3D1C7; line-height:1.5;}
[class*="st-key-prow_"] .gd b {color:#F1EFE8; font-weight:600;}
[class*="st-key-prow_"] .gd .dl {display:inline; margin-left:6px; font-size:11px;}
[class*="st-key-pbtn_"] button {min-height:0; height:28px; padding:0 10px; border-radius:7px; border:0.5px solid #5F5E5A;
  background:transparent; color:#D3D1C7; box-shadow:none;}
[class*="st-key-pbtn_"] button p {font-size:12px;}
[class*="st-key-pbtn_"] button:hover {color:#F1EFE8; border-color:#AFA9EC; background:rgba(127,119,221,.14);}

/* 이 단계의 결과 파일이 없는 탭 */
.gd .empty {margin-top:22px; padding:28px; border:0.5px dashed #444441; border-radius:8px; text-align:center; color:#D3D1C7; font-size:14px; line-height:1.9;}
.gd .empty span {font-size:12px; color:#888780;}

/* 실험 단계 버튼 (화면 왼쪽에 떠 있음). 위치(top)는 스크립트가 탭 아래 선에 맞춘다 */
.st-key-fab {position:fixed; top:150px; left:max(8px, calc(50% - 490px - 141px)); width:120px !important; z-index:50; gap:12px !important;
  padding:14px 10px 10px; background:#1E1E1D; border:0.5px solid #3A3A38; border-radius:14px; box-shadow:0 6px 18px rgba(0,0,0,.45); box-sizing:border-box;}
.st-key-fab .gd {margin:0;} .st-key-fab .fab-l {display:block; font-size:11px; color:#888780; text-align:center; margin-bottom:15px;}
.st-key-fab button {width:100%; height:auto; min-height:0; padding:10px 6px; border-radius:9px; border:0.5px solid #444441; background:transparent; color:#B4B2A9; box-shadow:none;}
.st-key-fab button p {font-size:13px; font-weight:600; white-space:nowrap; margin:0;}
.st-key-fab button:hover {color:#F1EFE8; border-color:#444441; background:transparent;}
.st-key-fab button:focus:not(:active), .st-key-fab button:active {color:#B4B2A9; border-color:#444441; background:transparent;}
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


# 그래프 움직임 (값은 그대로, 다 그려진 그림을 브라우저 애니메이션으로 드러낸다)
# - 꺾은선: 선이 baseline부터 이어서 그려지고, 선이 지나가는 순간 점·수치가 나타난다
# - 막대: 모양 그대로 아래(가로 막대는 왼쪽)부터 드러나고, 다 올라온 뒤에 수치
# - 분포도(점만 있는 그래프): baseline부터 점이 차례로, 추세선은 점이 다 찍힌 뒤
ANIM_JS = """
const LINE_MS = 1100, BAR_MS = 850, POP_MS = 320;
const EASE = 'cubic-bezier(.22,1,.36,1)';
const posX = el => { const m = el.transform && el.transform.baseVal.consolidate(); return m ? m.matrix.e : 0; };
const fadeIn = (el, delay, ms = POP_MS) =>
  el.animate([{opacity: 0}, {opacity: 1}], {duration: ms, delay, easing: 'ease-out', fill: 'both'});

function animateGraph(gd) {
  gd.getAnimations({subtree: true}).forEach(a => a.cancel());
  gd.querySelectorAll('.barlayer .trace').forEach(tr => {
    const horiz = !!(gd.data || []).find(t => t.type === 'bar' && t.orientation === 'h');
    tr.querySelectorAll('.point').forEach((pt, j) => {
      const path = pt.querySelector('path');
      if (!path) return;
      const delay = j * 40;
      const from = horiz ? 'inset(0 100% 0 0)' : 'inset(100% 0 0 0)';
      path.animate([{clipPath: from}, {clipPath: 'inset(0 0 0 0)'}], {duration: BAR_MS, delay, easing: EASE, fill: 'both'});
      pt.querySelectorAll('text').forEach(t => fadeIn(t, BAR_MS + delay));
    });
  });
  const traces = [...gd.querySelectorAll('.scatterlayer .trace')];
  const isLine = tr => { const l = tr.querySelector('.js-line'); return l && (l.getAttribute('d') || '').length > 2; };
  const dots = traces.filter(tr => !isLine(tr));
  let dotEnd = 0;
  dots.forEach(tr => {
    const pts = [...tr.querySelectorAll('.points path')], txt = [...tr.querySelectorAll('.textpoint, .text text')];
    const step = Math.min(220, 1200 / Math.max(pts.length, 1));
    pts.forEach((p, j) => fadeIn(p, j * step));
    txt.forEach((t, j) => fadeIn(t, j * step + 80));
    dotEnd = Math.max(dotEnd, pts.length * step);
  });
  traces.filter(isLine).forEach(tr => {
    const line = tr.querySelector('.js-line');
    const onlyLine = !tr.querySelector('.points path');
    const start = dots.length && onlyLine ? dotEnd : 0;
    const dashed = line.style.strokeDasharray && line.style.strokeDasharray !== 'none';
    if (dashed) {
      fadeIn(line, start, 500);
    } else {
      const len = line.getTotalLength();
      line.style.strokeDasharray = `${len} ${len}`;
      line.animate([{strokeDashoffset: len}, {strokeDashoffset: 0}], {duration: LINE_MS, delay: start, easing: 'linear', fill: 'both'})
        .finished.then(() => { line.style.strokeDasharray = ''; }).catch(() => {});
    }
    const box = line.getBBox(), x0 = box.x, w = Math.max(box.width, 1);
    tr.querySelectorAll('.points path').forEach(p => fadeIn(p, start + LINE_MS * Math.min(1, Math.max(0, (posX(p) - x0) / w))));
    tr.querySelectorAll('.textpoint, .text text').forEach(t => {
      const x = t.getAttribute('x') != null ? +t.getAttribute('x') : posX(t);
      fadeIn(t, start + LINE_MS * Math.min(1, Math.max(0, (x - x0) / w)) + 80);
    });
  });
}
"""

# Streamlit 화면용 스크립트 (app.py가 st.html로 한 번 넣는다)
# - 실험 단계 버튼(.st-key-fab) 위쪽을 탭 아래 선에 맞추고, 스크롤로 올라가면 화면 위 16px에 붙인다
# - 그래프가 처음 그려지거나 값이 바뀌면(다른 단계를 고르면) 한 번 움직인다. 마우스 툴팁·크기 조절로는 다시 움직이지 않는다
STREAMLIT_SCRIPT = "<script>\n(() => {\n  if (window.__gdPage) return;\n  window.__gdPage = true;\n" + ANIM_JS + """
  const sig = gd => JSON.stringify((gd.data || []).map(t => [t.x, t.y]));
  function watch(gd) {
    if (gd.__gdAnimBound || typeof gd.on !== 'function') return;
    gd.__gdAnimBound = true;
    const run = () => { const s = sig(gd); if (gd.__gdSig !== s) { gd.__gdSig = s; requestAnimationFrame(() => animateGraph(gd)); } };
    gd.on('plotly_afterplot', run);
    if (gd._fullLayout) run();
  }
  function placeFab() {
    const fab = document.querySelector('.st-key-fab'), bar = document.querySelector('.st-key-tabbar');
    if (fab && bar) fab.style.top = Math.max(16, bar.getBoundingClientRect().bottom) + 'px';
  }
  new MutationObserver(() => { document.querySelectorAll('.js-plotly-plot').forEach(watch); placeFab(); })
    .observe(document.body, {childList: true, subtree: true});
  document.addEventListener('scroll', placeFab, true);
  window.addEventListener('resize', placeFab);
})();
</script>"""


def esc(value):
    """JSON 값 등 사람이 쓰지 않은 글자는 그대로 이스케이프."""
    return html.escape(str(value), quote=True)


def wrap(inner):
    """HTML 조각을 대시보드 공통 상자(.gd)로 감싼다. ui.CSS 의 스타일은 이 상자 안에만 적용된다."""
    return f'<div class="gd">{inner}</div>'


def show(inner, width="auto"):
    """HTML 조각을 화면에 그린다 (Streamlit은 여기서만 부른다).
    나머지 함수는 HTML 글자만 만들어 돌려주므로, Streamlit 없이 unittest로 검사할 수 있다."""
    import streamlit as st          # 함수 안에서 import: 테스트가 이 파일을 불러올 때 streamlit 이 필요 없게
    if inner:
        st.markdown(wrap(inner), unsafe_allow_html=True, width=width)


def selected_css(*keys):
    """고른 탭·칩 버튼만 '켜진' 모양으로 칠하는 CSS (st-key-{key}는 Streamlit이 key마다 붙이는 클래스)."""
    on = "background:#F1EFE8 !important; border-color:#F1EFE8 !important; color:#1A1A19 !important;"
    rules = "".join(f".st-key-{k} button, .st-key-{k} button:hover, .st-key-{k} button:focus:not(:active) {{{on}}}"
                    f" .st-key-{k} button * {{color:#1A1A19 !important; font-weight:600;}}" for k in keys if k)
    return f"<style>{rules}</style>"


# ---------- 머리말 ----------

def header_html(title):
    """맨 위 대시보드 이름 (작게). 큰 제목 자리는 탭의 질문이 쓴다 (tab_header_html)."""
    return f'<p class="brand">{esc(title)}</p>'


def tab_header_html(question, badges=(), stage=None, change=None):
    """탭 머리말: 탭의 질문 아래 한 줄에
    'rag_v5_data 실험 결과'(중제목) · 그 단계의 실험 조건(연한 회색 배지) · 날짜·데이터 배지(오른쪽)."""
    bd = "".join(f'<span class="bd">{esc(b)}</span>' for b in badges if b)
    row = f'<span class="sn">{esc(stage)} 실험 결과</span>' if stage else ""
    row += f'<span class="ob">{esc(change)}</span>' if stage and change else ""
    row += f'<div class="bdg">{bd}</div>' if bd else ""
    return f'<p class="qt">{text.rich(question or "")}</p>' + (f'<div class="srow">{row}</div>' if row else "")


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
    """머리말 오른쪽 노란 조건 칩 (예: 어떤 평가셋·문항 기준인지). 글이 없으면 빈 글자."""
    return f'<span class="cond">{text.rich(cond)}</span>' if cond else ""


def notice_html(msg):
    """회색 ℹ️ 안내 한 줄 (예: '글 작성 이후 데이터가 바뀌었어요'). msg가 없으면 빈 글자."""
    return f'<div class="notice">ℹ️ {esc(msg)}</div>' if msg else ""


# ---------- 요약 · 카드 ----------

def summary_html(lines):
    """탭 상단 요약 상자 (.sum): 문장마다 불릿 한 줄."""
    if not lines:
        return ""
    return '<div class="sum"><ul>' + "".join(f"<li>{text.rich(x)}</li>" for x in lines) + "</ul></div>"


def delta(current, base, higher_is_better=True, unit="", digits=3, scale=1):
    """직전 단계 대비 변화 -> (글자, 상태). 상태 = 'good'(좋아짐) / 'bad'(나빠짐) / 'same'(같음).
    예: ('▲ +0.316', 'good'), ('▼ −0.626초', 'good'), ('= 0.000', 'same'). 값이 없으면 None.
    - 화면에 보이는 값(반올림한 값)끼리 뺀다 -> 카드의 두 값과 변화량이 어긋나지 않는다
    - scale=100, digits=1, unit='%p' 이면 비율을 퍼센트포인트로 (0.76 vs 0.438 -> '▲ +32.2%p')"""
    from .loader import round_half_up
    if current is None or base is None:
        return None
    if isinstance(current, int) and isinstance(base, int) and scale == 1:
        diff, shown = current - base, None   # 개수는 정수 그대로 (7.0개가 아니라 7개)
    else:
        diff = round_half_up(round_half_up(current * scale, digits) - round_half_up(base * scale, digits), digits)
        shown = f"{abs(diff):.{digits}f}"
    num = shown if shown is not None else str(abs(diff))
    if abs(diff) < 10 ** -(digits + 1):
        return (f"= {num}{unit}", "same")
    arrow, sign = ("▲", "+") if diff > 0 else ("▼", "−")
    return (f"{arrow} {sign}{num}{unit}", "good" if (diff > 0) == higher_is_better else "bad")


def _card_html(c, ref=False):
    """카드 하나. c = {label, value, unit, delta: (글자, 상태), vs: 'rag_v3 → rag_v4', color} 또는 1위 카드."""
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
            label, state = c["delta"]
            body += f'<div class="dl {state}">{esc(label)}</div>'
    return f'<div class="k{" ref" if ref else ""}"{style}>{body}</div>'


def _grid(cards, ref=False):
    """카드 여러 개를 같은 너비 칸으로."""
    return (f'<div class="kp" style="grid-template-columns:repeat({len(cards)},minmax(0,1fr))">'
            + "".join(_card_html(c, ref) for c in cards) + "</div>")


def compare_note_html(stage, prev_stage):
    """카드 밖 아래 한 줄 (흐리게): '직전 단계 대비 변화 (좋아짐 / 나빠짐)'. 직전 단계가 없으면 빈 글자."""
    if not stage or not prev_stage:
        return ""
    return ('<div class="kfoot">직전 단계 대비 변화 '
            '(<span class="good">좋아짐</span> / <span class="bad">나빠짐</span>)</div>')


def cards_html(cards, ref=None, ref_label="참고", foot=""):
    """숫자 카드 줄. ref(참고 카드)가 있으면 오른쪽에 얇은 선 + '참고' 이름표를 두고 작고 흐리게 붙인다.
    foot = 카드 아래 한 줄 (compare_note_html)."""
    if not ref:
        return _grid(cards) + foot
    return (f'<div class="kp2">{_grid(cards)}<div class="kref"><span>{esc(ref_label)}</span>'
            f'{_grid(ref, ref=True)}</div></div>' + foot)


# 요약 상자 줄 이름 (탭마다 말이 다르다). 색: good 초록 · same 파랑 · bad 주황
STATUS_WORDS = {
    "performance": {"good": "상승", "same": "동일", "bad": "하락"},
    "response_time": {"good": "빨라짐", "same": "동일", "bad": "느려짐"},
    "aux": {"good": "개선", "same": "동일", "bad": "악화"},
}


def status_summary_html(cards, words, answer=None, metric_label=None):
    """맨 위 요약 상자: 카드의 변화 상태를 모아 '상승 / 동일 / 하락' 세 줄 (색 + 글자) + 한 줄 결론.
    해당 항목이 없는 줄은 '없음'. 동일 줄은 항목이 있을 때만 보인다."""
    groups = {"good": [], "same": [], "bad": []}
    for c in cards:
        if c.get("delta"):
            groups[c["delta"][1]].append(c["label"])
    lines = []
    for state in ("good", "same", "bad"):
        names = groups[state]
        if state == "same" and not names:
            continue
        key = f'<span class="sk">{esc(metric_label)}</span>' if metric_label else ""
        body = " · ".join(esc(n) for n in names) if names else '<span class="none">없음</span>'
        lines.append(f'<div class="sl"><span class="tag {state}">{esc(words[state])}</span><span>{key}{body}</span></div>')
    ans = f'<div class="ans"><span class="ai">💡</span><span>{text.rich(answer)}</span></div>' if answer else ""
    return f'<div class="sum">{"".join(lines)}{ans}</div>'


def empty_html(stage, base_stage):
    """이 단계의 결과 파일이 없는 탭 안내."""
    return (f'<div class="empty">📭 이 탭은 {esc(stage)} 단계의 결과 파일이 아직 없어요.<br>'
            f'<span>결과가 들어오면 {esc(base_stage)}와 같은 화면으로 바뀌어요.</span></div>')


# ---------- 그래프 둘레 ----------

def chart_title_html(chart):
    """그래프 제목 (.q) + 부제 (.qs). chart = yaml의 charts.cXX"""
    if not chart:
        return ""
    sub = f'<span class="qs">{text.rich(chart["subtitle"])}</span>' if chart.get("subtitle") else ""
    return f'<p class="q">{text.rich(chart.get("title", ""))}{sub}</p>'


def hint_html(chart):
    """그래프 아래 작은 안내 글 (yaml charts.cXX.hint, 예: 그래프 읽는 법). 없으면 빈 글자."""
    return f'<div class="hint">{text.rich(chart["hint"])}</div>' if chart and chart.get("hint") else ""


LABEL_RE = re.compile(r"^\*\*(.+?)\*\*\s*(.*)$", re.S)     # "**전체 흐름** 문장…" -> 소제목, 나머지
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+(?=[^\s(])")      # 문장 끝(. ! ?) 뒤 빈칸에서 나눈다 (0.817 같은 숫자, 뒤에 붙은 '(보충)'은 안 나뉨)


def sentences(s):
    """글 -> 문장 목록."""
    return [x for x in SENTENCE_RE.split(str(s or "").strip()) if x]


def insight_groups(lines):
    """💡 항목 -> [(소제목 또는 None, [문장…])].
    - "**소제목** 문장1. 문장2." -> 소제목 + 문장 2개
    - "**소제목**" 한 줄 뒤에 오는 굵은 표시 없는 줄 -> 그 소제목 아래 문장 (모델 비교 글 형식)"""
    groups = []
    for line in lines or []:
        m = LABEL_RE.match(str(line).strip())
        if m:
            groups.append((m.group(1), sentences(m.group(2))))
        elif groups:
            groups[-1][1].extend(sentences(line))
        else:
            groups.append((None, sentences(line)))
    return groups


def insight_html(lines):
    """💡 요약 상자 (.rs). 그래프 아래에 둔다. 소제목은 한 줄, 그 아래 문장마다 불릿."""
    if not lines:
        return ""
    body = ""
    for label, items in insight_groups(lines):
        head = f'<div class="it">{text.rich(label)}</div>' if label else ""
        ul = "<ul>" + "".join(f"<li>{text.rich(x)}</li>" for x in items) + "</ul>" if items else ""
        body += f'<div class="ig">{head}{ul}</div>'
    return f'<div class="rs"><div class="em">💡</div><div class="rb">{body}</div></div>'


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

def result_table_html(header, rows, highlight=None, title="📊 결과", defs=None, widths=None, note=None, num=(),
                      rich_cols=(), cls=""):
    """표 상자 (.res). rows의 칸은 이미 화면용 글자. highlight = 강조할 행 번호.
    num = 오른쪽 정렬할 숫자 칸 번호, rich_cols = yaml 글처럼 처리할 칸(**굵게** 등), note = 표 아래 설명 한 줄(앞에 💡),
    cls = 상자에 더할 클래스 (예: 'lh15' = 줄 간격 1.5)."""
    widths = widths or {}
    box = f"res {cls}".strip()      # cls는 아래 반복문에서 다른 뜻으로 쓰이므로 먼저 상자 클래스를 만든다
    th = ""
    for i, h in enumerate(header):
        style = ' style="width:%s"' % widths[i] if i in widths else ""
        cls = ' class="num"' if i in num else ""
        th += f"<th{style}{cls}>{esc(h)}</th>"
    trs = ""
    marked = set(highlight) if isinstance(highlight, (list, tuple, set)) else {highlight}   # 여러 줄 강조 가능
    for i, row in enumerate(rows):
        cls = ' class="hl"' if i in marked else ""
        tds = ""
        for j, c in enumerate(row):
            tcls = ' class="num"' if j in num else ""
            if isinstance(c, tuple):        # (본문, 아래 작은 회색 글)
                main, sub = c
                cell = esc(main) + (f'<div class="csub">{esc(sub)}</div>' if sub else "")
            else:
                cell = text.rich(c) if j in rich_cols else esc(c)
            tds += f"<td{tcls}>{cell}</td>"
        trs += f"<tr{cls}>{tds}</tr>"
    extra = f'<div class="defs">{"<br>".join("· " + text.rich(d) for d in defs)}</div>' if defs else ""
    extra += f'<div class="note tip"><span class="ai">💡</span><span>{text.rich(note)}</span></div>' if note else ""
    return f'<div class="{box}"><span>{esc(title)}</span><table class="rt"><tr>{th}</tr>{trs}</table>{extra}</div>'


# ---------- 프롬프트 보기 (성능 변화 > 실험 기록) ----------
FOLD_MIN = 8   # '- '로 시작하는 근거 줄이 이만큼 이어지면 접는다


def prompt_lines(stages_cfg, key):
    """stages.yaml에서 단계 프롬프트를 줄 목록으로. prompt_from이면 그 단계 것을 쓴다."""
    seen = set()
    s = stages_cfg.get(key) or {}
    while s.get("prompt_from") and s["prompt_from"] not in seen:
        seen.add(s["prompt_from"])
        s = stages_cfg.get(s["prompt_from"]) or {}
    return str(s.get("prompt") or "").rstrip("\n").split("\n") if s.get("prompt") else []


def prompt_marks(prev, cur):
    """직전 단계 대비 줄마다 추가·변경 여부 (True = + 표시). 직전 단계가 없으면 모두 False."""
    import difflib
    if not prev:
        return [False] * len(cur)
    marks = [True] * len(cur)
    for tag, _, _, j1, j2 in difflib.SequenceMatcher(a=prev, b=cur, autojunk=False).get_opcodes():
        if tag == "equal":
            for j in range(j1, j2):
                marks[j] = False
    return marks


def _line_html(line, added):
    g = "+" if added else ""
    return f'<div class="ln{" add" if added else ""}"><span class="g">{g}</span><span>{esc(line) or "&nbsp;"}</span></div>'


def prompt_code_html(lines, marks):
    """프롬프트 줄들. 근거 줄('- ')이 FOLD_MIN줄 이상 이어지고 표시가 같으면 <details>로 접는다."""
    out, i = [], 0
    while i < len(lines):
        j = i
        while j < len(lines) and lines[j].startswith("- ") and marks[j] == marks[i]:
            j += 1
        if lines[i].startswith("- ") and j - i >= FOLD_MIN:
            added = marks[i]
            label = "추가" if added else "변경 없음"
            out.append(f'<details class="fold{" add" if added else ""}"><summary>{label} · {j - i}줄 '
                       f'<span class="op">펼치기</span><span class="cl">접기</span></summary>'
                       + "".join(_line_html(x, added) for x in lines[i:j]) + "</details>")
            i = j
        else:
            out.append(_line_html(lines[i], marks[i]))
            i += 1
    return "".join(out)


def prompt_view_html(key, order, stages_cfg, f1=None, question=None):
    """프롬프트 1개 + 오른쪽 '이 단계에서 바뀐 점'. f1 = {단계: Macro F1} (결과 줄에 씀)."""
    from .loader import fix
    idx = order.index(key) if key in order else 0
    prev_key = order[idx - 1] if idx > 0 else None
    cur = prompt_lines(stages_cfg, key)
    prev = prompt_lines(stages_cfg, prev_key) if prev_key else []
    s = stages_cfg.get(key) or {}
    same = bool(prev) and cur == prev
    marks = [False] * len(cur) if same else prompt_marks(prev, cur)
    n_add = sum(marks)
    head_l = f'<span>{esc(question) + " · " if question else ""}<b>{esc(key)}</b> 프롬프트</span>'
    if prev_key and n_add:
        head_r = f'<span class="pv-key"><i>+</i>직전 단계({esc(prev_key)})에서 추가·변경된 줄 {n_add}줄</span>'
    elif same:
        head_r = '<span class="pv-key" style="color:#85B7EB">직전 단계와 같음</span>'
    else:
        head_r = '<span class="pv-key" style="color:#888780">첫 단계</span>'
    main = (f'<div class="pv-main"><div class="pv-head">{head_l}{head_r}</div>'
            f'<div class="pv-code">{prompt_code_html(cur, marks)}</div></div>')

    side = f'<span>이 단계에서 바뀐 점</span><b>{esc(s.get("change") or "—")}</b>'
    if s.get("prompt_note"):
        side += f'<div class="pn">{text.rich(s["prompt_note"])}</div>'
    if same:
        side += '<div class="pn">이 캐릭터 조회 프롬프트는 직전 단계와 같습니다.</div>'
    f1 = f1 or {}
    if f1.get(key) is not None:
        side += "<span>결과 · Macro F1</span>"
        if prev_key and f1.get(prev_key) is not None:
            label, state = delta(f1[key], f1[prev_key])
            side += (f'<div class="rv">{fix(f1[prev_key])} → {fix(f1[key])}</div>'
                     f'<div class="dl {state}">{esc(label)}</div>')
        else:
            side += f'<div class="rv">{fix(f1[key])}</div>'
    return f'<div class="pv">{main}<div class="pv-side">{side}</div></div>'


# ---------- 단계별 프롬프트 표 (성능 변화 > 실험 기록). '⧉ 프롬프트 보기'를 누르면 모달로 prompt_view_html ----------
PROMPT_ICON = "⧉"                       # 새 창(모달)이 열린다는 뜻의 아이콘
PROMPT_BTN = f"{PROMPT_ICON} 프롬프트 보기"
PROMPT_HEAD = ["단계", "이 단계에서 바뀐 점", "Macro F1", "프롬프트 변경"]   # 마지막 칸 = '⧉ 프롬프트 보기' 버튼
PROMPT_WIDTHS = ["104px", None, "150px", "128px"]   # None = 남는 너비


def prompt_cells(key, order, stages_cfg, f1=None):
    """표 한 줄의 앞 칸 3개(HTML): 단계 · 바뀐 점 · Macro F1(이번 값 + 직전 대비 변화). 마지막 칸(버튼)은 부르는 쪽에서."""
    from .loader import fix
    idx = order.index(key) if key in order else 0
    prev_key = order[idx - 1] if idx > 0 else None
    f1 = f1 or {}
    score = ""
    if f1.get(key) is not None:
        if prev_key and f1.get(prev_key) is not None:
            label, state = delta(f1[key], f1[prev_key])
            score = f'{fix(f1[key])}<span class="dl {state}">{esc(label)}</span>'
        else:
            score = fix(f1[key])
    change = (stages_cfg.get(key) or {}).get("change") or "—"
    return [f"<b>{esc(key)}</b>", esc(change), score]


PROMPT_NOTE = "모든 단계에서 같은 캐릭터 조회 질문을 사용한 프롬프트 예시입니다."


def prompt_title_html():
    """Streamlit 화면의 단계별 프롬프트 표 제목 + 설명 (표 상자는 st-key-ptab 컨테이너)."""
    return f'<span class="pt-t">단계별 프롬프트</span><div class="pt-n">{esc(PROMPT_NOTE)}</div>'


def prompt_table_html(keys, order, stages_cfg, f1=None, current=None, button=None):
    """단계별 프롬프트 표 (.res 상자). button(단계) -> 마지막 칸 HTML (와이어프레임용 모달 버튼). 지금 단계 줄은 강조."""
    cols = "".join(f'<col style="width:{w}">' if w else "<col>" for w in PROMPT_WIDTHS)
    th = "".join(f"<th>{esc(h)}</th>" for h in PROMPT_HEAD)
    trs = ""
    for k in keys:
        cells = prompt_cells(k, order, stages_cfg, f1) + [button(k) if button else ""]
        hl = ' class="hl"' if k == current else ""
        trs += f"<tr{hl}>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>"
    return (f'<div class="res ptab"><span>단계별 프롬프트</span>'
            f'<div class="note" style="margin:-4px 0 10px">{esc(PROMPT_NOTE)}</div>'
            f'<table class="rt"><colgroup>{cols}</colgroup><tr>{th}</tr>{trs}</table></div>')


def _item_html(item):
    """주요 발견 한 줄: {title, desc, sub, items} 또는 글자."""
    if isinstance(item, str):
        return f"<li>{text.rich(item)}</li>"
    body = f'<b>{text.rich(item["title"])}</b>' if item.get("title") else ""
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
