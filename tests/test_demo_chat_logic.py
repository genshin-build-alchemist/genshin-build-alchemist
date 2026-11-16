"""웹 화면의 화면과 상관없는 로직 테스트 (demo/chat_logic.py, demo/fake.py)."""
import unittest
from datetime import datetime, timezone

from demo import chat_logic as cl
from demo import fake

NOW = datetime(2026, 11, 16, 15, 5, tzinfo=cl.KST)       # 월요일 오후 3:05


class TimeTest(unittest.TestCase):
    def test_afternoon(self):
        self.assertEqual(cl.fmt_time(NOW), "오후 3:05")

    def test_midnight_and_noon(self):
        self.assertEqual(cl.fmt_time(datetime(2026, 11, 16, 0, 7, tzinfo=cl.KST)), "오전 12:07")
        self.assertEqual(cl.fmt_time(datetime(2026, 11, 16, 12, 30, tzinfo=cl.KST)), "오후 12:30")
        self.assertEqual(cl.fmt_time(datetime(2026, 11, 16, 9, 0, tzinfo=cl.KST)), "오전 9:00")

    def test_date_label(self):
        self.assertEqual(cl.fmt_date(NOW), "2026년 11월 16일 (월)")
        self.assertEqual(cl.fmt_date(datetime(2026, 11, 22, tzinfo=cl.KST)), "2026년 11월 22일 (일)")

    def test_utc_is_converted_to_kst(self):
        utc = datetime(2026, 11, 16, 16, 30, tzinfo=timezone.utc)   # 한국 시간 다음 날 오전 1:30
        self.assertEqual(cl.fmt_time(utc), "오전 1:30")
        self.assertEqual(cl.fmt_date(utc), "2026년 11월 17일 (화)")

    def test_now_is_kst(self):
        self.assertEqual(cl.now_kst().utcoffset().total_seconds(), 9 * 3600)


class UidTest(unittest.TestCase):
    def test_valid(self):
        for uid in ("812345678", "8123456789", " 812345678 "):
            self.assertTrue(cl.is_uid(uid), uid)

    def test_invalid(self):
        for uid in ("", None, "81234567", "81234567890", "81234567a", "812 345 678", "UID 812345678"):
            self.assertFalse(cl.is_uid(uid), uid)


class MessageTest(unittest.TestCase):
    def test_next_id(self):
        self.assertEqual(cl.next_id([]), 1)
        self.assertEqual(cl.next_id([{"id": 3}, {"id": 7}]), 8)

    def test_user_message(self):
        m = cl.user_message(1, "  알베도 원소가 뭐야? ", NOW)
        self.assertEqual(m, {"id": 1, "role": "user", "kind": "qa", "text": "알베도 원소가 뭐야?",
                             "time": "오후 3:05", "date": "2026년 11월 16일 (월)"})

    def test_build_user_message(self):
        m = cl.build_user_message(2, "812345678", NOW)
        self.assertEqual((m["role"], m["kind"], m["uid"]), ("user", "build", "812345678"))

    def test_pending_then_replace(self):
        msgs = [cl.user_message(1, "q", NOW), cl.pending_message(2, "q")]
        self.assertEqual(msgs[1]["status"], "pending")
        msgs = cl.replace_message(msgs, cl.assistant_message(2, "q", message="답"))
        self.assertEqual([m["status"] for m in msgs if m["role"] == "assistant"], ["ok"])
        self.assertEqual(len(msgs), 2)

    def test_server_answer_is_not_rich(self):
        self.assertFalse(cl.assistant_message(1, "q", message="<b>x</b>")["rich"])

    def test_error_message(self):
        m = cl.error_message(5, "q")
        self.assertEqual(m["status"], "error")
        self.assertEqual(m["notes"], [{"level": "err", "text": cl.SERVER_DOWN}])

    def test_guide_message(self):
        m = cl.guide_message(3, "help", NOW)
        self.assertEqual((m["role"], m["kind"], m["date"]), ("guide", "help", "2026년 11월 16일 (월)"))

    def test_saveable_skips_guide_and_pending(self):
        msgs = [cl.guide_message(1, "help", NOW), cl.user_message(2, "q", NOW), cl.pending_message(3, "q"),
                cl.user_message(4, "q2", NOW), cl.assistant_message(5, "q2", message="답")]
        self.assertEqual([m["id"] for m in cl.saveable(msgs)], [2, 4, 5])

    def test_view_data(self):
        d = cl.view_data([cl.user_message(1, "q", NOW)], busy=True)
        self.assertEqual(set(d), {"messages", "busy", "examples"})
        self.assertTrue(d["busy"])
        self.assertEqual(sum(1 for e in d["examples"] if e.get("build")), 1)


OK_DATA = {
    "question": "카에데하라 카즈하 원소 뭐야?", "route": "lookup", "answer": ["바람"],
    "message": "카에데하라 카즈하의 원소는 바람이에요.",
    "evidence": [{"kind": "character", "title": "카에데하라 카즈하",
                  "doc_id": "character:kaedeharakazuha", "text": "원소: 바람"}],
    "found": True, "needs_recheck": False, "model": "mock-rule", "method": "rag",
    "data_version": "8e5badd 2026-11-04 7.2 actual",
}


def ok(data, seconds=1.234):
    return {"ok": True, "data": data, "error": None, "seconds": seconds}


def fail(error):
    return {"ok": False, "data": None, "error": error, "seconds": 0.5}


class AnswerFromResultTest(unittest.TestCase):
    def test_ok(self):
        m = cl.answer_from_result(2, "q", ok(OK_DATA))
        self.assertEqual((m["status"], m["message"], m["seconds"], m["notes"]),
                         ("ok", OK_DATA["message"], 1.234, []))
        self.assertFalse(m["rich"])
        self.assertEqual(m["sources"], [{"k": "캐릭터", "t": "카에데하라 카즈하",
                                         "id": "character:kaedeharakazuha", "x": "원소: 바람"}])

    def test_server_off_and_timeout_show_server_down(self):
        for err in (cl.client.MSG_SERVER_OFF, cl.client.MSG_TIMEOUT):
            m = cl.answer_from_result(2, "q", fail(err))
            self.assertEqual(m["status"], "error")
            self.assertEqual(m["notes"], [{"level": "err", "text": cl.SERVER_DOWN}])

    def test_other_error_keeps_client_text(self):
        m = cl.answer_from_result(2, "q", fail("서버에서 오류가 났어요 (오류 코드 500)."))
        self.assertEqual(m["notes"][0]["level"], "err")
        self.assertIn("500", m["notes"][0]["text"])

    def test_not_found(self):
        data = {**OK_DATA, "found": False, "answer": [], "evidence": [], "message": "찾지 못했어요."}
        m = cl.answer_from_result(2, "q", ok(data))
        self.assertEqual(m["notes"], [{"level": "warn", "text": cl.NOT_FOUND}])
        self.assertEqual(m["sources"], [])

    def test_needs_recheck(self):
        data = {**OK_DATA, "route": "build", "needs_recheck": True,
                "evidence": [{"kind": "build_card", "title": "빌드 카드", "doc_id": None, "text": "t"},
                             {"kind": "new_kind", "title": "새 종류", "text": "t"}]}
        m = cl.answer_from_result(2, "q", ok(data))
        self.assertEqual(m["notes"], [{"level": "info", "text": cl.RECHECK}])
        self.assertEqual([(s["k"], s["id"]) for s in m["sources"]],
                         [("빌드", cl.client.NO_DOC_ID), ("new_kind", cl.client.NO_DOC_ID)])

    def test_html_in_answer_stays_plain(self):
        m = cl.answer_from_result(2, "q", ok({**OK_DATA, "message": "<img src=x onerror=alert(1)>"}))
        self.assertFalse(m["rich"])      # 화면(chat.js)에서 escape해서 글자로 보여 준다


class FakeTest(unittest.TestCase):
    def test_known_question(self):
        m, delay = fake.answer(2, "카즈하의 원소와 무기 종류는 뭐야?")
        self.assertEqual((m["status"], m["rich"], m["seconds"]), ("ok", True, 1.12))
        self.assertEqual(len(m["sources"]), 1)
        self.assertGreater(delay, 0)

    def test_not_found_has_warning_and_no_source(self):
        m, _ = fake.answer(2, "7.2 패치에서 새로 추가된 캐릭터는 누구야?")
        self.assertEqual(m["notes"], [{"level": "warn", "text": cl.NOT_FOUND}])
        self.assertEqual(m["sources"], [])

    def test_server_word_means_server_down(self):
        m, _ = fake.answer(2, "서버 괜찮아?")
        self.assertEqual(m["status"], "error")
        self.assertEqual(m["notes"][0]["text"], cl.SERVER_DOWN)

    def test_other_question_gets_default(self):
        m, _ = fake.answer(2, "아무 질문")
        self.assertEqual(m["message"], fake.DEFAULT["a"])

    def test_build_party(self):
        m, delay = fake.build_answer(3, "812345678")
        self.assertEqual((m["kind"], m["uid"], m["status"], m["seconds"]), ("build", "812345678", "ok", 3.82))
        self.assertEqual(len(m["party"]), 4)
        self.assertEqual(len(m["sources"]), 3)
        self.assertEqual(m["notes"][0]["level"], "info")
        self.assertGreater(delay, 0)

    def test_build_uid_ending_000_is_unchecked(self):
        m, _ = fake.build_answer(3, "812345000")
        self.assertEqual(m["notes"], [{"level": "orange", "text": fake.UID_CHECK}])
        self.assertNotIn("party", m)
        self.assertEqual(m["uid"], "812345000")      # 다시 시도 버튼에 쓰임

    def test_build_pending_has_steps(self):
        m = cl.pending_message(3, "UID 812345678 빌드 추천", kind="build", steps=fake.BUILD_STEPS)
        self.assertEqual((m["status"], m["kind"], len(m["steps"])), ("pending", "build", 3))

    def test_examples_have_fake_answers(self):
        for e in cl.EXAMPLES:
            if not e.get("build"):
                self.assertIn(e["q"], fake.QA)


if __name__ == "__main__":
    unittest.main()
