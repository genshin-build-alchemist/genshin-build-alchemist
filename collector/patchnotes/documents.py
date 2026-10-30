"""변경 기록 -> RAG에 넣을 문서(텍스트 + 메타데이터)로 변환."""
from .textutil import humanize_field, shorten

FOLDER_LABELS = {"characters": "캐릭터", "talents": "스킬/특성",
                 "constellations": "명의 자리", "weapons": "무기"}


def make_document_text(record):
    folder = FOLDER_LABELS.get(record["folder"], record["folder"])
    lines = [f"[원신 {record['version']} 데이터 변경] {record['entity_name']} - {folder}"]
    if record["change_type"] == "added":
        lines.append("신규 추가됨")
    elif record["change_type"] == "removed":
        lines.append("삭제됨")
    else:
        for ch in record["changes"]:
            before = "(없음)" if ch["before"] is None else shorten(ch["before"])
            after = "(없음)" if ch["after"] is None else shorten(ch["after"])
            lines.append(f"- {humanize_field(ch['field'])}: {before} → {after}")
    return "\n".join(lines)


def to_rag_documents(records):
    docs = []
    for rec in records:
        docs.append({
            "id": f"{rec['version']}:{rec['folder']}:{rec['entity_id']}",
            "text": make_document_text(rec),
            "metadata": {k: rec[k] for k in
                         ("version", "from_version", "folder", "entity_id",
                          "entity_name", "change_type", "data_date")},
        })
    return docs
