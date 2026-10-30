"""챗봇 API (FR-07). 질문을 받아 답·경로·근거·데이터 존재 여부를 돌려준다.

실행 (프로젝트 루트에서):
    pip install -r requirements.txt && uvicorn api.main:app --reload
확인:
    http://127.0.0.1:8000/docs  (브라우저에서 바로 질문을 보내 볼 수 있는 화면)

기본은 모의 답변기(규칙 기반)라 GPU 없이 로컬 PC에서 돈다.
실제 LLM은 코랩에서 core.answer.LLMAnswerer(generate_fn) 를 넣어 Chatbot을 만들면 된다.
"""
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
    # TODO(FR-09): DB가 준비되면 여기서 chat_logs 테이블에 질문과 응답을 저장한다.
    return bot.ask(req.question)
