"""lib/loader.py 테스트 (검증 규칙 · 계산 · 읽기 전용 · 실행 위치와 무관한 경로).

실행 (저장소 루트에서): python -m unittest discover -s dashboard/tests
"""
import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

DASHBOARD = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(DASHBOARD))

from lib import loader  # noqa: E402
from lib.loader import fmt  # noqa: E402

HAS_DATA = all((loader.DATA_DIR / f).is_dir() for f in loader.FOLDERS)


def question(i, f1=1.0, qtype="lookup", seconds=1.0):
    return {"id": f"{qtype}_{i}", "question": f"질문{i}", "type": qtype, "field": "element",
            "gold": ["물"], "pred": ["물"] if f1 == 1.0 else ["불"], "raw": "", "f1": f1, "seconds": seconds}


def result(method="rag", n=4, limit=None, macro=None, dataset="info_v2-dev", code="main@aaa",
           created="2026-11-10T06:00:00", experiment_id=None, **extra):
    pq = [question(i, 1.0 if i % 2 else 0.5) for i in range(n)]
    data = {"experiment_id": experiment_id or f"dev_{method}", "method": method, "dataset_version": dataset,
            "created_at": created, "limit": limit, "config": {"code_version": code},
            "metrics": {"n": n, "macro_f1": loader.recompute_macro_f1(pq) if macro is None else macro},
            "per_question": pq}
    data.update(extra)
    return data


class FakeData:
    """임시 data 폴더. files = {'dev': {'a.json': {...}}}"""

    def __init__(self, files):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name)
        for folder, items in files.items():
            (self.path / folder).mkdir()
            for name, data in items.items():
                (self.path / folder / name).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def load(self, folder, order=None):
        return loader.load_folder(folder, self.path, order)

    def cleanup(self):
        self._tmp.cleanup()


def levels(res):
    return [c["level"] for c in res["checks"]]


class CheckRulesTest(unittest.TestCase):
    """README 2-2, 2-3 규칙 하나당 테스트 하나."""

    def run_folder(self, files, folder="dev", order=None):
        fake = FakeData({folder: files})
        self.addCleanup(fake.cleanup)
        return fake.load(folder, order)

    def test_clean_folder_has_no_checks(self):
        res = self.run_folder({"a.json": result("baseline"), "b.json": result("rag")})
        self.assertEqual(res["checks"], [])
        self.assertEqual([r["key"] for r in res["runs"]], ["baseline", "rag"])

    def test_order_follows_stages_not_filename(self):
        res = self.run_folder({"a.json": result("rag_v4"), "z.json": result("baseline")})
        self.assertEqual([r["key"] for r in res["runs"]], ["baseline", "rag_v4"])

    def test_post_excluded_without_warning(self):
        res = self.run_folder({"a.json": result("rag_v4"), "a_post.json": result("rag_v4+post")})
        self.assertEqual([r["file"] for r in res["runs"]], ["a.json"])
        self.assertEqual(res["excluded"][0]["file"], "a_post.json")
        self.assertEqual(res["checks"], [])

    def test_limit_not_null_excluded_yellow(self):
        res = self.run_folder({"a.json": result("rag"), "b.json": result("rag_v3", limit=20)})
        self.assertEqual([r["key"] for r in res["runs"]], ["rag"])
        self.assertEqual(levels(res), ["yellow"])

    def test_limit_missing_excluded_yellow(self):
        data = result("rag")
        del data["limit"]
        res = self.run_folder({"a.json": data})
        self.assertEqual(res["runs"], [])
        self.assertEqual(levels(res), ["yellow"])

    def test_aux_without_limit_is_kept(self):
        aux = {"experiment_id": "aux_dev_rag", "method": "rag", "dataset_version": "info_v2-dev",
               "created_at": "2026-11-10T07:00:00", "config": {"code_version": "main@b"},
               "metrics": {"n": 60, "accuracy": 0.5}, "hallucinations": []}
        res = self.run_folder({"aux_dev_rag.json": aux}, folder="aux")
        self.assertEqual(len(res["runs"]), 1)
        self.assertEqual(res["checks"], [])

    def test_dataset_version_mixed_red(self):
        res = self.run_folder({"a.json": result("rag"), "b.json": result("rag_v3", dataset="info_v1-dev")})
        self.assertIn("red", levels(res))

    def test_n_mismatch_yellow(self):
        data = result("rag")
        data["metrics"]["n"] = 99
        res = self.run_folder({"a.json": data})
        self.assertEqual(levels(res), ["yellow"])
        self.assertIn("99", res["checks"][0]["msg"])

    def test_macro_mismatch_yellow(self):
        res = self.run_folder({"a.json": result("rag", macro=0.9)})
        self.assertEqual(levels(res), ["yellow"])
        self.assertIn("macro F1", res["checks"][0]["msg"])

    def test_code_version_mixed_no_check(self):
        # code_version이 달라도 안내하지 않는다 (11/12 결정)
        res = self.run_folder({"a.json": result("rag"), "b.json": result("rag_v3", code="main@bbb")})
        self.assertEqual(res["checks"], [])

    def test_duplicate_method_uses_latest(self):
        res = self.run_folder({"old.json": result("rag", created="2026-11-01T00:00:00"),
                               "new.json": result("rag", created="2026-11-09T00:00:00")})
        self.assertEqual([r["file"] for r in res["runs"]], ["new.json"])
        self.assertEqual(levels(res), ["yellow"])

    def test_unregistered_method_goes_last(self):
        res = self.run_folder({"a.json": result("rag_v5"), "b.json": result("rag")})
        self.assertEqual([r["key"] for r in res["runs"]], ["rag", "rag_v5"])
        self.assertIn("rag_v5", res["checks"][0]["msg"])

    def test_custom_order(self):
        res = self.run_folder({"a.json": result("rag_v5"), "b.json": result("rag")}, order=["rag", "rag_v5"])
        self.assertEqual(res["checks"], [])

    def test_latest_created_at_ignores_excluded(self):
        res = self.run_folder({"a.json": result("rag", created="2026-11-10T06:00:00"),
                               "a_post.json": result("rag+post", created="2026-11-10T09:00:00")})
        self.assertEqual(res["latest_created_at"], "2026-11-10T06:00:00")

    def test_model_compare_keys_by_model(self):
        files = {f"{eid}.json": result("rag_v4", experiment_id=eid, dataset="info_v1-dev")
                 for eid in ["dev_rag_v4_qwen2.5-7b-fp16-T4", "dev_rag_v4_qwen2.5-1.5b-fp16-l4",
                             "dev_rag_v4_qwen2.5-7b-bf16-l4"]}
        res = self.run_folder(files, folder="model_compare")
        self.assertEqual([loader.model_label(r) for r in res["runs"]],
                         ["1.5B · L4 · fp16", "7B · L4 · bf16", "7B · T4 · fp16"])
        self.assertEqual(res["checks"], [])   # method가 모두 rag_v4여도 중복이 아님

    def test_model_compare_bad_id_excluded(self):
        res = self.run_folder({"x.json": result("rag_v4", experiment_id="dev_rag_v4_llama")}, folder="model_compare")
        self.assertEqual(res["runs"], [])
        self.assertEqual(levels(res), ["yellow"])

    def test_missing_folder_is_empty(self):
        res = self.run_folder({}, folder="dev")
        self.assertEqual(res["runs"], [])
        self.assertIsNone(res["latest_created_at"])


class CalcTest(unittest.TestCase):
    def test_fmt(self):
        self.assertEqual(fmt(0.8165), "0.817")
        self.assertEqual(fmt(0.8115), "0.812")   # round()는 0.811이 됨 -> 5 이상 올림
        self.assertEqual(fmt(1.0), "1.0")
        self.assertEqual(fmt(6.59), "6.59")
        self.assertEqual(fmt(12), "12")
        self.assertEqual(fmt(None), "기록 없음")
        self.assertEqual(fmt(3.0625, digits=1), "3.1")

    def test_pearson_r(self):
        self.assertAlmostEqual(loader.pearson_r([1, 2, 3], [2, 4, 6]), 1.0)
        self.assertAlmostEqual(loader.pearson_r([1, 2, 3], [3, 2, 1]), -1.0)
        self.assertAlmostEqual(loader.pearson_r([1, 2, 3, 4], [1, 3, 2, 4]), 0.8)
        self.assertIsNone(loader.pearson_r([1, 1, 1], [1, 2, 3]))   # 편차가 0
        self.assertIsNone(loader.pearson_r([1], [1]))

    def test_parse_model_id(self):
        self.assertEqual(loader.parse_model_id("dev_rag_v4_qwen2.5-7b-bf16-l4"),
                         {"size": "7B", "precision": "bf16", "gpu": "L4", "size_num": 7.0})
        self.assertEqual(loader.parse_model_id("dev_rag_v4_qwen2.5-1.5b-fp16-T4")["size"], "1.5B")
        self.assertIsNone(loader.parse_model_id("dev_rag_v4"))

    def test_best_of_tie(self):
        self.assertEqual(loader.best_of([("1.5B", 1.0), ("3B", 1.0), ("7B", 0.975)]), (["1.5B", "3B"], 1.0))
        self.assertEqual(loader.best_of([("1.5B", 1.142), ("3B", 1.843)], higher=False), (["1.5B"], 1.142))

    def test_hallucinations_by_type(self):
        aux = {"hallucinations": [{"id": "filter_a"}, {"id": "filter_b"}, {"id": "unknown_1"}, {"id": "x"}]}
        self.assertEqual(loader.hallucinations_by_type(aux), {"lookup": 0, "filter": 2, "unknown": 1, "other": 1})
        self.assertIsNone(loader.hallucinations_by_type({}))

    def test_question_helpers(self):
        data = {"per_question": [question(0, 1.0, "filter", 1.0), question(1, 0.5, "filter", 3.0),
                                 question(2, 1.0, "lookup", 2.0)]}
        self.assertEqual(loader.median_seconds(data), 2.0)
        self.assertEqual(loader.median_seconds(data, "filter"), 2.0)
        self.assertEqual(loader.avg_answer_len(data), 1)
        self.assertEqual([w["id"] for w in loader.wrong_questions(data)], ["filter_1"])
        self.assertIsNone(loader.median_seconds({"per_question": []}))


@unittest.skipUnless(HAS_DATA, "dashboard/data 폴더가 없음")
class RealDataTest(unittest.TestCase):
    """실제 결과 JSON으로 와이어프레임 숫자가 나오는지 (dashboard/data)."""

    @classmethod
    def setUpClass(cls):
        cls.all = loader.load_all()

    def run_of(self, folder, key):
        return next(r for r in self.all[folder]["runs"] if r["key"] == key)

    def test_no_red_or_yellow(self):
        bad = [c for c in loader.all_checks(self.all) if c["level"] in ("red", "yellow")]
        self.assertEqual(bad, [])

    def test_runs_count(self):
        self.assertEqual({f: len(r["runs"]) for f, r in self.all.items()},
                         {"official": 5, "dev": 5, "aux": 5, "model_compare": 8})

    def test_dev_numbers(self):
        d = self.run_of("dev", "rag_v4")["data"]
        self.assertEqual(fmt(loader.median_seconds(d)), "1.482")
        self.assertEqual(fmt(loader.metric(d, "avg_seconds", "filter")), "4.713")
        runs = self.all["dev"]["runs"]
        r = loader.pearson_r([loader.metric(x["data"], "empty_answers") for x in runs],
                             [loader.metric(x["data"], "avg_seconds") for x in runs])
        self.assertEqual(fmt(r), "-0.904")

    def test_model_compare_numbers(self):
        by = {loader.model_label(r): r["data"] for r in self.all["model_compare"]["runs"]}
        self.assertEqual([fmt(loader.avg_answer_len(by[f"{s} · L4 · fp16"]), 1) for s in ("1.5B", "3B", "7B")],
                         ["3.1", "12.8", "8.1"])
        self.assertEqual(fmt(loader.metric(by["7B · T4 · 4bit"], "macro_f1")), "0.812")

    def test_aux_hallucination_types(self):
        aux = self.run_of("aux", "rag_v4")["data"]
        self.assertEqual(loader.hallucinations_by_type(aux), {"lookup": 0, "filter": 4, "unknown": 1, "other": 0})

    def test_official_unknown_wrong(self):
        wrong = loader.wrong_questions(self.run_of("official", "rag_v4")["data"], "unknown")
        self.assertEqual([w["question"] for w in wrong], ["나디르는 몇 성 캐릭터야?", "티엔류는 몇 성 캐릭터야?"])

    def test_files_not_modified(self):
        files = sorted(loader.DATA_DIR.rglob("*.json"))
        before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
        loader.load_all()
        after = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
        self.assertEqual(before, after)

    def test_works_from_other_directory(self):
        # 배포(Streamlit Cloud)처럼 실행 위치가 달라도 같은 파일을 찾는다
        old = os.getcwd()
        with tempfile.TemporaryDirectory() as tmp:
            os.chdir(tmp)
            try:
                res = loader.load_folder("official")
            finally:
                os.chdir(old)
        self.assertEqual(len(res["runs"]), 5)


if __name__ == "__main__":
    unittest.main()
