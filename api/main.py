"""챗봇 API (FR-07). 질문을 받아 답·경로·근거·데이터 존재 여부를 돌려준다.

실행 (프로젝트 루트에서):
    pip install -r requirements.txt && uvicorn api.main:app --reload
확인:
    http://127.0.0.1:8000/docs  (브라우저에서 바로 질문을 보내 볼 수 있는 화면)

답변기는 환경변수 GBA_ANSWERER로 고른다 (설명: core/llm.py 맨 위)
    mock (기본) : 규칙 기반 모의 답변기. GPU·torch 없이 로컬 PC에서 화면·API를 개발할 때
    llm         : 실제 모델(Qwen2.5-3B, rag_v4 프롬프트 + 후처리). 평가 점수(macro F1 0.846)와 같은 설정
실제 모델로 실행 (맥·리눅스, 프로젝트 루트에서):
    pip install -r requirements.txt -r requirements-llm.txt && GBA_ANSWERER=llm uvicorn api.main:app
"""
# TODO(D) 서비스. 위에서부터 순서대로, 끝나면 [ ] -> [x]
#  1. [ ] Neon(neon.com)에 DB 만들기 -> 접속 주소를 A에게 DM (채널에 올리지 않기). 표 만들기는 A가 주는 코랩 셀로
#  2. [ ] 프로젝트 루트 .env 파일에 DATABASE_URL=... 넣고 로컬에서 접속 확인 (.env는 깃에 안 올라감)
#  3. [ ] 아래 ask()에서 대화 기록을 chat_logs 표에 저장 (칸 설명: db/schema.sql 4번)
#  4. [ ] 웹 화면 고르기: Gradio 또는 Streamlit. 질문 입력 -> message, 근거(evidence), 응답 시간 보여 주기
#  5. [ ] 코랩 + ngrok으로 실제 모델(Qwen) API 띄우기 -> 웹 화면에서 접속 (README '실제 모델로 API 실행하기')
#         API는 GBA_ANSWERER=llm 이면 실제 모델을 쓴다 (core/llm.py). D는 코랩에서 띄우고 ngrok 주소만 연결하면 된다
#  6. [ ] 전후 비교 대시보드: dashboard/README.md
#  막히면: A에게 질문
from fastapi import FastAPI
from pydantic import BaseModel, Field

from core.kb import load_kb
from core.llm import answerer_from_env
from core.pipeline import Chatbot

app = FastAPI(title="Genshin Build Alchemist", version="0.1.0")
bot = Chatbot(load_kb(), answerer_from_env())


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
            "build_cards": len(kb.build_cards), "model": bot.answerer.name,
            "method": getattr(bot.answerer, "method", "rag"),
            "postprocess": getattr(bot.answerer, "postprocess", False)}


@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest):
    # TODO(D) 3번: 대화 기록 저장 (FR-09)
    #  - 걸린 시간을 재서(time.perf_counter) 응답과 같이 chat_logs에 넣는다: seconds, retrieved_doc_ids 칸도 있음
    #  - answer·evidence는 JSONB 칸이라 json.dumps(..., ensure_ascii=False)로 넣는다
    #  - DB 저장이 실패해도 답은 그대로 돌려준다 (try/except로 감싸고 오류만 출력)
    #  - 테스트: tests/test_api_db.py 에 저장 테스트 추가
    return bot.ask(req.question)
