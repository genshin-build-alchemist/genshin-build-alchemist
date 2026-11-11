"""챗봇의 핵심 로직. 노트북 평가와 FastAPI가 같은 코드를 쓴다.

    kb.py         데이터 불러오기 (캐릭터, 무기·성유물, 패치 변경, 빌드 카드)
    router.py     질문 종류 판별 (조건부 워크플로, 경로 6개)
    retrieval.py  경로별 근거 검색 (RAG의 R)
    answer.py     답 만들기 (모의 답변기 / LLM 답변기)
    validate.py   빌드 카드 검사 + 패치 후 재확인 판정
    pipeline.py   위를 이어 붙인 ask() -> API 응답 형식
"""
