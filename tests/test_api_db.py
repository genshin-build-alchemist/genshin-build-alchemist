"""API와 DB 시드 테스트. fastapi가 설치되지 않았으면 API 테스트는 건너뛴다."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

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
        # .env 에 DATABASE_URL 이 있어도 테스트가 실제 DB에 기록을 쌓지 않게 저장을 막는다
        cls.no_db = mock.patch("api.chat_log.save_chat_log")
        cls.no_db.start()

    @classmethod
    def tearDownClass(cls):
        cls.no_db.stop()

    def test_health(self):
        r = self.client.get("/health")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["characters"], 126)
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


@unittest.skipIf(TestClient is None, "fastapi, httpx가 설치되지 않음 (pip install -r requirements.txt)")
class ChatLogTest(unittest.TestCase):
    """대화 기록 저장 (FR-09). 실제 DB 없이 저장 함수를 가짜로 바꿔 확인한다.
    TestClient 는 백그라운드 작업이 끝난 뒤에 응답을 돌려주므로 바로 확인할 수 있다."""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_ask_saves_log_in_background(self):
        with mock.patch("api.chat_log.save_chat_log") as save:
            body = self.client.post("/ask", json={"question": "알베도 원소가 뭐야?"}).json()
        save.assert_called_once()
        saved, seconds = save.call_args.args
        self.assertEqual(saved, body)                       # 응답과 같은 내용을 저장
        self.assertEqual(saved["route"], "lookup")
        self.assertIsInstance(seconds, float)
        self.assertGreaterEqual(seconds, 0.0)

    def test_save_failure_still_returns_answer(self):
        with mock.patch("api.chat_log.save_chat_log", side_effect=RuntimeError("DB 접속 실패")), \
             mock.patch("api.chat_log.print", create=True) as printed:
            r = self.client.post("/ask", json={"question": "알베도 원소가 뭐야?"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["answer"], ["바위"])
        printed.assert_called_once()                        # 오류는 출력만 한다
        self.assertIn("DB 접속 실패", printed.call_args.args[0])


class SeedTest(unittest.TestCase):
    def test_seed_file(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "seed.sql"
            n = make_seed(out=out)
            text = out.read_text(encoding="utf-8")
        self.assertEqual(n, 126)
        self.assertEqual(text.count("INSERT INTO characters"), 126)
        self.assertIn("ON CONFLICT (key)", text)

    def test_sql_quoting(self):
        self.assertEqual(sql_value(None), "NULL")
        self.assertEqual(sql_value("it's"), "'it''s'")


if __name__ == "__main__":
    unittest.main()
