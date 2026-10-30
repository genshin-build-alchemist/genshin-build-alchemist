"""genshin-db 깃 이력에서 최근 N개 버전의 변경 이력을 뽑아 JSON/JSONL로 저장한다.

실행: python3 collect_patchnotes.py --last 3
"""
import argparse
import json
from collections import Counter
from pathlib import Path

from patchnotes.collector import collect_changes, ensure_repo
from patchnotes.documents import to_rag_documents

ROOT = Path(__file__).parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--last", type=int, default=3, help="최근 몇 개 버전 구간을 뽑을지")
    ap.add_argument("--repo-dir", default=str(ROOT / "cache" / "genshin-db"))
    ap.add_argument("--out-dir", default=str(ROOT / "out"))
    args = ap.parse_args()

    print("[1/4] 저장소 준비 중... (처음에는 1~2분 걸릴 수 있습니다)")
    repo = ensure_repo(args.repo_dir)

    print("[2/4] 버전별 변경 이력 계산 중...")
    window, records = collect_changes(repo, last=args.last)
    print("      대상 버전:", " -> ".join(s["version"] for s in window))

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "patch_changes.json").write_text(
        json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")

    docs = to_rag_documents(records)
    with (out_dir / "patch_docs.jsonl").open("w", encoding="utf-8") as f:
        for doc in docs:
            f.write(json.dumps(doc, ensure_ascii=False) + "\n")

    print(f"[3/4] 저장 완료: {out_dir}/patch_changes.json, patch_docs.jsonl")
    print("[4/4] 요약")
    summary = Counter((r["version"], r["change_type"]) for r in records)
    for (version, ctype), n in sorted(summary.items()):
        print(f"      {version} {ctype}: {n}건")
    modified = [d for d in docs if d["metadata"]["change_type"] == "modified"]
    for doc in modified[:3]:
        print("      ---\n      " + doc["text"].replace("\n", "\n      "))


if __name__ == "__main__":
    main()
