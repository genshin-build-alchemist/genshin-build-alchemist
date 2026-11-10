"""genshin-db 깃 이력에서 버전별 변경 이력을 뽑아 JSON/JSONL로 저장한다.

실행: python3 collect_patchnotes.py --since 5.0      (5.0부터 최신까지, 팀 기본 범위)
      python3 collect_patchnotes.py --last 3         (최근 3개 버전 구간)
표기만 바뀐 변경(잡음)은 기본으로 거른다 (patchnotes/noise.py). 거르지 않으려면 --keep-noise
"""
import argparse
import json
from collections import Counter
from pathlib import Path

from patchnotes.collector import collect_changes, ensure_repo
from patchnotes.documents import to_rag_documents
from patchnotes.noise import drop_noise

ROOT = Path(__file__).parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--last", type=int, default=3, help="최근 몇 개 버전 구간을 뽑을지 (--since가 없을 때)")
    ap.add_argument("--since", help="이 버전부터 최신까지 뽑기 (예: 5.0)")
    ap.add_argument("--keep-noise", action="store_true", help="표기만 바뀐 변경도 남기기")
    ap.add_argument("--repo-dir", default=str(ROOT / "cache" / "genshin-db"))
    ap.add_argument("--out-dir", default=str(ROOT / "out"))
    args = ap.parse_args()

    print("[1/4] 저장소 준비 중... (처음에는 1~2분 걸릴 수 있습니다)")
    repo = ensure_repo(args.repo_dir)

    print("[2/4] 버전별 변경 이력 계산 중...")
    window, records = collect_changes(repo, last=args.last, since=args.since)
    print("      대상 버전:", " -> ".join(s["version"] for s in window))
    if not args.keep_noise:
        total = len(records)
        records, by_rule, dropped = drop_noise(records)
        print(f"      잡음 거르기: 기록 {total}건 -> {len(records)}건 (통째로 빠진 기록 {dropped}건)")
        for rule, n in by_rule.most_common():
            print(f"        - {rule}: 변경 {n}개")

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
