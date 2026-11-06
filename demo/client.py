"""웹 화면(demo/app.py)이 챗봇 API(POST /ask)를 부르는 부분.

streamlit을 import하지 않는다 -> 화면 없이 unittest로 검사할 수 있다 (tests/test_demo_client.py).
"""
import time

import httpx

# ngrok 무료 주소는 처음 접속하면 경고 페이지(HTML)를 보여 준다. 이 헤더가 있으면 건너뛴다
HEADERS = {"ngrok-skip-browser-warning": "true"}
# 연결은 10초 안에 안 되면 꺼진 것으로 보고, 답은 실제 모델이 느릴 수 있어 120초까지 기다린다
TIMEOUT = httpx.Timeout(120.0, connect=10.0)
MAX_QUESTION = 300      # api/main.py AskRequest의 max_length와 같게

MSG_EMPTY = "질문을 입력해 주세요."
MSG_TOO_LONG = f"질문은 {MAX_QUESTION}자 이내로 적어 주세요."
MSG_SERVER_OFF = "지금은 서버가 꺼져 있어요. 잠시 뒤에 다시 시도해 주세요."
MSG_TIMEOUT = "답이 너무 오래 걸려요. 잠시 뒤에 다시 시도해 주세요."
MSG_BAD_URL = "서버 주소(API_URL)가 올바르지 않아요. http:// 또는 https://로 시작하는지 확인해 주세요."
MSG_BAD_QUESTION = "서버가 질문을 받지 못했어요. 질문을 조금 바꿔서 다시 시도해 주세요."
MSG_BAD_RESPONSE = "서버 응답을 읽지 못했어요. 서버 주소가 챗봇 API가 맞는지 확인해 주세요."
NO_DOC_ID = "문서 id 없음"

# ngrok: 404 = 주소가 꺼짐(ERR_NGROK_3200), 502 = 터널은 있는데 코랩 서버가 꺼짐
SERVER_OFF_CODES = {404, 502, 503, 504}


def _result(ok, seconds, data=None, error=None):
    return {"ok": ok, "data": data, "error": error, "seconds": round(seconds, 2)}


def ask_api(api_url, question, timeout=TIMEOUT):
    """질문을 보내고 결과를 돌려준다. 오류가 나도 예외를 던지지 않고 안내 문구를 담아 돌려준다.

    돌려주는 값: {"ok": bool, "data": API 응답 dict 또는 None, "error": 안내 문구 또는 None,
                 "seconds": 화면에서 잰 응답 시간(요청 보낸 시각 ~ 받은 시각)}
    """
    question = (question or "").strip()
    if not question:
        return _result(False, 0.0, error=MSG_EMPTY)
    if len(question) > MAX_QUESTION:
        return _result(False, 0.0, error=MSG_TOO_LONG)

    url = (api_url or "").strip().rstrip("/") + "/ask"
    start = time.perf_counter()
    try:
        r = httpx.post(url, json={"question": question}, headers=HEADERS, timeout=timeout)
    except (httpx.UnsupportedProtocol, httpx.InvalidURL):
        return _result(False, time.perf_counter() - start, error=MSG_BAD_URL)
    except (httpx.ConnectError, httpx.ConnectTimeout):
        return _result(False, time.perf_counter() - start, error=MSG_SERVER_OFF)
    except httpx.TimeoutException:          # 연결은 됐는데 답이 120초 넘게 안 옴
        return _result(False, time.perf_counter() - start, error=MSG_TIMEOUT)
    except httpx.RequestError:              # 그 밖의 네트워크 오류
        return _result(False, time.perf_counter() - start, error=MSG_SERVER_OFF)
    seconds = time.perf_counter() - start

    if r.status_code in SERVER_OFF_CODES:
        return _result(False, seconds, error=MSG_SERVER_OFF)
    if r.status_code == 422:
        return _result(False, seconds, error=MSG_BAD_QUESTION)
    if r.status_code != 200:
        return _result(False, seconds, error=f"서버에서 오류가 났어요 (오류 코드 {r.status_code}).")
    try:
        data = r.json()
    except ValueError:                      # HTML 경고 페이지 등 JSON이 아닌 응답
        return _result(False, seconds, error=MSG_BAD_RESPONSE)
    if not isinstance(data, dict) or "message" not in data:
        return _result(False, seconds, error=MSG_BAD_RESPONSE)
    return _result(True, seconds, data=data)


def format_evidence(ev):
    """근거 1개를 화면용 dict로. doc_id가 null이거나 칸이 없어도 오류 없이 표시한다."""
    ev = ev if isinstance(ev, dict) else {}
    return {
        "kind": ev.get("kind") or "",
        "title": ev.get("title") or "(제목 없음)",
        "doc_id": ev.get("doc_id") or NO_DOC_ID,
        "text": ev.get("text") or "",
    }


def status_notes(data):
    """found / needs_recheck에 따라 보여 줄 안내 목록. [(종류, 문구)], 종류는 "info" 또는 "warning"."""
    notes = []
    if not data.get("found", True):
        notes.append(("info", "찾지 못했어요. 지금 가진 데이터에는 이 질문의 근거가 없어요."))
    if data.get("needs_recheck"):
        notes.append(("warning", "재확인 필요: 빌드 정보는 패치에 따라 바뀔 수 있어 게임에서 한 번 더 확인해 주세요."))
    return notes
