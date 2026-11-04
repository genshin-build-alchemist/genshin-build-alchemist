"""genshin-db 원본 -> RAG 검색용 문서 (P1 기본 단계 1-1 문서 전처리, 1-2 청킹의 입력).

문서 1개 = 검색 단위 1개. 종류(kind)
  character      : 캐릭터 프로필 (원소·무기·성급·지역·소속·칭호·설명)
  talent         : 스킬·고유 특성 1개 (일반 공격 / 원소 스킬 / 원소 폭발 / 고유 특성 N)
  constellation  : 명의 자리 1~6 (캐릭터 1명당 1문서)
  weapon         : 무기 (종류·성급·주옵션·효과·1재련 효과·설명)
  artifact       : 성유물 세트 (1·2·4세트 효과, 부위 이름)
  patch          : 패치 변경 기록 1건 (data/patch_changes.json, collector가 만든 것)

전처리 규칙 (전후 비교표는 data/docs/preprocess_report.md)
  1. 게임 서식 태그 제거 (<color=...>, <i> 등)
  2. 자리표시자 템플릿({0}) 대신 값이 채워진 1재련 설명 사용
  3. 빈 값·'없음' -> 본문에는 '정보 없음', 메타데이터에는 null (characters_ko.json과 같은 규칙)
  4. 검색에 쓰지 않는 필드 제외: 육성 재료(costs), 성우(cv, 실존 인물 이름), 긴 이야기(story),
     내부 코드(ELEMENT_GEO 같은 type 값, id), 서식 태그가 남은 원문(descriptionRaw)
  5. 공백·빈 줄 정리
  6. 본문이 완전히 같은 문서는 하나만 남김 (예: 같은 이름의 무기)

실행
  python3 -m core.documents --fetch                  # genshin-db 원본을 collector/cache에 받기 (처음 한 번)
  python3 -m core.documents                          # data/docs/documents_ko.jsonl + preprocess_report.md
  python3 -m core.documents --genshin-db 경로         # 원본 위치를 직접 지정
"""
import argparse
import hashlib
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_COMMIT = "49a6544"                       # data/*.json과 같은 genshin-db 커밋 (7.1)
DEFAULT_GENSHIN_DB = ROOT / "collector" / "cache" / "genshin-db"
OUT_DIR = ROOT / "data" / "docs"
FOLDERS = ("characters", "talents", "constellations", "weapons", "artifacts")
EXCLUDED_FIELDS = {
    "costs": "육성 재료 (검색 질문과 무관, 분량이 큼)",
    "cv": "성우 이름 (실존 인물 정보, 서비스에 불필요)",
    "story": "긴 이야기 글 (설정 문장이 검색을 방해)",
    "descriptionRaw": "서식 태그가 남은 원문 (정리된 description과 중복)",
    "effectTemplateRaw": "자리표시자 {0}가 남은 템플릿 (1재련 설명으로 대체)",
    "id / *Type": "내부 코드 (ELEMENT_GEO 등, 한글 값과 중복)",
}

TAG = re.compile(r"<[^>]+>")
SPACES = re.compile(r"[ \t]+")
NO_INFO = "정보 없음"
SLOT_NAMES = {"combat1": "일반 공격", "combat2": "원소 스킬", "combat3": "원소 폭발",
              "passive1": "고유 특성 1", "passive2": "고유 특성 2", "passive3": "고유 특성 3",
              "passive4": "고유 특성 4"}
PIECES = (("flower", "생명의 꽃"), ("plume", "죽음의 깃털"), ("sands", "시간의 모래"),
          ("goblet", "공간의 성배"), ("circlet", "이성의 왕관"))


# ── 정리 도구 ───────────────────────────────────────────────
class Stats:
    """전처리 전후 비교표에 쓸 숫자를 모은다."""

    def __init__(self):
        self.raw_files = Counter()
        self.raw_chars = Counter()
        self.tags_removed = Counter()
        self.excluded_chars = Counter()
        self.empty_values = Counter()
        self.duplicates = []

    def tag(self, kind, text):
        if isinstance(text, str):
            self.tags_removed[kind] += len(TAG.findall(text))


def clean(text):
    """서식 태그 제거, 공백·빈 줄 정리. 문자열이 아니면 빈 문자열."""
    if not isinstance(text, str):
        return ""
    text = TAG.sub("", text)
    lines = [SPACES.sub(" ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def value_or_none(value):
    """빈 값과 '없음'은 None (메타데이터용)."""
    if value is None:
        return None
    value = str(value).strip()
    return None if value in ("", "없음") else value


def show(value):
    """본문용: None이면 '정보 없음'."""
    return value if value else NO_INFO


def rarity_text(r):
    return f"{r}성" if isinstance(r, int) else value_or_none(r)


def _doc(kind, key, title, lines, meta):
    text = "\n".join(line for line in lines if line)
    return {"doc_id": f"{kind}:{key}", "kind": kind, "title": title, "text": text,
            "metadata": {"kind": kind, **meta, "source": f"genshin-db {DATA_COMMIT}"}}


# ── 종류별 문서 만들기 ─────────────────────────────────────────
def character_doc(key, d, stats):
    element, region = value_or_none(d.get("elementText")), value_or_none(d.get("region"))
    for f in ("elementText", "region", "affiliation", "title"):
        if not value_or_none(d.get(f)):
            stats.empty_values[f"character.{f}"] += 1
    meta = {"name": d["name"], "element": element, "weapon": value_or_none(d.get("weaponText")),
            "rarity": rarity_text(d.get("rarity")), "region": region}
    lines = [
        d["name"] + (f" ({value_or_none(d.get('title'))})" if value_or_none(d.get("title")) else ""),
        f"원소: {show(element)} / 무기: {show(meta['weapon'])} / 성급: {show(meta['rarity'])} / 지역: {show(region)}",
        f"소속: {show(value_or_none(d.get('affiliation')))} / 운명의 자리: {show(value_or_none(d.get('constellation')))}",
        f"돌파 스탯: {show(value_or_none(d.get('substatText')))} / 생일: {show(value_or_none(d.get('birthday')))}",
        clean(d.get("description")),
    ]
    return _doc("character", key, d["name"], lines, meta)


def talent_docs(key, d, owner, stats):
    docs = []
    for slot, label in SLOT_NAMES.items():
        part = d.get(slot)
        if not part:
            continue
        stats.tag("talent", part.get("descriptionRaw"))
        desc = clean(part.get("description") or part.get("descriptionRaw"))
        meta = {"name": owner, "slot": label, "skill_name": clean(part.get("name"))}
        docs.append(_doc("talent", f"{key}:{slot}", f"{owner} {label}: {meta['skill_name']}",
                         [f"{owner} {label}: {meta['skill_name']}", desc], meta))
    return docs


def constellation_doc(key, d, owner, stats):
    lines = [f"{owner} 명의 자리"]
    for n in range(1, 7):
        part = d.get(f"c{n}")
        if part:
            stats.tag("constellation", part.get("descriptionRaw"))
            lines.append(f"{n}돌파 {clean(part.get('name'))}: {clean(part.get('description') or part.get('descriptionRaw'))}")
    return _doc("constellation", key, f"{owner} 명의 자리", lines, {"name": owner})


def weapon_doc(key, d, stats):
    stats.tag("weapon", d.get("effectTemplateRaw"))
    r1 = clean((d.get("r1") or {}).get("description"))
    meta = {"name": d["name"], "weapon": value_or_none(d.get("weaponText")), "rarity": rarity_text(d.get("rarity")),
            "main_stat": value_or_none(d.get("mainStatText"))}
    main = f"{meta['main_stat']} {d.get('baseStatText') or ''}".strip() if meta["main_stat"] else NO_INFO
    lines = [
        f"{d['name']} ({show(meta['rarity'])} {show(meta['weapon'])})",
        f"기초 공격력: {round(d['baseAtkValue']) if d.get('baseAtkValue') else NO_INFO} / 주옵션: {main}",
        f"효과 「{clean(d.get('effectName'))}」(1재련): {r1}" if d.get("effectName") else "",
        clean(d.get("description")),
    ]
    return _doc("weapon", key, d["name"], lines, meta)


def artifact_doc(key, d, stats):
    rarities = d.get("rarityList") or []
    meta = {"name": d["name"], "rarity": "/".join(f"{r}성" for r in rarities) or None}
    lines = [f"{d['name']} (성유물 세트, {show(meta['rarity'])})"]
    for n in ("1", "2", "4"):
        effect = clean(d.get(f"effect{n}Pc"))
        if effect:
            lines.append(f"{n}세트 효과: {effect}")
    pieces = [f"{label} {clean(d[slot]['name'])}" for slot, label in PIECES if d.get(slot)]
    if pieces:
        lines.append("부위: " + " / ".join(pieces))
    return _doc("artifact", key, d["name"], lines, meta)


def patch_docs(records):
    """패치 변경 기록 -> 문서. 본문 형식은 collector와 같다."""
    sys.path.insert(0, str(ROOT))
    from collector.patchnotes.documents import make_document_text   # noqa: E402
    docs = []
    for r in records:
        meta = {"name": r["entity_name"], "version": r["version"], "folder": r["folder"],
                "change_type": r["change_type"]}
        docs.append({"doc_id": f"patch:{r['version']}:{r['folder']}:{r['entity_id']}", "kind": "patch",
                     "title": f"{r['version']} {r['entity_name']}", "text": make_document_text(r),
                     "metadata": {"kind": "patch", **meta, "source": f"genshin-db {r.get('data_commit', '')}".strip()}})
    return docs


# ── 전체 만들기 ──────────────────────────────────────────────
def _load_folder(base, folder, stats):
    items = {}
    for path in sorted((base / folder).glob("*.json")):
        text = path.read_text(encoding="utf-8")
        stats.raw_files[folder] += 1
        stats.raw_chars[folder] += len(text)
        data = json.loads(text)
        for field in ("costs", "cv", "story", "descriptionRaw", "effectTemplateRaw"):
            if field in data:
                stats.excluded_chars[field] += len(json.dumps(data[field], ensure_ascii=False))
        for slot in ("flower", "plume", "sands", "goblet", "circlet"):
            if isinstance(data.get(slot), dict) and "story" in data[slot]:
                stats.excluded_chars["story"] += len(data[slot]["story"])
        items[path.stem] = data
    return items


def build_documents(genshin_db, patches_path=ROOT / "data" / "patch_changes.json"):
    """genshin-db 저장소 경로 -> (문서 목록, Stats)."""
    base = Path(genshin_db) / "src" / "data" / "Korean"
    if not base.is_dir():
        raise FileNotFoundError(f"{base} 가 없습니다. 먼저 'python3 -m core.documents --fetch'로 원본을 받으세요.")
    stats = Stats()
    raw = {f: _load_folder(base, f, stats) for f in FOLDERS}
    owner = {k: d["name"] for k, d in raw["characters"].items()}

    docs = []
    for key, d in raw["characters"].items():
        stats.tag("character", d.get("description"))
        docs.append(character_doc(key, d, stats))
    for key, d in raw["talents"].items():
        docs += talent_docs(key, d, owner.get(key, d.get("name", key)), stats)
    for key, d in raw["constellations"].items():
        docs.append(constellation_doc(key, d, owner.get(key, d.get("name", key)), stats))
    for key, d in raw["weapons"].items():
        docs.append(weapon_doc(key, d, stats))
    for key, d in raw["artifacts"].items():
        docs.append(artifact_doc(key, d, stats))
    if Path(patches_path).exists():
        records = json.loads(Path(patches_path).read_text(encoding="utf-8"))
        stats.raw_files["patch_changes"] += len(records)
        docs += patch_docs(records)

    unique, seen = [], {}
    for doc in docs:                                  # 규칙 6: 같은 종류·같은 본문은 하나만
        h = hashlib.sha1((doc["kind"] + "\n" + doc["text"]).encode("utf-8")).hexdigest()
        if h in seen:
            stats.duplicates.append((doc["doc_id"], seen[h]))
            continue
        seen[h] = doc["doc_id"]
        unique.append(doc)
    return unique, stats, raw


# ── 전처리 전후 비교표 ─────────────────────────────────────────
def _pick_examples(raw, docs):
    """비교표 예시: 서식 태그가 있는 스킬 1개, 자리표시자가 있는 무기 1개, 빈 값이 있는 캐릭터 1개."""
    by_id = {d["doc_id"]: d["text"] for d in docs}
    examples = []
    for key, d in raw["talents"].items():
        slot = next((s for s in SLOT_NAMES if TAG.search((d.get(s) or {}).get("descriptionRaw") or "")), None)
        if slot and f"talent:{key}:{slot}" in by_id:
            examples.append(("스킬 (서식 태그)", d[slot]["descriptionRaw"][:400], by_id[f"talent:{key}:{slot}"][:400]))
            break
    for key, d in raw["weapons"].items():
        if "{0}" in (d.get("effectTemplateRaw") or "") and f"weapon:{key}" in by_id:
            examples.append(("무기 효과 (자리표시자)", d["effectTemplateRaw"], by_id[f"weapon:{key}"]))
            break
    for key, d in raw["characters"].items():
        if not value_or_none(d.get("elementText")) or not value_or_none(d.get("region")):
            before = {k: d.get(k) for k in ("name", "title", "elementText", "region", "elementType")}
            if "cv" in d:
                before["cv"] = "(성우 이름 4개 언어, 생략)"
            examples.append(("캐릭터 (빈 값·내부 코드·성우)", json.dumps(before, ensure_ascii=False),
                             by_id[f"character:{key}"]))
            break
    return examples


def make_report(docs, stats, raw):
    kinds = Counter(d["kind"] for d in docs)
    lengths = {}
    for d in docs:
        lengths.setdefault(d["kind"], []).append(len(d["text"]))
    lines = ["# 문서 전처리 전후 비교표", "",
             f"genshin-db 한국어 데이터 커밋 `{DATA_COMMIT}` (7.1) + 패치 변경 기록 → `data/docs/documents_ko.jsonl`",
             "만드는 코드: `core/documents.py` (`python3 -m core.documents`)", "",
             "## 1. 전체 요약", "",
             "| 종류 | 원본 | 문서 | 문서 평균 길이(자) | 최대 길이(자) |", "| --- | --- | --- | --- | --- |"]
    origin = {"character": ("characters", "파일"), "talent": ("talents", "파일(스킬 6~7개씩)"),
              "constellation": ("constellations", "파일"), "weapon": ("weapons", "파일"),
              "artifact": ("artifacts", "파일"), "patch": ("patch_changes", "기록")}
    for kind in ("character", "talent", "constellation", "weapon", "artifact", "patch"):
        folder, unit = origin[kind]
        ls = lengths.get(kind, [0])
        lines.append(f"| {kind} | {stats.raw_files[folder]} {unit} | {kinds[kind]} | {sum(ls) // len(ls)} | {max(ls)} |")
    raw_total = sum(stats.raw_chars.values())
    doc_total = sum(len(d["text"]) for d in docs)
    lines += [f"| **합계** | 원본 JSON {raw_total:,}자 | **{len(docs)}** | 본문 합계 {doc_total:,}자 | |", "",
              "## 2. 정제 항목", "",
              "| 규칙 | 전 | 후 |", "| --- | --- | --- |",
              f"| 서식 태그 제거 | 태그 {sum(stats.tags_removed.values()):,}개 (스킬 {stats.tags_removed['talent']:,}, "
              f"명의 자리 {stats.tags_removed['constellation']:,}, 무기 템플릿 {stats.tags_removed['weapon']:,}) | 0개 |",
              f"| 빈 값·'없음' 통일 | 지역 빈칸 {stats.empty_values['character.region']}명, 원소 '없음' "
              f"{stats.empty_values['character.elementText']}명, 칭호 빈칸 {stats.empty_values['character.title']}명, "
              f"소속 빈칸 {stats.empty_values['character.affiliation']}명 | 본문 '정보 없음', 메타데이터 null |",
              f"| 같은 본문 문서 제거 | {len(docs) + len(stats.duplicates)}개 | {len(docs)}개 "
              f"(제거 {len(stats.duplicates)}개: {', '.join(a for a, _ in stats.duplicates[:5]) or '-'}) |", "",
              "## 3. 제외한 필드", "",
              "| 필드 | 이유 | 원본에서 차지한 분량(자) |", "| --- | --- | --- |"]
    for field, reason in EXCLUDED_FIELDS.items():
        amount = stats.excluded_chars.get(field.split(" ")[0])
        lines.append(f"| `{field}` | {reason} | {f'{amount:,}' if amount else '-'} |")

    lines += ["", "## 4. 예시 (전 → 후)", ""]
    for title, before, after in _pick_examples(raw, docs):
        lines += [f"### {title}", "", "전:", "```", before, "```", "후:", "```", after, "```", ""]
    lines += ["## 5. 개인정보", "",
              "게임 데이터라 이용자 개인정보는 없다. 실존 인물 정보인 성우 이름(`cv`)은 서비스에 필요 없어 제외했다.", ""]
    return "\n".join(lines)


def write_outputs(docs, report, out_dir=OUT_DIR):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "documents_ko.jsonl", "w", encoding="utf-8") as f:
        for doc in docs:
            f.write(json.dumps(doc, ensure_ascii=False) + "\n")
    (out_dir / "preprocess_report.md").write_text(report, encoding="utf-8")
    return out_dir


def fetch_genshin_db(dest=DEFAULT_GENSHIN_DB, commit=DATA_COMMIT):
    """genshin-db에서 필요한 폴더만 받는다 (sparse checkout, 수 MB)."""
    dest = Path(dest)
    if not (dest / ".git").exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", "-q", "--filter=blob:none", "--no-checkout",
                        "https://github.com/theBowja/genshin-db.git", str(dest)], check=True)
    patterns = [f"src/data/Korean/{f}/*" for f in FOLDERS]
    subprocess.run(["git", "-C", str(dest), "sparse-checkout", "set", "--no-cone", *patterns], check=True)
    subprocess.run(["git", "-C", str(dest), "checkout", "-q", commit], check=True)
    return dest


def main(argv=None):
    parser = argparse.ArgumentParser(description="genshin-db 원본 -> RAG 문서 + 전처리 전후 비교표")
    parser.add_argument("--genshin-db", default=str(DEFAULT_GENSHIN_DB), help="genshin-db 저장소 경로")
    parser.add_argument("--out", default=str(OUT_DIR), help="결과 폴더 (기본 data/docs)")
    parser.add_argument("--fetch", action="store_true", help="원본을 받은 뒤 만들기")
    args = parser.parse_args(argv)
    if args.fetch:
        fetch_genshin_db(args.genshin_db)
    docs, stats, raw = build_documents(args.genshin_db)
    out = write_outputs(docs, make_report(docs, stats, raw), args.out)
    kinds = Counter(d["kind"] for d in docs)
    print(f"문서 {len(docs)}개 -> {out}/documents_ko.jsonl  ({', '.join(f'{k} {v}' for k, v in kinds.items())})")
    print(f"전처리 전후 비교표 -> {out}/preprocess_report.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
