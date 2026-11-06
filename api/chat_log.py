"""대화 기록 저장 (FR-09). /ask 응답 1개 = chat_logs 표 1줄 (칸 설명: db/schema.sql 4번).

접속 주소는 환경변수 DATABASE_URL, 없으면 프로젝트 루트 .env 의 DATABASE_URL 을 쓴다.
둘 다 없으면 저장하지 않고 넘어간다 (DB 없이 로컬 개발·테스트 가능).
"""
import json
import os
from pathlib import Path

ENV_FILE = Path(__file__).resolve().parent.parent / ".env"
CONNECT_TIMEOUT = 10     # 초. Neon 무료 요금제는 잠들었다 깨어나는 데 몇 초 걸린다

INSERT_SQL = """
INSERT INTO chat_logs (question, route, answer, message, evidence, found, needs_recheck,
                       model, method, data_version, seconds, retrieved_doc_ids)
VALUES (%s, %s, %s::jsonb, %s, %s::jsonb, %s, %s, %s, %s, %s, %s, %s)
"""


def database_url():
    """환경변수 -> .env 순서로 DATABASE_URL 을 찾는다. .env 의 다른 값은 건드리지 않는다."""
    url = os.environ.get("DATABASE_URL")
    if url:
        return url
    if ENV_FILE.exists():
        from dotenv import dotenv_values
        return dotenv_values(ENV_FILE).get("DATABASE_URL")
    return None


def doc_ids_of(response):
    """응답 근거의 doc_id 목록 (문서가 아닌 근거는 뺀다). 하나도 없으면 None(NULL)."""
    ids = [e["doc_id"] for e in response.get("evidence", []) if e.get("doc_id")]
    return ids or None


def save_chat_log(response, seconds, retrieved_doc_ids=None):
    """응답(dict) 1개를 chat_logs 에 1줄 저장한다. 저장했으면 True, 주소가 없어 건너뛰면 False."""
    url = database_url()
    if not url:
        return False
    import psycopg      # 설치 안 된 환경에서도 api.main 을 불러올 수 있게 여기서 불러온다
    params = (
        response["question"],
        response["route"],
        json.dumps(response["answer"], ensure_ascii=False),
        response["message"],
        json.dumps(response["evidence"], ensure_ascii=False),
        response["found"],
        response["needs_recheck"],
        response["model"],
        response["method"],
        response["data_version"],
        seconds,
        retrieved_doc_ids if retrieved_doc_ids is not None else doc_ids_of(response),
    )
    with psycopg.connect(url, connect_timeout=CONNECT_TIMEOUT) as conn:   # 블록이 끝나면 자동 commit
        conn.execute(INSERT_SQL, params)
    return True


def log_chat_safely(response, seconds):
    """BackgroundTasks 에서 부르는 함수. 저장이 실패해도 오류만 출력한다 (응답은 이미 나갔다)."""
    try:
        save_chat_log(response, seconds)
    except Exception as e:      # 접속 실패, 표 없음 등 무엇이든
        print(f"[chat_log] 대화 기록 저장 실패: {type(e).__name__}: {e}")
