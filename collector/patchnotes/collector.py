"""genshin-db 깃 이력에서 '버전별 변경 이력'을 뽑아낸다.

흐름: 저장소 준비 -> 버전별 대표 커밋 찾기 -> 연속된 두 버전의 한국어 데이터 비교 -> 변경 기록 목록
"""
import json
import re
import subprocess
from pathlib import Path

from .differ import diff_json

REPO_URL = "https://github.com/theBowja/genshin-db"
LANG_DIR = "src/data/Korean"
FOLDERS = ["characters", "talents", "constellations", "weapons"]
DEFAULT_REF = "origin/HEAD"          # 실제 저장소용. 테스트에서는 "HEAD"를 넘긴다.
VERSION_RE = re.compile(r"^(\d+)\.(\d+)\b")


def run_git(repo, *args):
    result = subprocess.run(["git", "-C", str(repo), *args],
                            capture_output=True, text=True, encoding="utf-8")
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} 실패: {result.stderr.strip()}")
    return result.stdout


def ensure_repo(repo_dir, url=REPO_URL):
    """없으면 가볍게 복제(파일 내용은 필요할 때만 받음), 있으면 최신으로 갱신."""
    repo_dir = Path(repo_dir)
    if (repo_dir / ".git").exists():
        run_git(repo_dir, "fetch", "--quiet", "origin")
        return repo_dir
    repo_dir.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["git", "clone", "--quiet", "--filter=blob:none", "--no-checkout", url, str(repo_dir)],
        capture_output=True, text=True, encoding="utf-8")
    if result.returncode != 0:
        raise RuntimeError(f"저장소 복제 실패(네트워크를 확인하세요): {result.stderr.strip()}")
    return repo_dir


def parse_version(subject):
    """커밋 제목에서 버전 추출: '7.1 data' -> '7.1', 'fix typo' -> None"""
    m = VERSION_RE.match(subject.strip())
    return f"{m.group(1)}.{m.group(2)}" if m else None


def _version_key(version):
    return tuple(int(x) for x in version.split("."))


def version_snapshots(repo, ref=DEFAULT_REF):
    """버전마다 가장 최근 커밋 1개를 골라 오래된 버전부터 정렬해 돌려준다."""
    out = run_git(repo, "log", ref, "--format=%H%x09%cs%x09%s", "--", LANG_DIR)
    seen = {}
    for line in out.splitlines():
        commit, date, subject = line.split("\t", 2)
        version = parse_version(subject)
        if version and version not in seen:      # git log는 최신순이라 처음 만난 것이 최신
            seen[version] = {"version": version, "commit": commit, "date": date, "subject": subject}
    return sorted(seen.values(), key=lambda s: _version_key(s["version"]))


def _read_json(repo, rev, path):
    try:
        return json.loads(run_git(repo, "show", f"{rev}:{path}"))
    except RuntimeError:
        return None


def _changed_files(repo, old_rev, new_rev):
    paths = [f"{LANG_DIR}/{folder}" for folder in FOLDERS]
    run_git(repo, "diff", "--no-renames", "--numstat", old_rev, new_rev, "--", *paths)  # 필요한 파일을 한꺼번에 미리 받아 둠
    out = run_git(repo, "diff", "--no-renames", "--name-status", old_rev, new_rev, "--", *paths)
    return [line.split("\t", 1) for line in out.splitlines() if line.strip()]


def diff_versions(repo, old, new):
    """연속된 두 버전(old, new 스냅샷) 사이의 변경 기록 목록을 만든다."""
    records = []
    for status, path in _changed_files(repo, old["commit"], new["commit"]):
        parts = path.split("/")
        folder, entity_id = parts[-2], parts[-1].removesuffix(".json")
        before = _read_json(repo, old["commit"], path) if status != "A" else None
        after = _read_json(repo, new["commit"], path) if status != "D" else None
        base = {
            "version": new["version"], "from_version": old["version"],
            "data_commit": new["commit"][:7], "data_date": new["date"],
            "folder": folder, "entity_id": entity_id,
            "entity_name": (after or before or {}).get("name", entity_id),
        }
        if status == "A":
            records.append({**base, "change_type": "added", "changes": []})
        elif status == "D":
            records.append({**base, "change_type": "removed", "changes": []})
        else:
            changes = diff_json(before, after)
            if changes:   # 서식만 바뀐 파일은 건너뜀
                records.append({**base, "change_type": "modified", "changes": changes})
    return records


def collect_changes(repo, last=3, ref=DEFAULT_REF, since=None):
    """버전 구간(예: 6.6->6.7, 6.7->7.0 ...)의 변경 기록을 모두 모은다.
    since를 주면 그 버전부터 최신까지(예: since='5.0' -> 4.8->5.0 ... 7.1->7.2), 없으면 최근 last개 구간."""
    snapshots = version_snapshots(repo, ref)
    if len(snapshots) < 2:
        raise ValueError("버전 커밋이 2개 미만이라 비교할 수 없습니다.")
    if since:
        start = next((i for i, s in enumerate(snapshots) if _version_key(s["version"]) >= _version_key(since)), None)
        if start is None:
            raise ValueError(f"{since} 이후 버전 커밋이 없습니다.")
        window = snapshots[max(start - 1, 0):]      # 시작 버전의 바로 앞 버전과 비교해야 그 버전의 변경이 나온다
    else:
        window = snapshots[-(last + 1):]
    records = []
    for old, new in zip(window, window[1:]):
        records.extend(diff_versions(repo, old, new))
    return window, records
