"""챗봇 웹 화면 (Streamlit + Custom Components v2). 화면은 demo/ui/의 HTML/CSS/JS, 파이썬은 데이터만 주고받는다.

로컬 실행 (프로젝트 루트에서): streamlit run demo/app.py
가짜 모드 (서버 없이 와이어프레임 답변): CHAT_UI_FAKE=1 streamlit run demo/app.py
서버 주소는 Streamlit secrets의 API_URL에서 읽는다 (설명: demo/README.md)

흐름: 화면에서 질문(trigger "ask") -> 질문 + 대기 카드를 대화에 넣고 다시 그림
      -> 다음 실행에서 화면을 그린 뒤 답을 만들어 대기 카드를 바꾸고 다시 그림
"""
import os
import sys
import time
from pathlib import Path

import streamlit as st

HERE = Path(__file__).resolve().parent
# streamlit run demo/app.py 로 실행해도 같은 폴더의 파일을 찾도록
sys.path.insert(0, str(HERE))
import chat_logic as cl  # noqa: E402
import fake  # noqa: E402
from client import ask_api  # noqa: E402

UI = HERE / "ui"
FAKE = os.environ.get("CHAT_UI_FAKE") == "1"

# Streamlit 기본 화면 요소(헤더, 툴바, 여백)를 숨겨서 컴포넌트가 화면 전체를 쓰게 한다
HIDE_CHROME = """<style>
header[data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stDecoration"],
[data-testid="stStatusWidget"], [data-testid="stSkillsNudge"], #MainMenu, footer {display:none !important;}
[data-testid="stMainBlockContainer"] {padding:0 !important; max-width:none !important;}
</style>"""
# 화면(chat.js)이 파이썬에 보내는 신호 이름: ask=질문, build=UID, help=사용법, build_guide=빌드 안내
TRIGGERS = ("ask", "build", "help", "build_guide")


@st.cache_resource
def chat_component():
    """화면 파일 3개를 읽어 컴포넌트를 한 번만 등록한다.
    @st.cache_resource: Streamlit은 화면이 바뀔 때마다 이 파일을 처음부터 다시 실행하는데,
    이 표시가 있으면 첫 실행 결과를 기억해 두고 다시 만들지 않는다 (ui 파일을 고치면 껐다 켜야 반영)."""
    read = lambda name: (UI / name).read_text(encoding="utf-8")  # noqa: E731
    return st.components.v2.component(
        "gb_chat", html=read("chat.html"), css=read("chat.css"), js=read("chat.js"))


def handle_event(name, value):
    """화면 이벤트 -> 대화 목록 변경. 답을 만들어야 하면 ss.job에 할 일을 남긴다.

    여기서는 서버를 부르지 않는다. 질문과 대기 카드를 먼저 화면에 보여 주고,
    실제 답은 다음 실행에서 run_job 이 만든다 (기다리는 동안 화면이 멈춰 보이지 않게)."""
    msgs, now = ss.messages, cl.now_kst()
    mid = cl.next_id(msgs)
    if name == "ask":
        text = str(value or "").strip()
        if not text:
            return
        # 내 질문(mid) + 대기 카드(mid+1)를 붙이고, "mid+1 카드 자리에 답을 넣어라"는 할 일을 남긴다
        msgs += [cl.user_message(mid, text, now), cl.pending_message(mid + 1, text)]
        ss.job = {"type": "ask", "id": mid + 1, "question": text}
    elif name == "build":
        uid = str(value or "").strip()
        if not cl.is_uid(uid):          # 화면에서 막지만 한 번 더 확인
            return
        msgs.append(cl.build_user_message(mid, uid, now))
        if FAKE:                        # 가짜 모드: 로딩 단계 -> 파티 카드
            msgs.append(cl.pending_message(mid + 1, f"UID {uid} 빌드 추천", kind="build",
                                           steps=fake.BUILD_STEPS))
            ss.job = {"type": "build", "id": mid + 1, "uid": uid}
        else:                           # 서버에 빌드 기능이 없음 -> "준비 중" 안내
            msgs.append(cl.guide_message(mid + 1, "build_ready", now, uid=uid))
    elif name in ("help", "build_guide"):
        msgs.append(cl.guide_message(mid, name, now))


def run_job(job):
    """대기 카드 자리에 들어갈 답 카드를 만든다 (화면을 그린 뒤 실행).
    순서: 빌드(가짜) -> 가짜 모드 -> 서버 주소 확인 -> 실제 서버 호출."""
    if job["type"] == "build":          # 가짜 모드에서만 생김
        msg, delay = fake.build_answer(job["id"], job["uid"])
        time.sleep(delay)
        return msg
    if FAKE:
        msg, delay = fake.answer(job["id"], job["question"])
        time.sleep(delay)
        return msg
    api_url = read_api_url()
    if not api_url:
        return cl.error_message(job["id"], job["question"], cl.NO_API_URL)
    result = ask_api(api_url, job["question"])
    return cl.answer_from_result(job["id"], job["question"], result)


def read_api_url():
    """secrets의 API_URL. 파일이 없거나 값이 없으면 None.
    로컬은 .streamlit/secrets.toml, 배포는 Streamlit Cloud 설정 화면의 Secrets에 넣는다 (깃에 안 올림)."""
    try:
        return st.secrets.get("API_URL")
    except Exception:       # secrets 파일 자체가 없을 때
        return None


st.set_page_config(page_title="여행자 가이드봇", page_icon="✨", layout="wide")
st.html(HIDE_CHROME)

# session_state: 다시 실행돼도 남아 있는 보관함 (브라우저 탭 1개마다 따로, 새로고침하면 비워짐)
ss = st.session_state
ss.setdefault("messages", [])     # 대화 목록. 처음 한 번만 빈 목록으로 만든다
ss.setdefault("job", None)        # 아직 못 끝낸 할 일 (답 만들기). 없으면 None

# 화면을 그린다. data = 파이썬 -> 화면, result = 화면 -> 파이썬 (사용자가 보낸 신호)
# on_..._change: 신호를 받을 이름을 등록하는 자리. 할 일은 아래에서 직접 처리해서 빈 함수(lambda: None)
chat = chat_component()
result = chat(key="chat", data=cl.view_data(ss.messages, busy=ss.job is not None),
              **{f"on_{t}_change": lambda: None for t in TRIGGERS})

# 1) 화면 이벤트: 답을 만드는 중이면 무시 (두 번 눌림 방지)
if ss.job is None:
    for t in TRIGGERS:
        value = getattr(result, t, None)   # 이번 실행에 그 신호가 왔으면 값, 아니면 None
        if value is not None:
            handle_event(t, value)
            st.rerun()                     # 바뀐 대화(질문 + 대기 카드)로 지금 바로 다시 그림

# 2) 남은 일: 화면에 대기 카드가 그려진 뒤 답을 만들고 다시 그린다
if ss.job is not None:
    ss.messages = cl.replace_message(ss.messages, run_job(ss.job))   # 대기 카드 -> 답 카드
    ss.job = None                                                    # 할 일 끝
    st.rerun()                                                       # 답이 들어간 화면으로 다시 그림
