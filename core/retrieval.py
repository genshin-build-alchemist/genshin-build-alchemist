"""경로별 근거 검색 (RAG의 R). 지금은 규칙·키워드 기반이다.

반환 형식: 근거 목록 [{'kind', 'title', 'text', 'data'}]
  - kind : character / patch / build_card / weapon / artifact / recheck
  - text : 모델에게 보여 줄 한 줄 (대괄호 없는 문장형이 작은 모델에게 읽기 쉬웠다: 1차 실험)
  - data : 원본 값 (모의 답변기와 API 응답에서 사용)

검색 방식을 임베딩(Chroma 또는 PostgreSQL pgvector)으로 바꿔도 이 반환 형식만 지키면 된다.
"""
# 벡터 검색: 아이템(무기·성유물) 질문에만 쓴다 -> core/vector.py (재료는 load_item_index로 넣는다)
#  캐릭터 조회·조건 검색·패치는 키워드 검색 그대로 (기본 단계 결정, 하이브리드는 다음 프로젝트)
import json
import re
from functools import lru_cache
from pathlib import Path

from core.kb import slot_label
from core.validate import recheck_reasons

KIND_KO = {"characters": "캐릭터", "talents": "스킬", "constellations": "명의 자리", "weapons": "무기"}
FILTER_TOP_K = 30         # any 모드에서만 쓰는 상한 (조건 하나만 맞는 캐릭터까지 들어와서 상위 30명으로 자른다)
# filter 경로에서 근거로 넘길 캐릭터 (rag_v5)
#   all : 조건을 모두 만족하는 캐릭터만 (챗봇 기본). DB의 WHERE a AND b 와 같다. 근거 = 정답 목록이라 상한이 없다
#   any : 조건을 하나라도 만족하면 (rag ~ rag_v4 방식. 평가 노트북에서 예전 결과를 재현할 때만)
#         모델이 30명 안에서 조건을 직접 거르게 했더니 안 맞는 이름까지 따라 써서
#         조건 검색 정밀도가 낮았다 (info14_rag_v4-V2: 조건 검색 F1 0.262, 남은 환각 5건 중 4건)
FILTER_MODES = ("all", "any")
FILTER_MODE = "all"
PATCH_MAX_LINES = 60
PATCH_DETAIL_MAX = 5      # 기록이 이 개수 이하이면 근거에 바뀌기 전 → 후 본문을 넣는다


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


def patch_versions(rr, kb):
    """찾을 버전 목록. 버전을 말하면 그 버전, 캐릭터만 말하면 수집된 모든 버전(최신 먼저), 둘 다 없으면 최신 버전."""
    if rr.version:
        return [rr.version] if rr.version in kb.versions else []
    if rr.character:
        return list(reversed(kb.versions))
    return [kb.latest_version] if kb.latest_version else []


def patch_records(rr, kb):
    """patch 질문 -> 변경 기록 목록. 버전·캐릭터·종류(무기/캐릭터/스킬/별자리)·신규 여부로 거른다."""
    out = []
    for version in patch_versions(rr, kb):
        for r in kb.patches:
            if r["version"] != version:
                continue
            if rr.character is not None and r["entity_name"] != rr.character:
                continue
            if rr.patch_folder and r["folder"] != rr.patch_folder:
                continue
            if rr.patch_added and r["change_type"] != "added":
                continue
            out.append(r)
    return out


# 근거 본문에서 뺄 줄: 수치 표의 자리표시자({param7:F1P} 등, 사람이 읽을 수 없음),
# 무기 재련 2~5단계(1단계와 숫자만 다름), 재련 수치 목록(values #)
PATCH_SKIP_LINE = re.compile(r"\{param|^- r[2-5] |^- r\d values")


def patch_text(r):
    """변경 기록 1건의 본문 (바뀌기 전 → 후). patch 문서(documents_ko.jsonl)에서 읽을 수 없는 줄만 뺀 글."""
    from collector.patchnotes.documents import make_document_text
    lines = [line for line in make_document_text(r).split("\n") if not PATCH_SKIP_LINE.search(line)]
    return "\n".join(line.replace("- r1 ", "- 재련 1단계 ", 1) for line in lines)


def doc_id_for(kind, data):
    """근거 -> 검색용 문서 id (data/docs/documents_ko.jsonl, DB documents 표와 같은 규칙).
    문서가 아닌 근거(빌드 카드, 재확인 표시)는 None."""
    if kind in ("character", "weapon", "artifact"):
        return f"{kind}:{data['key']}"
    if kind == "patch":
        return f"patch:{data['version']}:{data['folder']}:{data['entity_id']}"
    return None


ITEM_TOP_K = 5
DOCS_PATH = Path(__file__).resolve().parent.parent / "data" / "docs" / "documents_ko.jsonl"


@lru_cache(maxsize=1)
def _item_docs():
    """무기·성유물 문서 doc_id -> 본문 (documents_ko.jsonl, 벡터 검색과 같은 글). 파일이 없으면 빈 dict."""
    try:
        with open(DOCS_PATH, encoding="utf-8") as f:
            docs = (json.loads(line) for line in f if line.strip())
            return {d["doc_id"]: d["text"] for d in docs if d["kind"] in ("weapon", "artifact")}
    except OSError:
        return {}


def item_evidence(kind, info):
    """무기·성유물 1개 -> 근거. 본문은 문서 파일에서, 없으면 데이터로 한 줄."""
    doc_id = doc_id_for(kind, info)
    text = _item_docs().get(doc_id)
    if not text:
        text = (f"{info['name']}: {info['rarity']} {info['weapon']}, 주옵션 {info['main_stat']}" if kind == "weapon"
                else f"{info['name']}: 2세트 {info.get('effect_2pc') or '-'} / 4세트 {info.get('effect_4pc') or '-'}")
    return _ev(kind, info["name"], text, info)


def _ev(kind, title, text, data):
    return {"kind": kind, "title": title, "text": text, "data": data, "doc_id": doc_id_for(kind, data)}


def filter_characters(conditions, pool, mode=FILTER_MODE):
    """조건 -> 캐릭터 목록. all: 조건을 모두 만족 (이름 순), any: 맞는 조건 수가 많은 순으로 상위 FILTER_TOP_K명."""
    if mode not in FILTER_MODES:
        raise ValueError(f"filter_mode는 {FILTER_MODES} 중 하나: {mode!r}")
    if not conditions:
        return []
    need = len(conditions) if mode == "all" else 1      # 맞아야 하는 조건 수
    scored = []
    for c in pool:
        score = sum(1 for f, v in conditions.items() if c[f] == v)
        if score >= need:
            scored.append((-score, c["name"], c))
    picked = [c for _, _, c in sorted(scored)]
    return picked if mode == "all" else picked[:FILTER_TOP_K]


def retrieve(rr, kb, pool=None, filter_mode=None):
    """rr: router.RouteResult. pool: 검색 대상 캐릭터 목록 (평가 때 학습/평가 분리용, 기본은 전체).
    filter_mode: 'all'(기본, rag_v5) / 'any'(rag ~ rag_v4 재현용). 위 FILTER_MODE 설명 참고."""
    pool = kb.characters if pool is None else pool
    if rr.route == "lookup":
        return [_ev("character", c["name"], character_line(c), c) for c in pool if c["name"] == rr.character]

    if rr.route == "filter":
        chars = filter_characters(rr.conditions, pool, filter_mode or FILTER_MODE)
        return [_ev("character", c["name"], character_line(c), c) for c in chars]

    if rr.route == "patch":
        records = patch_records(rr, kb)
        # 기록이 적으면(한 캐릭터·한 무기) 바뀌기 전 → 후 본문을 근거로, 많으면 한 줄 요약으로
        # 신규·삭제 기록은 본문이 '신규 추가됨' 한 줄뿐이라 늘 한 줄 요약으로 쓴다
        detail = len(records) <= PATCH_DETAIL_MAX
        return [_ev("patch", r["entity_name"],
                    patch_text(r) if detail and r["change_type"] == "modified" else f"{r['version']} {patch_line(r)}", r)
                for r in records[:PATCH_MAX_LINES]]

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

    if rr.route == "item":
        if rr.item:     # 이름이 있으면 그 문서 1개 (키워드 검색)
            info = (kb.weapon_by_name if rr.item_kind == "weapon" else kb.artifact_by_name).get(rr.item)
            return [item_evidence(rr.item_kind, info)] if info else []
        try:                                            # 이름이 없으면 벡터 검색 (core/vector.py)
            from core.vector import item_vector_search
            doc_ids = item_vector_search(rr.question, k=ITEM_TOP_K)
        except Exception:   # 벡터 검색이 실패해도 API는 멈추지 않는다 -> 근거 없음
            doc_ids = []
        by_doc = {doc_id_for("weapon", w): ("weapon", w) for w in kb.weapons}
        by_doc.update({doc_id_for("artifact", a): ("artifact", a) for a in kb.artifacts})
        return [item_evidence(*by_doc[d]) for d in doc_ids if d in by_doc][:ITEM_TOP_K]

    return []   # unknown


def build_card_line(card):
    ms = card.get("main_stats") or {}
    main = " / ".join(f"{k} {v}" for k, v in (("시간의 모래", ms.get("sands")), ("공간의 성배", ms.get("goblet")),
                                               ("이성의 왕관", ms.get("circlet"))) if v)
    return (f"{card['character']} 빌드: 추천 무기 {', '.join(card.get('weapons', [])) or '-'} / "
            f"추천 성유물 {', '.join(card.get('artifact_sets', [])) or '-'}"
            + (f" / 주옵션 {main}" if main else "")
            + f" (출처 {card.get('source_name') or card.get('source_url') or '-'}, {card.get('checked_version')} 확인)")
