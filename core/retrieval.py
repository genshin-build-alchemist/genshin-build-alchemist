"""경로별 근거 검색 (RAG의 R). 지금은 규칙·키워드 기반이다.

반환 형식: 근거 목록 [{'kind', 'title', 'text', 'data'}]
  - kind : character / patch / build_card / weapon / artifact / recheck
  - text : 모델에게 보여 줄 한 줄 (대괄호 없는 문장형이 작은 모델에게 읽기 쉬웠다: 1차 실험)
  - data : 원본 값 (모의 답변기와 API 응답에서 사용)

검색 방식을 임베딩(Chroma 또는 PostgreSQL pgvector)으로 바꿔도 이 반환 형식만 지키면 된다.
"""
# TODO(B) 벡터 검색 붙이기. 위에서부터 순서대로, 끝나면 [ ] -> [x] 로 바꿔서 PR
#  1. [ ] 임베딩 파일 만들기: 코랩에서 embed_and_save 셀 실행 -> 드라이브 data/embeddings/
#         완료 기준: 벡터 길이 1.000, 이름 질문 Hit@1 90% 이상
#  2. [ ] vector_search(question, k, pool) 만들기: 질문 -> 비슷한 문서 doc_id 상위 k개
#         질문도 문서와 같은 모델 + normalize_embeddings=True + 앞말 없이 임베딩한다
#  3. [ ] filter 경로 = 조건 필터 + 벡터: rr.conditions 로 먼저 거르고, 벡터는 걸러진 것 안에서 순위만
#         (벡터만으로는 '활 + 수메르' 같은 여러 조건을 못 맞춘다. 버그 아님)
#         키워드 검색은 이미 '조건 모두 만족'으로 바뀜 (FILTER_MODE = "all"). 벡터 검색도 같은 규칙을 지킨다
#  4. [ ] 검색 정확도(Hit@k) 재기: core/retrieval_eval.py 맨 위 '사용' 참고 (정답 근거 = data/eval/evidence_info_v1.json)
#         기준점(지금 키워드 검색): 템플릿 질문은 만점, 말투 변형 질문 hit@1 0.681 (띄어쓰기 없음 0.0)
#         DEV 세트와 style_questions_dev.csv로만 비교하고, 평가 문항은 마지막에 한 번만 본다
#  5. [ ] 캐릭터 말고 전체 문서(특성·운명의 자리·무기·성유물·패치)로 늘리기 (KINDS = None)
#  6. [ ] 청킹 비교: 문서 통째('doc') vs 길이로 자르기('len200' 등). 결과는 드라이브 results/ JSON
#  7. [ ] 아래 retrieve()가 벡터 검색을 쓰게 연결. 반환 형식(kind/title/text/data)은 그대로
#  규칙: 학습용(DEV) 질문은 평가용 캐릭터 문서를 검색하지 않는다 (pool 인자로 범위 제한)
#  막히면: A에게 질문. 예시 셀은 A가 디스코드로 공유
from core.kb import slot_label
from core.validate import recheck_reasons

KIND_KO = {"characters": "캐릭터", "talents": "스킬", "constellations": "명의 자리", "weapons": "무기"}
FILTER_TOP_K = 30
# filter 경로에서 근거로 넘길 캐릭터
#   all : 조건을 모두 만족하는 캐릭터만 (챗봇 기본). DB의 WHERE a AND b 와 같다
#   any : 조건을 하나라도 만족하면 (예전 방식, rag~rag_v4 실험 결과를 재현할 때만)
#         모델이 30명 중에서 조건을 직접 거르게 했더니 안 맞는 이름까지 따라 써서 정밀도가 0.21에 그쳤다 (info14_rag_v4)
FILTER_MODES = ("all", "any")
FILTER_MODE = "all"
PATCH_MAX_LINES = 60


def character_line(c):
    def v(f):
        return c[f] or "정보 없음"
    return f"{c['name']}: 원소 {v('element')} / 무기 {v('weapon')} / {v('rarity')} / 지역 {v('region')}"


def patch_line(r):
    name, kind = r["entity_name"], KIND_KO.get(r["folder"], r["folder"])
    if r["change_type"] == "added":
        if r["folder"] in ("characters", "weapons"):
            return f"{name}: 신규 {kind} 추가"
        return f"{name}: {kind} 정보 새로 추가"
    if r["change_type"] == "removed":
        return f"{name}: {kind} 정보 삭제"
    parts = sorted({slot_label(c["field"]) for c in r["changes"]} - {None})
    return f"{name}: {kind} 수정, 바뀐 부분 = {', '.join(parts) if parts else '기타'}"


def _ev(kind, title, text, data):
    return {"kind": kind, "title": title, "text": text, "data": data}


def retrieve(rr, kb, pool=None, filter_mode=None):
    """rr: router.RouteResult. pool: 검색 대상 캐릭터 목록 (평가 때 학습/평가 분리용, 기본은 전체).
    filter_mode: 'all'(기본) / 'any'. 위 FILTER_MODE 설명 참고."""
    pool = kb.characters if pool is None else pool
    if rr.route == "lookup":
        return [_ev("character", c["name"], character_line(c), c) for c in pool if c["name"] == rr.character]

    if rr.route == "filter":
        mode = filter_mode or FILTER_MODE
        if mode not in FILTER_MODES:
            raise ValueError(f"filter_mode는 {FILTER_MODES} 중 하나: {mode!r}")
        need = len(rr.conditions) if mode == "all" else 1      # 맞아야 하는 조건 수
        scored = []
        for c in pool:
            score = sum(1 for f, v in rr.conditions.items() if c[f] == v)
            if score >= need:
                scored.append((-score, c["name"], c))
        return [_ev("character", c["name"], character_line(c), c) for _, _, c in sorted(scored)[:FILTER_TOP_K]]

    if rr.route == "patch":
        version = rr.version or kb.latest_version
        if version not in kb.versions:
            return []
        records = [r for r in kb.patches if r["version"] == version
                   and (rr.character is None or r["entity_name"] == rr.character)]
        return [_ev("patch", r["entity_name"], f"{version} {patch_line(r)}", r) for r in records[:PATCH_MAX_LINES]]

    if rr.route == "build":
        card = kb.card_by_character.get(rr.character)
        if not card:
            return []
        evidence = [_ev("build_card", card["character"], build_card_line(card), card)]
        for w in card.get("weapons", []):
            info = kb.weapon_by_name.get(w)
            if info:
                evidence.append(_ev("weapon", w, f"{w}: {info['rarity']} {info['weapon']}, 주옵션 {info['main_stat']}", info))
        for a in card.get("artifact_sets", []):
            info = kb.artifact_by_name.get(a)
            if info:
                evidence.append(_ev("artifact", a, f"{a}: 2세트 {info['effect_2pc'] or '-'}", info))
        for r in recheck_reasons(card, kb):
            evidence.append(_ev("recheck", r["target"],
                                f"재확인 필요: {r['version']}에서 {r['target']} 변경 ({', '.join(r['parts'])})", r))
        return evidence

    return []   # unknown


def build_card_line(card):
    ms = card.get("main_stats") or {}
    main = " / ".join(f"{k} {v}" for k, v in (("시간의 모래", ms.get("sands")), ("공간의 성배", ms.get("goblet")),
                                               ("이성의 왕관", ms.get("circlet"))) if v)
    return (f"{card['character']} 빌드: 추천 무기 {', '.join(card.get('weapons', [])) or '-'} / "
            f"추천 성유물 {', '.join(card.get('artifact_sets', [])) or '-'}"
            + (f" / 주옵션 {main}" if main else "")
            + f" (출처 {card.get('source_name') or card.get('source_url') or '-'}, {card.get('checked_version')} 확인)")
