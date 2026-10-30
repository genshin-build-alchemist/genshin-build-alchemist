"""data/characters_ko.json -> db/seed_characters.sql (characters 테이블에 넣을 INSERT 문).

실행: python3 db/make_seed.py
DB 드라이버 없이 SQL 파일만 만든다. 다시 실행해도 같은 행은 덮어쓴다(ON CONFLICT).
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "characters_ko.json"
OUT = ROOT / "db" / "seed_characters.sql"
COLUMNS = ("key", "name", "element", "weapon", "rarity", "region")


def sql_value(v):
    if v is None:
        return "NULL"
    return "'" + str(v).replace("'", "''") + "'"


def make_seed(src=SRC, out=OUT):
    chars = json.loads(Path(src).read_text(encoding="utf-8"))["characters"]
    lines = ["-- 자동 생성 파일: python3 db/make_seed.py", "BEGIN;"]
    for c in chars:
        values = ", ".join(sql_value(c[col]) for col in COLUMNS)
        lines.append(
            f"INSERT INTO characters ({', '.join(COLUMNS)}) VALUES ({values}) "
            f"ON CONFLICT (key) DO UPDATE SET name = EXCLUDED.name, element = EXCLUDED.element, "
            f"weapon = EXCLUDED.weapon, rarity = EXCLUDED.rarity, region = EXCLUDED.region;")
    lines.append("COMMIT;")
    Path(out).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(chars)


if __name__ == "__main__":
    n = make_seed()
    print(f"{OUT.relative_to(ROOT)} 생성: 캐릭터 {n}명")
