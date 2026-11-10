"""DB 스키마·시드 테스트. 실행: python3 -m unittest tests.test_db_schema -v

기본 테스트는 DB 없이 돈다 (SQL 파일 내용 검사).
실제 PostgreSQL + pgvector로 확인하려면 빈 DB 주소를 넣고 실행한다 (표를 지우고 다시 만드니 꼭 빈 테스트 DB로):
  TEST_DATABASE_URL=postgresql://postgres@localhost:5432/test python3 -m unittest tests.test_db_schema -v
"""
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from db.make_documents_seed import SRC, insert_sql, make_documents_seed, sql_text

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = ROOT / "db" / "schema.sql"
DOCS = ROOT / "data" / "docs" / "documents_ko.jsonl"
TEST_DB = os.environ.get("TEST_DATABASE_URL")


class SchemaFileTest(unittest.TestCase):
    def test_schema_has_vector_tables(self):
        sql = SCHEMA.read_text(encoding="utf-8")
        for needle in ("CREATE EXTENSION IF NOT EXISTS vector", "CREATE TABLE IF NOT EXISTS documents",
                       "CREATE TABLE IF NOT EXISTS chunks", "embedding       vector(768)",
                       "USING hnsw (embedding vector_cosine_ops)", "CREATE TABLE IF NOT EXISTS chat_logs"):
            self.assertIn(needle, sql)

    def test_document_kinds_match_documents_file(self):
        # 문서 파일에 있는 종류가 표의 CHECK 목록에 모두 들어 있어야 넣을 때 실패하지 않는다
        sql = SCHEMA.read_text(encoding="utf-8")
        kinds = {json.loads(line)["kind"] for line in DOCS.read_text(encoding="utf-8").splitlines()}
        for kind in kinds:
            self.assertIn(f"'{kind}'", sql)


class DocumentsSeedTest(unittest.TestCase):
    def test_quoting(self):
        self.assertEqual(sql_text("「잇신의 기술」 명검's"), "'「잇신의 기술」 명검''s'")

    def test_insert_sql(self):
        doc = {"doc_id": "character:x", "kind": "character", "title": "엑스", "text": "엑스의 'it'",
               "metadata": {"name": "엑스", "element": None}}
        sql = insert_sql(doc)
        self.assertIn("'엑스의 ''it'''", sql)
        self.assertIn('\'{"element": null, "name": "엑스"}\'::jsonb', sql)
        self.assertIn("ON CONFLICT (doc_id) DO UPDATE", sql)

    def test_seed_file(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "seed.sql"
            n = make_documents_seed(out=out)
            text = out.read_text(encoding="utf-8")
        n_docs = len(SRC.read_text(encoding="utf-8").splitlines())    # documents_ko.jsonl 한 줄 = 문서 1개
        self.assertEqual(n, n_docs)
        self.assertEqual(text.count("INSERT INTO documents"), n_docs)
        self.assertTrue(text.startswith("-- 자동 생성 파일") and text.rstrip().endswith("COMMIT;"))


@unittest.skipUnless(TEST_DB and shutil.which("psql"), "TEST_DATABASE_URL이 없거나 psql이 없음")
class PostgresIntegrationTest(unittest.TestCase):
    """실제 DB에 스키마·시드를 넣고 벡터 검색과 변경 감지를 확인한다."""

    def psql(self, sql=None, file=None):
        cmd = ["psql", TEST_DB, "-q", "-X", "-A", "-t", "-v", "ON_ERROR_STOP=1"]
        cmd += ["-f", str(file)] if file else ["-c", sql]
        return subprocess.run(cmd, check=True, capture_output=True, text=True).stdout.strip()

    def test_schema_seed_and_search(self):
        self.psql("DROP TABLE IF EXISTS chunks, documents, chat_logs, characters")
        self.psql(file=SCHEMA)
        self.psql(file=SCHEMA)                                   # 두 번 실행해도 안전
        with tempfile.TemporaryDirectory() as d:
            seed = Path(d) / "seed.sql"
            make_documents_seed(out=seed)
            self.psql(file=seed)
            self.assertEqual(self.psql("SELECT count(*) FROM documents"), "1430")
            # 자동 계산 칸
            self.assertEqual(self.psql("SELECT element || '/' || region FROM documents "
                                       "WHERE doc_id = 'character:kaedeharakazuha'"), "바람/이나즈마")
            # 가짜 임베딩으로 벡터 검색: 자기 자신이 1등
            self.psql("INSERT INTO chunks (chunk_id, doc_id, text, embedding_model, embedding) "
                      "SELECT 'doc|test|' || d.doc_id, d.doc_id, d.text, 'test', "
                      "(SELECT array_agg(random())::vector(768) FROM generate_series(1, 768) g "
                      "WHERE d.doc_id IS NOT NULL) FROM documents d")
            top = self.psql("SELECT doc_id FROM chunks ORDER BY embedding <=> "
                            "(SELECT embedding FROM chunks WHERE doc_id = 'character:albedo') LIMIT 1")
            self.assertEqual(top, "character:albedo")
            # 같은 시드를 다시 넣으면 바뀐 문서 0개, 본문을 바꾸면 그 문서만 잡힘
            self.psql(file=seed)
            changed = "SELECT count(*) FROM documents d JOIN chunks c USING (doc_id) WHERE d.updated_at > c.created_at"
            self.assertEqual(self.psql(changed), "0")
            self.psql("INSERT INTO documents (doc_id, kind, title, text) VALUES "
                      "('character:albedo', 'character', '알베도', '바뀐 본문') "
                      "ON CONFLICT (doc_id) DO UPDATE SET text = EXCLUDED.text, updated_at = CASE WHEN "
                      "documents.text = EXCLUDED.text THEN documents.updated_at ELSE now() END")
            self.assertEqual(self.psql(changed), "1")
        self.psql("DROP TABLE IF EXISTS chunks, documents, chat_logs, characters")


if __name__ == "__main__":
    unittest.main()
