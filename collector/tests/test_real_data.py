"""실제 genshin-db 저장소로 하는 점검. 인터넷이 필요해서 기본은 건너뛴다.

실행: RUN_NETWORK_TESTS=1 python3 -m unittest tests.test_real_data -v
(저장소를 이미 받아 둔 경우 GENSHIN_DB_CACHE=경로 를 같이 주면 다시 받지 않는다)
"""
import os
import tempfile
import unittest
from pathlib import Path

from patchnotes.collector import collect_changes, ensure_repo, version_snapshots
from patchnotes.documents import to_rag_documents


@unittest.skipUnless(os.environ.get("RUN_NETWORK_TESTS") == "1", "RUN_NETWORK_TESTS=1 일 때만 실행")
class RealDataTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cache = os.environ.get("GENSHIN_DB_CACHE")
        if cache:
            cls.repo = ensure_repo(cache)
        else:
            cls.tmp = tempfile.TemporaryDirectory()
            cls.repo = ensure_repo(Path(cls.tmp.name) / "genshin-db")

    def test_has_many_versions_in_order(self):
        snaps = version_snapshots(self.repo)
        self.assertGreaterEqual(len(snaps), 10)
        keys = [tuple(map(int, s["version"].split("."))) for s in snaps]
        self.assertEqual(keys, sorted(keys))

    def test_recent_versions_produce_clean_korean_documents(self):
        window, records = collect_changes(self.repo, last=2)
        self.assertEqual(len(window), 3)
        self.assertGreater(len(records), 0)
        docs = to_rag_documents(records)
        for doc in docs:
            self.assertNotIn("<color", doc["text"])     # 서식 태그가 남아 있으면 안 됨
            self.assertTrue(doc["metadata"]["entity_name"])


if __name__ == "__main__":
    unittest.main()
