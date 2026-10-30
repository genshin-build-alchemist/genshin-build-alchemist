"""빌드 카드 검사 (FR-06).

1) 이름 검사: 카드에 적은 캐릭터·무기·성유물 이름이 genshin-db 데이터에 실제로 있는지,
   무기 종류가 캐릭터가 쓰는 무기와 맞는지 확인한다. (오타, 없는 아이템 잡기)
2) 재확인 판정: 카드를 확인한 버전(checked_version) 이후 패치에서
   그 캐릭터나 추천 무기가 바뀌었으면 '재확인 필요'로 표시한다.

실행: python -m core.validate            (data/build_cards 전체 검사)
      python -m core.validate 폴더경로
"""
import re
import sys

from core.kb import load_build_cards, load_kb, slot_label, version_key

REQUIRED = ("character", "weapons", "artifact_sets", "checked_version", "source_url")
MAIN_STAT_SLOTS = ("sands", "goblet", "circlet")


def eun(word):
    """받침에 맞춰 '은/는'을 붙인다. 예: 알베도 -> 알베도는, 사유 -> 사유는, 진 -> 진은"""
    ch = word[-1]
    has_batchim = "가" <= ch <= "힣" and (ord(ch) - ord("가")) % 28 != 0
    return word + ("은" if has_batchim else "는")


def validate_card(card, kb):
    """문제 목록(문자열)을 돌려준다. 빈 목록이면 통과."""
    problems = []
    for key in REQUIRED:
        if not card.get(key):
            problems.append(f"'{key}' 칸이 비어 있음")
    name = card.get("character")
    char = kb.char_by_name.get(name)
    if name and not char:
        problems.append(f"캐릭터 이름이 데이터에 없음: {name}")
    for w in card.get("weapons") or []:
        info = kb.weapon_by_name.get(w)
        if not info:
            problems.append(f"무기 이름이 데이터에 없음: {w}")
        elif char and char["weapon"] and info["weapon"] != char["weapon"]:
            problems.append(f"무기 종류가 맞지 않음: {w}({info['weapon']}) / {eun(name)} {char['weapon']} 사용")
    for a in card.get("artifact_sets") or []:
        if a not in kb.artifact_by_name:
            problems.append(f"성유물 세트 이름이 데이터에 없음: {a}")
    version = card.get("checked_version")
    if version and not re.fullmatch(r"\d+\.\d+", str(version)):
        problems.append(f"확인 버전 형식이 이상함: {version} (예: 7.1)")
    for slot in card.get("main_stats") or {}:
        if slot not in MAIN_STAT_SLOTS:
            problems.append(f"주옵션 칸 이름이 이상함: {slot} (sands / goblet / circlet 중 하나)")
    return problems


def recheck_reasons(card, kb):
    """확인 버전 이후 바뀐 항목 목록. [{'version', 'target', 'parts'}]. 빈 목록이면 재확인 필요 없음."""
    try:
        checked = version_key(card["checked_version"])
    except (KeyError, ValueError):
        return []
    character = card.get("character")
    weapons = set(card.get("weapons") or [])
    reasons = []
    for r in kb.patches:
        if version_key(r["version"]) <= checked or r["change_type"] == "added":
            continue
        is_char = r["entity_name"] == character and r["folder"] in ("characters", "talents", "constellations")
        is_weapon = r["entity_name"] in weapons and r["folder"] == "weapons"
        if not (is_char or is_weapon):
            continue
        parts = sorted({slot_label(c["field"]) for c in r["changes"]} - {None})
        reasons.append({"version": r["version"], "target": r["entity_name"],
                        "parts": parts or ["기타"]})
    return reasons


def main(folder=None):
    kb = load_kb()
    cards = load_build_cards(folder) if folder else kb.build_cards
    if not cards:
        print("검사할 빌드 카드가 없습니다. data/build_cards/_template.json 을 복사해서 작성하세요.")
        return 0
    bad = 0
    for card in cards:
        problems = validate_card(card, kb)
        reasons = recheck_reasons(card, kb)
        status = "문제 있음" if problems else ("재확인 필요" if reasons else "통과")
        print(f"[{status}] {card.get('_file', '?')} ({card.get('character')})")
        for p in problems:
            print(f"    - {p}")
        for r in reasons:
            print(f"    - {r['version']}에서 {r['target']} 변경: {', '.join(r['parts'])}")
        bad += bool(problems)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else None))
