"""질문 하나를 처리하는 전체 흐름: 경로 판별 -> 근거 검색 -> 답 -> API 응답 형식.

응답 형식 (FastAPI가 그대로 돌려준다, PRD 8장 '결과 양식'의 API 응답 제안)
{
  "question": "...",
  "route": "lookup | filter | patch | build | unknown",
  "answer": ["..."],            # 채점과 같은 목록 형식
  "message": "...",             # 사용자에게 보여 줄 문장
  "evidence": [{"kind", "title", "text", "doc_id"}],   (doc_id: 빌드 카드·재확인 표시는 null)
  "found": true/false,          # 데이터에서 근거를 찾았는지
  "needs_recheck": true/false,  # 빌드 가이드가 패치 이후 재확인이 필요한지
  "model": "...", "method": "rag", "data_version": "..."
}
"""
from core.answer import MockAnswerer
from core.retrieval import retrieve
from core.router import Router

FIELD_KO = {"element": "원소", "weapon": "무기", "rarity": "성급", "region": "지역"}
PATCH_FOLDER_KO = {"characters": "캐릭터", "weapons": "무기", "talents": "스킬·특성", "constellations": "명의 자리"}


class Chatbot:
    def __init__(self, kb, answerer=None):
        self.kb = kb
        self.router = Router(kb)
        self.answerer = answerer or MockAnswerer()

    def ask(self, question, pool=None):
        self._last_question = question
        rr = self.router.route(question)
        evidence = retrieve(rr, self.kb, pool)
        found = bool(evidence)
        # 근거가 없으면 모델을 부르지 않는다: 지어낸 답을 원천 차단
        answer = self.answerer.answer(question, rr, evidence) if found else []
        needs_recheck = any(e["kind"] == "recheck" for e in evidence)
        return {
            "question": question,
            "route": rr.route,
            "answer": answer,
            "message": self._message(rr, answer, evidence, found),
            "evidence": [{k: e.get(k) for k in ("kind", "title", "text", "doc_id")} for e in evidence],
            "found": found,
            "needs_recheck": needs_recheck,
            "model": getattr(self.answerer, "name", "unknown"),
            "method": getattr(self.answerer, "method", "rag"),
            "data_version": self.kb.data_version,
        }

    def _message(self, rr, answer, evidence, found):
        if not found:
            if rr.route == "build":
                return f"{rr.character}의 빌드 가이드가 아직 없어요."
            if rr.route == "patch":
                versions = ", ".join(self.kb.versions)
                if rr.character and not rr.version:
                    return f"{rr.character}의 변경 기록을 데이터에서 찾지 못했어요. (수집된 버전: {versions})"
                version = rr.version or self.kb.latest_version
                who = f" {rr.character}의" if rr.character else ""
                return f"{version} 버전{who} 변경 기록을 데이터에서 찾지 못했어요. (수집된 버전: {versions})"
            return "데이터에서 답을 찾지 못했어요. 캐릭터 이름이나 조건을 확인해 주세요."
        if not answer:
            return "근거는 찾았지만 질문에 맞는 답이 없어요."
        joined = ", ".join(answer)
        if rr.route == "lookup":
            label = FIELD_KO.get(rr.asked_field)
            return f"{rr.character}의 {label}: {joined}" if label else f"{rr.character}: {joined}"
        if rr.route == "filter":
            return f"조건에 맞는 캐릭터 {len(answer)}명: {joined}"
        if rr.route == "patch":
            if rr.character:
                if rr.version:
                    return f"{rr.version} 버전 {rr.character}의 바뀐 부분: {joined}"
                return f"{rr.character}의 바뀐 부분 (수집된 버전 {', '.join(self.kb.versions)}): {joined}"
            version = rr.version or self.kb.latest_version
            label = PATCH_FOLDER_KO.get(rr.patch_folder)
            if rr.patch_added:
                return f"{version} 버전 신규 {label or '캐릭터·무기'}: {joined}"
            if label:
                return f"{version} 버전에서 바뀐 {label}: {joined}"
            return f"{version} 버전에서 스킬·명의 자리가 바뀐 캐릭터: {joined}"
        if rr.route == "build":
            msg = f"{rr.character} 추천: {joined}"
            rechecks = [e["text"] for e in evidence if e["kind"] == "recheck"]
            if rechecks:
                msg += " / " + "; ".join(rechecks)
            return msg
        return joined
