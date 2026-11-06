"""검색 근거의 doc_id 테스트. 실행: python3 -m unittest tests.test_evidence_doc_id -v

doc_id = 검색용 문서 id (data/docs/documents_ko.jsonl, DB documents 표). 대화 기록 chat_logs.retrieved_doc_ids에 저장된다.
"""
import json
import os
import unittest
from pathlib import Path
from unittest import mock

from api import chat_log
from core.kb import load_kb
from core.pipeline import Chatbot
from core.retrieval import doc_id_for, retrieve
from core.router import Router

ROOT = Path(__file__).resolve().parent.parent
DOC_IDS = {json.loads(line)["doc_id"] for line in (ROOT / "data" / "docs" / "documents_ko.jsonl").read_text(encoding="utf-8").splitlines()}
KB = load_kb()


class DocIdRuleTest(unittest.TestCase):
    """모든 캐릭터·무기·성유물·패치 기록의 doc_id가 실제 문서에 있어야 한다."""

    def test_every_source_maps_to_a_document(self):
        groups = {"character": KB.characters, "weapon": KB.weapons, "artifact": KB.artifacts, "patch": KB.patches}
        for kind, rows in groups.items():
            missing = [doc_id_for(kind, r) for r in rows if doc_id_for(kind, r) not in DOC_IDS]
            self.assertEqual(missing, [], f"{kind}: 문서에 없는 doc_id {missing[:3]}")
            self.assertTrue(rows, kind)

    def test_examples(self):
        albedo = KB.char_by_name["알베도"]
        self.assertEqual(doc_id_for("character", albedo), "character:albedo")
        self.assertIsNone(doc_id_for("build_card", {"character": "알베도"}))
        self.assertIsNone(doc_id_for("recheck", {"target": "x"}))


class RetrieveDocIdTest(unittest.TestCase):
    def setUp(self):
        self.router = Router(KB)

    def test_evaluation_questions(self):
        data = json.loads((ROOT / "data" / "eval" / "questions_info_v1.json").read_text(encoding="utf-8"))
        for q in data["questions"]:
            for e in retrieve(self.router.route(q["question"]), KB):
                self.assertIn(e["doc_id"], DOC_IDS, q["id"])

    def test_patch_question(self):
        evidence = retrieve(self.router.route("7.0에서 사유 뭐 바뀌었어?"), KB)
        self.assertTrue(evidence)
        self.assertTrue(all(e["doc_id"].startswith("patch:7.0:") and e["doc_id"] in DOC_IDS for e in evidence))


class ResponseDocIdTest(unittest.TestCase):
    def test_pipeline_response(self):
        r = Chatbot(KB).ask("몬드 출신 5성 캐릭터 누구 있어?")
        self.assertTrue(r["evidence"])
        self.assertTrue(all(e["doc_id"] in DOC_IDS for e in r["evidence"]))
        self.assertEqual(set(r["evidence"][0]), {"kind", "title", "text", "doc_id"})

    def test_chat_log_saves_doc_ids(self):
        r = Chatbot(KB).ask("알베도 원소가 뭐야?")
        self.assertEqual(chat_log.doc_ids_of(r), ["character:albedo"])
        self.assertIsNone(chat_log.doc_ids_of({"evidence": [{"doc_id": None}]}))
        self.assertIsNone(chat_log.doc_ids_of({"evidence": []}))
        fake_conn = mock.MagicMock()
        with mock.patch.dict(os.environ, {"DATABASE_URL": "postgresql://test"}), \
             mock.patch("psycopg.connect", return_value=fake_conn):
            self.assertTrue(chat_log.save_chat_log(r, 0.5))
        params = fake_conn.__enter__.return_value.execute.call_args.args[1]
        self.assertEqual(params[-1], ["character:albedo"])     # retrieved_doc_ids
        self.assertEqual(params[-2], 0.5)                      # seconds


try:
    from fastapi.testclient import TestClient
    from api.main import app
except ImportError:      # fastapi 없는 환경
    TestClient = None


@unittest.skipIf(TestClient is None, "fastapi, httpx가 설치되지 않음")
class ApiDocIdTest(unittest.TestCase):
    def test_ask_returns_doc_id(self):
        with mock.patch("api.chat_log.save_chat_log"):
            body = TestClient(app).post("/ask", json={"question": "알베도 원소가 뭐야?"}).json()
        self.assertEqual(body["evidence"][0]["doc_id"], "character:albedo")


if __name__ == "__main__":
    unittest.main()
