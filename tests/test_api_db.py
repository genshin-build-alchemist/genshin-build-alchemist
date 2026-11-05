"""API와 DB 시드 테스트. fastapi가 설치되지 않았으면 API 테스트는 건너뛴다."""
import tempfile
import unittest
from pathlib import Path

try:
    from fastapi.testclient import TestClient
    from api.main import app
except ImportError:      # fastapi / httpx 미설치
    TestClient = None

from db.make_seed import make_seed, sql_value


@unittest.skipIf(TestClient is None, "fastapi, httpx가 설치되지 않음 (pip install -r requirements.txt)")
class ApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_health(self):
        r = self.client.get("/health")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["characters"], 124)
        self.assertEqual(r.json()["model"], "mock-rule")          # 기본은 모의 답변기 (GBA_ANSWERER 없음)

    def test_ask(self):
        r = self.client.post("/ask", json={"question": "몬드 출신 5성 캐릭터 누구 있어?"})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["route"], "filter")
        self.assertIn("알베도", body["answer"])
        self.assertTrue(body["found"])

    def test_unknown_question(self):
        body = self.client.post("/ask", json={"question": "원신에서 제일 센 캐릭터는?"}).json()
        self.assertEqual((body["route"], body["found"], body["answer"]), ("unknown", False, []))

    def test_empty_question_rejected(self):
        self.assertEqual(self.client.post("/ask", json={"question": ""}).status_code, 422)


class SeedTest(unittest.TestCase):
    def test_seed_file(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "seed.sql"
            n = make_seed(out=out)
            text = out.read_text(encoding="utf-8")
        self.assertEqual(n, 124)
        self.assertEqual(text.count("INSERT INTO characters"), 124)
        self.assertIn("ON CONFLICT (key)", text)

    def test_sql_quoting(self):
        self.assertEqual(sql_value(None), "NULL")
        self.assertEqual(sql_value("it's"), "'it''s'")


if __name__ == "__main__":
    unittest.main()
