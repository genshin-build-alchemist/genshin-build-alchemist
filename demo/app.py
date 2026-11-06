"""챗봇 웹 화면 (Streamlit). 질문 -> /ask 응답의 답(message), 근거(evidence), 응답 시간을 보여 준다.

로컬 실행 (프로젝트 루트에서): streamlit run demo/app.py
서버 주소는 Streamlit secrets의 API_URL에서 읽는다 (설명: demo/README.md)
"""
import sys
from pathlib import Path

import streamlit as st

# streamlit run demo/app.py 로 실행해도 같은 폴더의 client.py를 찾도록
sys.path.insert(0, str(Path(__file__).resolve().parent))
from client import ask_api, format_evidence, status_notes, MAX_QUESTION  # noqa: E402

# docs/demo_scenario.md 시연 질문 (패치 질문 제외)
EXAMPLES = [
    "카에데하라 카즈하 원소 뭐야?",
    "카즈하는 몇 성이에요?",
    "이나즈마 출신 바람 원소 캐릭터 누구 있어?",
    "카즈하 원소 스킬 어떤 거야?",
    "카즈하 좋아하는 음식 뭐야?",
]


def read_api_url():
    """secrets의 API_URL. 파일이 없거나 값이 없으면 None."""
    try:
        return st.secrets.get("API_URL")
    except Exception:       # secrets 파일 자체가 없을 때
        return None


def pick_example(q):
    st.session_state.question = q
    st.session_state.auto_submit = True


def show_result(result):
    if not result["ok"]:
        st.error(result["error"])
        return
    data = result["data"]
    st.subheader("답")
    st.write(data.get("message", ""))
    for level, text in status_notes(data):
        (st.warning if level == "warning" else st.info)(text)

    st.subheader("응답 시간")
    st.write(f"{result['seconds']:.2f}초")
    st.caption(f"경로 {data.get('route', '-')} · 모델 {data.get('model', '-')} · "
               f"데이터 {data.get('data_version', '-')}")

    evidence = data.get("evidence") or []
    st.subheader(f"근거 {len(evidence)}개")
    if not evidence:
        st.caption("근거 문서 없음")
    for ev in map(format_evidence, evidence):
        label = f"[{ev['kind']}] {ev['title']}" if ev["kind"] else ev["title"]
        with st.expander(label):
            st.caption(f"doc_id: {ev['doc_id']}")
            st.text(ev["text"])


st.set_page_config(page_title="Genshin Build Alchemist", page_icon="🌬️")
st.title("원신 캐릭터 챗봇")
st.caption("캐릭터 데이터에서 근거를 찾아 답해요. 근거가 없으면 지어내지 않고 '찾지 못했어요'라고 답해요.")

api_url = read_api_url()
if not api_url:
    st.error("서버 주소가 설정되지 않았어요. Streamlit secrets에 API_URL을 넣어 주세요 (demo/README.md 참고).")
    st.stop()

st.write("예시 질문")
cols = st.columns(len(EXAMPLES))
for col, q in zip(cols, EXAMPLES):
    col.button(q, on_click=pick_example, args=(q,))

with st.form("ask_form"):
    question = st.text_input("질문", key="question", max_chars=MAX_QUESTION,
                             placeholder="예: 알베도 원소가 뭐야?")
    submitted = st.form_submit_button("질문하기")

if submitted or st.session_state.pop("auto_submit", False):
    with st.spinner("답변 생성 중... (실제 모델은 몇 초 걸려요)"):
        st.session_state.result = ask_api(api_url, question)

if "result" in st.session_state:
    show_result(st.session_state.result)
