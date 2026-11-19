"""챗봇 웹 화면(demo/app.py)의 화면과 상관없는 로직: 메시지 만들기, 한국 시간 표시, UID 검사.

streamlit을 import하지 않는다 -> unittest로 검사한다 (tests/test_demo_chat_logic.py).

메시지 dict (컴포넌트 data.messages의 한 칸, 화면 그리기: demo/ui/chat.js)
- user      : {id, role:"user", kind:"qa"|"build", text, uid?, time, date}
- assistant : {id, role:"assistant", kind, status:"pending"|"ok"|"error", question, message, rich,
               notes:[{level:"warn"|"info"|"err"|"orange", text}], sources:[{k,t,id,x}], seconds, party?, uid?, steps?}
- guide     : {id, role:"guide", kind:"help"|"build_guide"|"build_ready", date, uid?}
  guide는 사용법·안내라서 나중에 DB 대화 기록에 저장하지 않는다 (saveable 참고)
"""
import re
from datetime import datetime
from zoneinfo import ZoneInfo

try:                                    # tests: from demo import chat_logic
    from . import client
except ImportError:                     # streamlit run demo/app.py: import chat_logic
    import client

KST = ZoneInfo("Asia/Seoul")
WEEKDAYS = "월화수목금토일"     # datetime.weekday(): 월요일 = 0

# 입력창 위 예시 칩 (와이어프레임 v10 그대로). build=True는 UID 입력 모드로 바꾸는 칩
EXAMPLES = [
    {"cat": "빌드 추천", "q": "맞춤 빌드·파티 추천받기", "build": True},
    {"cat": "캐릭터", "q": "카즈하의 원소와 무기 종류는 뭐야?"},
    {"cat": "무기", "q": "천공의 검의 기초 공격력과 부옵션은 뭐야?"},
    {"cat": "성유물", "q": "청록색 그림자 4세트 효과는 뭐야?"},
    {"cat": "패치 변경", "q": "7.2 패치에서 새로 추가된 캐릭터는 누구야?"},
]

# 화면 안내 문구 (와이어프레임 v10)
SERVER_DOWN = "🚨 서버 응답이 없어요. 서버 상태를 확인해 주세요."
NOT_FOUND = "⚠️ 찾지 못했어요. 지금 가진 데이터에는 이 질문의 근거가 없어요."
RECHECK = "ℹ️ 재확인 필요: 빌드 정보는 패치에 따라 바뀔 수 있어 게임에서 한 번 더 확인해 주세요."
NO_API_URL = "🚨 서버 주소가 설정되지 않았어요. Streamlit secrets에 API_URL을 넣어 주세요."
# 이 오류들은 와이어프레임의 "서버 응답이 없어요"로 보여 준다. 나머지는 client 안내 문구 그대로
SERVER_DOWN_ERRORS = {client.MSG_SERVER_OFF, client.MSG_TIMEOUT}

# 출처 패널 라벨: 근거 kind (core/retrieval.py) -> 한국어. 표에 없으면 원래 값
KIND_LABELS = {"character": "캐릭터", "weapon": "무기", "artifact": "성유물", "patch": "패치",
               "build_card": "빌드", "recheck": "재확인"}

UID_RE = re.compile(r"^\d{9,10}$")    # 정규식: 처음(^)부터 끝($)까지 숫자(\d)만 9~10개


# ----- 시간 (한국 시간) -----
def now_kst():
    """지금 한국 시각. 서버(Streamlit Cloud)는 외국 시간대일 수 있어서 항상 한국 시간으로 고정한다."""
    return datetime.now(KST)


def to_kst(dt):
    """시간대가 없는 값은 한국 시간으로 보고, 있는 값은 한국 시간으로 바꾼다."""
    return dt.replace(tzinfo=KST) if dt.tzinfo is None else dt.astimezone(KST)


def fmt_time(dt):
    """질문 시각: '오후 3:05' (와이어프레임 hm 함수와 같은 모양)"""
    dt = to_kst(dt)
    ap = "오전" if dt.hour < 12 else "오후"
    # 24시간 -> 12시간: 15시 % 12 = 3. 0시·12시는 0이 되므로 `or 12`로 12를 쓴다. :02d = 두 자리(05)
    return f"{ap} {dt.hour % 12 or 12}:{dt.minute:02d}"


def fmt_date(dt):
    """날짜 구분선: '2026년 11월 16일 (월)'"""
    dt = to_kst(dt)
    return f"{dt.year}년 {dt.month}월 {dt.day}일 ({WEEKDAYS[dt.weekday()]})"


# ----- UID -----
def is_uid(text):
    """원신 UID 모양(숫자 9~10자리)인지. 실제로 있는 UID인지는 알 수 없다."""
    return bool(UID_RE.match(str(text or "").strip()))


# ----- 메시지 만들기 -----
def next_id(messages):
    """새 메시지 번호 = 지금까지 가장 큰 번호 + 1 (메시지가 없으면 1).
    화면(chat.js)은 이 번호로 "이미 그린 메시지"를 구분해서 새 메시지만 추가로 그린다."""
    return max((m["id"] for m in messages), default=0) + 1


def user_message(mid, text, now):
    """사용자가 보낸 질문 말풍선. time = 말풍선 옆 시각, date = 날짜가 바뀔 때 보여 줄 구분선."""
    return {"id": mid, "role": "user", "kind": "qa", "text": text.strip(),
            "time": fmt_time(now), "date": fmt_date(now)}


def build_user_message(mid, uid, now):
    """빌드 추천 모드에서 UID를 보냈을 때의 사용자 말풍선 ("UID 123456789 빌드 추천")."""
    uid = uid.strip()
    return {"id": mid, "role": "user", "kind": "build", "text": f"UID {uid} 빌드 추천", "uid": uid,
            "time": fmt_time(now), "date": fmt_date(now)}


def pending_message(mid, question, kind="qa", steps=None):
    """답을 기다리는 동안 보여 줄 카드 ("답을 찾고 있어요…").
    steps: 빌드 추천처럼 단계별 로딩 문구를 보여 줄 때만 넘긴다. 답이 오면 replace_message 로 바뀐다."""
    m = assistant_message(mid, question, status="pending", kind=kind)
    if steps:
        m["steps"] = list(steps)
    return m


def assistant_message(mid, question, status="ok", message="", notes=None, sources=None,
                      seconds=None, kind="qa", rich=False, **extra):
    """답 카드. rich=True(HTML 그대로 표시)는 가짜 모드의 고정 문구에만 쓴다. 서버 답은 항상 False.

    status: pending(대기) / ok(정상) / error(빨간 오류). notes: 답 아래 색깔 안내 목록.
    sources: 출처 패널 목록. **extra: 그 밖에 붙일 칸(party, uid 등)을 이름=값으로 받는다."""
    m = {"id": mid, "role": "assistant", "kind": kind, "status": status, "question": question,
         "message": message, "rich": bool(rich), "notes": list(notes or []),
         "sources": list(sources or []), "seconds": seconds}
    m.update(extra)      # extra 칸을 m에 합친다
    return m


def error_message(mid, question, text=SERVER_DOWN, kind="qa"):
    """빨간 오류 카드 (서버 무응답 등)."""
    return assistant_message(mid, question, status="error", notes=[note("err", text)], kind=kind)


def source_item(ev):
    """근거 1개 -> 출처 패널 한 칸 {k: 종류, t: 제목, id: 문서 id, x: 본문}."""
    ev = client.format_evidence(ev)
    return {"k": KIND_LABELS.get(ev["kind"], ev["kind"] or "근거"), "t": ev["title"],
            "id": ev["doc_id"], "x": ev["text"]}


def answer_from_result(mid, question, result):
    """client.ask_api 결과 -> 답 카드.

    - 서버 꺼짐·시간 초과 -> 빨간 SERVER_DOWN, 그 밖의 오류 -> 빨간 상자에 client 안내 그대로
    - found=false -> 노란 NOT_FOUND, needs_recheck -> 회색 RECHECK
    """
    # 1) 서버 호출 실패 -> 빨간 오류 카드
    if not result.get("ok"):
        err = result.get("error") or SERVER_DOWN
        return error_message(mid, question, SERVER_DOWN if err in SERVER_DOWN_ERRORS else f"🚨 {err}")
    # 2) 성공 -> 답 문장 + 상태 안내 + 근거 목록(출처 패널용)
    data = result["data"]
    notes = []
    if not data.get("found", True):
        notes.append(note("warn", NOT_FOUND))
    if data.get("needs_recheck"):
        notes.append(note("info", RECHECK))
    return assistant_message(mid, question, message=data.get("message", ""), notes=notes,
                             sources=[source_item(ev) for ev in data.get("evidence") or []],
                             seconds=result.get("seconds"))


def guide_message(mid, kind, now, uid=None):
    """안내 카드. 글은 화면(chat.js의 GUIDE)에 있고, 여기서는 어떤 안내인지(kind)만 정한다.
    kind: help(사용법) / build_guide(빌드 추천 안내) / build_ready(UID 확인 후 "준비 중")."""
    m = {"id": mid, "role": "guide", "kind": kind, "date": fmt_date(now)}
    if uid:
        m["uid"] = uid
    return m


def note(level, text):
    """답 아래 안내 한 줄. level = 색: err(빨강) / warn(노랑) / info(회색) / orange(주황)."""
    return {"level": level, "text": text}


def replace_message(messages, new):
    """같은 id의 메시지를 새 것으로 바꾼 목록 (대기 카드 -> 답 카드)."""
    return [new if m["id"] == new["id"] else m for m in messages]


def saveable(messages):
    """DB 대화 기록에 저장할 메시지: guide(사용법·안내)와 대기 중 카드는 뺀다."""
    return [m for m in messages
            if m["role"] != "guide" and not (m["role"] == "assistant" and m["status"] == "pending")]


def view_data(messages, busy=False):
    """파이썬 -> 화면(chat.js)으로 넘기는 data. 이 값이 바뀔 때마다 화면이 다시 그려진다.
    busy=True 면 화면이 입력을 막는다 (답을 만드는 중에 두 번 보내지 않게)."""
    return {"messages": list(messages), "busy": bool(busy), "examples": EXAMPLES}
