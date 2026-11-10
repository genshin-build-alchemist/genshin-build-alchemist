"""진짜 git 저장소를 임시로 만들어 수집 흐름 전체를 검사한다. 인터넷이 필요 없다."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from patchnotes.collector import collect_changes, version_snapshots
from patchnotes.documents import make_document_text, to_rag_documents

LANG = "src/data/Korean"


def git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def write(repo, rel, data):
    path = Path(repo) / LANG / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def commit(repo, message):
    git(repo, "add", "-A")
    git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", message)


class CollectorGitTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        repo = Path(cls.tmp.name)
        git(repo, "init", "-q")

        # 1.0: 치치 스킬만 있음
        write(repo, "talents/qiqi.json", {"id": 1, "name": "치치",
              "combat2": {"name": "나비의 서", "description": "치유량이 증가한다."}})
        write(repo, "weapons/oldsword.json", {"name": "낡은 검"})
        commit(repo, "1.0 data")

        # 버전 커밋이 아닌 커밋은 무시되어야 한다
        write(repo, "talents/qiqi.json", {"id": 1, "name": "치치",
              "combat2": {"name": "나비의 서", "description": "치유량이 증가한다."}, "note": "x"})
        commit(repo, "fix typo")

        # 1.1: 치치 설명 변경 + 신규 캐릭터 + 서식만 바뀐 파일 + 무기 삭제
        write(repo, "talents/qiqi.json", {"id": 1, "name": "치치",
              "combat2": {"name": "나비의 서", "description": "치유량과 지속 시간이 증가한다."}})
        write(repo, "characters/newbie.json", {"name": "신캐"})
        write(repo, "talents/formatonly.json", {"name": "서식", "d": "<color=#FFF>피해</color> 증가"})
        commit(repo, "1.1 data")

        # 1.2: 서식만 바꿈(기록되면 안 됨) + 무기 삭제
        write(repo, "talents/formatonly.json", {"name": "서식", "d": "피해 증가"})
        (repo / LANG / "weapons/oldsword.json").unlink()
        commit(repo, "1.2 data")
        cls.repo = repo

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_snapshots_ignore_non_version_commits_and_sort(self):
        snaps = version_snapshots(self.repo, "HEAD")
        self.assertEqual([s["version"] for s in snaps], ["1.0", "1.1", "1.2"])

    def test_collect_detects_modified_added_removed(self):
        window, records = collect_changes(self.repo, last=2, ref="HEAD")
        self.assertEqual([s["version"] for s in window], ["1.0", "1.1", "1.2"])
        by_key = {(r["version"], r["entity_id"]): r for r in records}

        modified = by_key[("1.1", "qiqi")]
        self.assertEqual(modified["change_type"], "modified")
        self.assertEqual(modified["entity_name"], "치치")
        self.assertEqual(modified["changes"][0]["field"], "combat2/description")

        self.assertEqual(by_key[("1.1", "newbie")]["change_type"], "added")
        self.assertEqual(by_key[("1.2", "oldsword")]["change_type"], "removed")

    def test_format_only_changes_are_not_recorded(self):
        _, records = collect_changes(self.repo, last=2, ref="HEAD")
        self.assertNotIn("formatonly", [r["entity_id"] for r in records if r["version"] == "1.2"])

    def test_last_limits_the_window(self):
        window, records = collect_changes(self.repo, last=1, ref="HEAD")
        self.assertEqual([s["version"] for s in window], ["1.1", "1.2"])
        self.assertTrue(all(r["version"] == "1.2" for r in records))

    def test_since_starts_from_that_version(self):
        window, records = collect_changes(self.repo, since="1.2", ref="HEAD")
        self.assertEqual([s["version"] for s in window], ["1.1", "1.2"])     # 1.2의 변경 = 1.1 -> 1.2 비교
        self.assertTrue(all(r["version"] == "1.2" for r in records))
        window, _ = collect_changes(self.repo, since="1.0", ref="HEAD")
        self.assertEqual([s["version"] for s in window], ["1.0", "1.1", "1.2"])
        with self.assertRaises(ValueError):
            collect_changes(self.repo, since="9.0", ref="HEAD")

    def test_documents_are_readable_and_have_metadata(self):
        _, records = collect_changes(self.repo, last=2, ref="HEAD")
        docs = {d["id"]: d for d in to_rag_documents(records)}
        doc = docs["1.1:talents:qiqi"]
        self.assertIn("치치", doc["text"])
        self.assertIn("원소 스킬 설명", doc["text"])
        self.assertIn("지속 시간", doc["text"])
        self.assertEqual(doc["metadata"]["version"], "1.1")
        self.assertIn("신규 추가됨", make_document_text(
            next(r for r in records if r["entity_id"] == "newbie")))

    def test_needs_two_versions(self):
        with tempfile.TemporaryDirectory() as d:
            git(d, "init", "-q")
            write(d, "talents/a.json", {"name": "a"})
            commit(d, "1.0 data")
            with self.assertRaises(ValueError):
                collect_changes(d, last=3, ref="HEAD")


if __name__ == "__main__":
    unittest.main()
