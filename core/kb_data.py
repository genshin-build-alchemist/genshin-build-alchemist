"""genshin-db 원본 -> 챗봇 기본 데이터 (data/characters_ko.json, data/items_ko.json).

  characters_ko.json : 캐릭터 이름·원소·무기·성급·지역 (조회·조건 검색, 평가셋 정답의 출처)
  items_ko.json      : 무기(종류·성급·주옵션·효과 이름), 성유물(1·2·4세트 효과)

빈 값과 '없음'은 null로 통일한다 (예: 여행자 원소, 지역이 아직 없는 최신 캐릭터).
genshin-db 커밋은 core/documents.py의 DATA_COMMIT 하나로 맞춘다 (검색 문서와 같은 시점이어야 한다).

실행
  python3 -m core.kb_data --fetch      # DATA_COMMIT 원본을 collector/cache에 받은 뒤 만들기
  python3 -m core.kb_data              # 이미 받은 원본으로 만들기
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

from core.documents import DATA_COMMIT, DEFAULT_GENSHIN_DB, fetch_genshin_db

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
SOURCE = "theBowja/genshin-db (MIT) src/data/Korean/"


def _value(x):
    """빈 값·'없음' -> None"""
    if isinstance(x, str) and x.strip() in ("", "없음"):
        return None
    return x


def _rarity(n):
    return f"{n}성" if n else None


def _load(base, folder):
    for path in sorted((base / folder).glob("*.json")):
        yield path.stem, json.loads(path.read_text(encoding="utf-8"))


def build_kb_data(genshin_db):
    """genshin-db 저장소 경로 -> (characters 목록, weapons 목록, artifacts 목록). key(파일 이름) 순."""
    base = Path(genshin_db) / "src" / "data" / "Korean"
    if not base.is_dir():
        raise FileNotFoundError(f"{base} 가 없습니다. 먼저 'python3 -m core.kb_data --fetch'로 원본을 받으세요.")
    characters = [{"key": k, "name": d["name"], "element": _value(d.get("elementText")),
                   "weapon": _value(d.get("weaponText")), "rarity": _rarity(d.get("rarity")),
                   "region": _value(d.get("region"))}
                  for k, d in _load(base, "characters")]
    weapons = [{"key": k, "name": d["name"], "weapon": _value(d.get("weaponText")),
                "rarity": _rarity(d.get("rarity")), "main_stat": _value(d.get("mainStatText")),
                "effect_name": _value(d.get("effectName"))}
               for k, d in _load(base, "weapons")]
    artifacts = [{"key": k, "name": d["name"], "effect_1pc": _value(d.get("effect1Pc")),
                  "effect_2pc": _value(d.get("effect2Pc")), "effect_4pc": _value(d.get("effect4Pc"))}
                 for k, d in _load(base, "artifacts")]
    return characters, weapons, artifacts


def commit_label(genshin_db):
    """'8e5badd 2026-11-04 7.2 actual' 같은 출처 표시 (data_version으로 API 응답에 나간다)."""
    out = subprocess.run(["git", "-C", str(genshin_db), "log", "-1", "--format=%h %cs %s", "--abbrev=7", "HEAD"],
                         capture_output=True, text=True, encoding="utf-8", check=True)
    return out.stdout.strip()


def write_kb_data(characters, weapons, artifacts, commit, out_dir=DATA_DIR):
    out_dir = Path(out_dir)
    chars = {"source": SOURCE + "characters", "commit": commit, "count": len(characters), "characters": characters}
    items = {"source": SOURCE + "weapons, artifacts", "commit": commit, "weapons": weapons, "artifacts": artifacts}
    for name, data in (("characters_ko.json", chars), ("items_ko.json", items)):
        (out_dir / name).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return out_dir


def main(argv=None):
    parser = argparse.ArgumentParser(description="genshin-db 원본 -> data/characters_ko.json, data/items_ko.json")
    parser.add_argument("--genshin-db", default=str(DEFAULT_GENSHIN_DB), help="genshin-db 저장소 경로")
    parser.add_argument("--out", default=str(DATA_DIR), help="결과 폴더 (기본 data)")
    parser.add_argument("--fetch", action="store_true", help=f"원본({DATA_COMMIT})을 받은 뒤 만들기")
    args = parser.parse_args(argv)
    if args.fetch:
        fetch_genshin_db(args.genshin_db)
    characters, weapons, artifacts = build_kb_data(args.genshin_db)
    out = write_kb_data(characters, weapons, artifacts, commit_label(args.genshin_db), args.out)
    print(f"캐릭터 {len(characters)}명, 무기 {len(weapons)}개, 성유물 {len(artifacts)}세트 -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
