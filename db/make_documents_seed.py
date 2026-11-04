"""data/docs/documents_ko.jsonl -> db/seed_documents.sql (documents 표에 넣을 INSERT 문).

실행: python3 db/make_documents_seed.py && psql "$DATABASE_URL" -f db/seed_documents.sql
DB 드라이버 없이 SQL 파일만 만든다. 다시 실행해도 같은 문서는 덮어쓴다(ON CONFLICT).
본문이 바뀐 문서만 updated_at이 갱신되므로, chunks 표의 임베딩을 다시 만들어야 하는 문서를 찾을 수 있다:
  SELECT d.doc_id FROM documents d JOIN chunks c USING (doc_id) WHERE d.updated_at > c.created_at;
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "docs" / "documents_ko.jsonl"
OUT = ROOT / "db" / "seed_documents.sql"


def sql_text(value):
    """문자열 -> SQL 문자열 리터럴 (작은따옴표를 두 번 써서 이스케이프)."""
    return "'" + str(value).replace("'", "''") + "'"


def insert_sql(doc):
    meta = json.dumps(doc["metadata"], ensure_ascii=False, sort_keys=True)
    return (
        "INSERT INTO documents (doc_id, kind, title, text, metadata) VALUES ("
        f"{sql_text(doc['doc_id'])}, {sql_text(doc['kind'])}, {sql_text(doc['title'])}, "
        f"{sql_text(doc['text'])}, {sql_text(meta)}::jsonb) "
        "ON CONFLICT (doc_id) DO UPDATE SET kind = EXCLUDED.kind, title = EXCLUDED.title, "
        "text = EXCLUDED.text, metadata = EXCLUDED.metadata, "
        # 본문(종류·글)이 그대로면 updated_at을 바꾸지 않는다 -> 임베딩 다시 만들 문서를 골라낼 수 있음
        "updated_at = CASE WHEN documents.kind = EXCLUDED.kind AND documents.text = EXCLUDED.text "
        "THEN documents.updated_at ELSE now() END;"
    )


def make_documents_seed(src=SRC, out=OUT):
    docs = [json.loads(line) for line in Path(src).read_text(encoding="utf-8").splitlines() if line.strip()]
    lines = ["-- 자동 생성 파일: python3 db/make_documents_seed.py", "BEGIN;"]
    lines += [insert_sql(doc) for doc in docs]
    lines.append("COMMIT;")
    Path(out).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(docs)


if __name__ == "__main__":
    n = make_documents_seed()
    print(f"{OUT.relative_to(ROOT)} 생성: 문서 {n}개")
