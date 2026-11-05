"""챗봇 API (FR-07). 질문을 받아 답·경로·근거·데이터 존재 여부를 돌려준다.

실행 (프로젝트 루트에서):
    pip install -r requirements.txt && uvicorn api.main:app --reload
확인:
    http://127.0.0.1:8000/docs  (브라우저에서 바로 질문을 보내 볼 수 있는 화면)

기본은 모의 답변기(규칙 기반)라 GPU 없이 로컬 PC에서 돈다.
실제 LLM은 코랩에서 core.answer.LLMAnswerer(generate_fn) 를 넣어 Chatbot을 만들면 된다.
"""
# TODO(D) 서비스. 위에서부터 순서대로, 끝나면 [ ] -> [x]
#  1. [ ] Neon(neon.com)에 DB 만들기 -> 접속 주소를 A에게 DM (채널에 올리지 않기). 표 만들기는 A가 주는 코랩 셀로
#  2. [ ] 프로젝트 루트 .env 파일에 DATABASE_URL=... 넣고 로컬에서 접속 확인 (.env는 깃에 안 올라감)
#  3. [ ] 아래 ask()에서 대화 기록을 chat_logs 표에 저장 (칸 설명: db/schema.sql 4번)
#  4. [ ] 웹 화면 고르기: Gradio 또는 Streamlit. 질문 입력 -> message, 근거(evidence), 응답 시간 보여 주기
#  5. [ ] 코랩 + ngrok으로 실제 모델(Qwen) API 띄우기 -> 웹 화면에서 접속 (README '코랩에서 실제 LLM 연결하기')
#  6. [ ] 전후 비교 대시보드: dashboard/README.md
#  막히면: A에게 질문
from fastapi import FastAPI
from pydantic import BaseModel, Field

from core.kb import load_kb
from core.pipeline import Chatbot

app = FastAPI(title="Genshin Build Alchemist", version="0.1.0")
bot = Chatbot(load_kb())


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=300, examples=["알베도 원소가 뭐야?"])


class Evidence(BaseModel):
    kind: str
    title: str
    text: str


class AskResponse(BaseModel):
    question: str
    route: str
    answer: list[str]
    message: str
    evidence: list[Evidence]
    found: bool
    needs_recheck: bool
    model: str
    method: str
    data_version: str


@app.get("/health")
def health():
    kb = bot.kb
    return {"status": "ok", "characters": len(kb.characters), "patch_versions": kb.versions,
            "build_cards": len(kb.build_cards), "model": bot.answerer.name}


@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest):
    # TODO(D) 3번: 대화 기록 저장 (FR-09)
    #  - 걸린 시간을 재서(time.perf_counter) 응답과 같이 chat_logs에 넣는다: seconds, retrieved_doc_ids 칸도 있음
    #  - answer·evidence는 JSONB 칸이라 json.dumps(..., ensure_ascii=False)로 넣는다
    #  - DB 저장이 실패해도 답은 그대로 돌려준다 (try/except로 감싸고 오류만 출력)
    #  - 테스트: tests/test_api_db.py 에 저장 테스트 추가
    return bot.ask(req.question)
