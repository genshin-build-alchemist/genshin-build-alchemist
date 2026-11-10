"""웹 화면의 API 호출 로직 테스트 (demo/client.py). 실제 서버 없이 httpx.post를 가짜로 바꿔서 확인한다."""
import unittest
from unittest import mock

import httpx

from demo import client

URL = "https://example.ngrok-free.app"
OK_BODY = {
    "question": "카에데하라 카즈하 원소 뭐야?", "route": "lookup", "answer": ["바람"],
    "message": "카에데하라 카즈하의 원소는 바람이에요.",
    "evidence": [{"kind": "character", "title": "카에데하라 카즈하",
                  "doc_id": "character:kaedeharakazuha", "text": "..."}],
    "found": True, "needs_recheck": False, "model": "mock-rule", "method": "rag",
    "data_version": "8e5badd 2026-11-04 7.2 actual",
}


def fake_response(status, json_body=None, text=None):
    req = httpx.Request("POST", URL + "/ask")
    if json_body is not None:
        return httpx.Response(status, json=json_body, request=req)
    return httpx.Response(status, text=text or "", request=req)


class AskApiTest(unittest.TestCase):
    def ask(self, response=None, error=None, question="카에데하라 카즈하 원소 뭐야?"):
        with mock.patch("demo.client.httpx.post") as post:
            if error is not None:
                post.side_effect = error
            else:
                post.return_value = response
            result = client.ask_api(URL, question)
        return result, post

    def test_ok(self):
        result, post = self.ask(fake_response(200, OK_BODY))
        self.assertTrue(result["ok"])
        self.assertIsNone(result["error"])
        self.assertEqual(result["data"]["message"], OK_BODY["message"])
        self.assertIsInstance(result["seconds"], float)
        self.assertGreaterEqual(result["seconds"], 0)

    def test_request_shape(self):
        _, post = self.ask(fake_response(200, OK_BODY))
        args, kwargs = post.call_args
        self.assertEqual(args[0], URL + "/ask")
        self.assertEqual(kwargs["json"], {"question": "카에데하라 카즈하 원소 뭐야?"})
        self.assertEqual(kwargs["headers"]["ngrok-skip-browser-warning"], "true")
        self.assertGreaterEqual(kwargs["timeout"].read, 60)      # 실제 모델을 기다릴 만큼 넉넉하게

    def test_trailing_slash_in_url(self):
        with mock.patch("demo.client.httpx.post", return_value=fake_response(200, OK_BODY)) as post:
            client.ask_api(URL + "/", "질문")
        self.assertEqual(post.call_args[0][0], URL + "/ask")

    def test_server_off(self):
        result, _ = self.ask(error=httpx.ConnectError("refused"))
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], client.MSG_SERVER_OFF)

    def test_connect_timeout_is_server_off(self):
        result, _ = self.ask(error=httpx.ConnectTimeout("timeout"))
        self.assertEqual(result["error"], client.MSG_SERVER_OFF)

    def test_read_timeout(self):
        result, _ = self.ask(error=httpx.ReadTimeout("slow"))
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], client.MSG_TIMEOUT)

    def test_ngrok_offline_404_html(self):
        result, _ = self.ask(fake_response(404, text="<html>ERR_NGROK_3200</html>"))
        self.assertEqual(result["error"], client.MSG_SERVER_OFF)

    def test_ngrok_502_colab_down(self):
        result, _ = self.ask(fake_response(502, text="<html>ERR_NGROK_8012</html>"))
        self.assertEqual(result["error"], client.MSG_SERVER_OFF)

    def test_server_error_500(self):
        result, _ = self.ask(fake_response(500, text="Internal Server Error"))
        self.assertFalse(result["ok"])
        self.assertIn("500", result["error"])

    def test_html_instead_of_json(self):
        result, _ = self.ask(fake_response(200, text="<html>ngrok warning</html>"))
        self.assertEqual(result["error"], client.MSG_BAD_RESPONSE)

    def test_json_without_message(self):
        result, _ = self.ask(fake_response(200, {"status": "ok"}))
        self.assertEqual(result["error"], client.MSG_BAD_RESPONSE)

    def test_empty_question_not_sent(self):
        result, post = self.ask(fake_response(200, OK_BODY), question="   ")
        self.assertEqual(result["error"], client.MSG_EMPTY)
        post.assert_not_called()

    def test_too_long_question_not_sent(self):
        result, post = self.ask(fake_response(200, OK_BODY), question="가" * 301)
        self.assertEqual(result["error"], client.MSG_TOO_LONG)
        post.assert_not_called()

    def test_bad_url(self):
        result = client.ask_api("example.com", "질문")       # http:// 빠짐 -> 실제 요청 전에 실패
        self.assertEqual(result["error"], client.MSG_BAD_URL)


class FormatTest(unittest.TestCase):
    def test_doc_id_null(self):
        ev = client.format_evidence({"kind": "build", "title": "빌드 카드", "doc_id": None, "text": "t"})
        self.assertEqual(ev["doc_id"], client.NO_DOC_ID)
        self.assertEqual(ev["title"], "빌드 카드")

    def test_doc_id_missing(self):
        ev = client.format_evidence({"kind": "recheck", "title": "재확인", "text": "t"})
        self.assertEqual(ev["doc_id"], client.NO_DOC_ID)

    def test_doc_id_kept(self):
        ev = client.format_evidence(OK_BODY["evidence"][0])
        self.assertEqual(ev["doc_id"], "character:kaedeharakazuha")

    def test_not_found(self):
        notes = client.status_notes({**OK_BODY, "found": False, "answer": [], "evidence": []})
        self.assertEqual([lvl for lvl, _ in notes], ["info"])
        self.assertIn("찾지 못했어요", notes[0][1])

    def test_needs_recheck(self):
        notes = client.status_notes({**OK_BODY, "route": "build", "needs_recheck": True})
        self.assertEqual([lvl for lvl, _ in notes], ["warning"])
        self.assertIn("재확인 필요", notes[0][1])

    def test_normal_has_no_notes(self):
        self.assertEqual(client.status_notes(OK_BODY), [])


if __name__ == "__main__":
    unittest.main()
