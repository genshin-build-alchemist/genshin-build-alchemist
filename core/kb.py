"""데이터(지식 베이스) 불러오기. 파일 위치는 data/ 폴더 기준.

- characters_ko.json : 캐릭터 124명의 원소·무기·성급·지역 (FR-01)
- items_ko.json      : 무기 255개, 성유물 63세트 (FR-02)
- patch_changes.json : 버전별 변경 기록 (FR-03·04, collector/가 만든다)
- build_cards/*.json : 팀이 작성하는 빌드 카드 (FR-06). 이름이 _ 로 시작하는 파일은 양식이라 건너뛴다
"""
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

SLOT_LABELS = {"combat1": "일반 공격", "combat2": "원소 스킬", "combat3": "원소 폭발"}


def version_key(version):
    """'7.0' -> (7, 0). 버전 비교용."""
    return tuple(int(x) for x in str(version).split("."))


def slot_label(field_path):
    """변경 필드 경로 -> 사람이 읽는 부분 이름. 예: 'passive1/description' -> '고유 특성 1'."""
    head = field_path.split("/")[0].split("[")[0]
    if head in SLOT_LABELS:
        return SLOT_LABELS[head]
    m = re.fullmatch(r"passive(\d+)", head)
    if m:
        return f"고유 특성 {m.group(1)}"
    m = re.fullmatch(r"c(\d+)", head)
    if m:
        return f"명의 자리 {m.group(1)}"
    m = re.fullmatch(r"r(\d+)", head)
    if m:
        return f"재련 {m.group(1)}단계"
    return None


def _read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@dataclass
class KnowledgeBase:
    characters: list
    weapons: list
    artifacts: list
    patches: list
    build_cards: list = field(default_factory=list)
    data_version: str = ""

    def __post_init__(self):
        self.char_by_name = {c["name"]: c for c in self.characters}
        self.weapon_by_name = {}
        for w in self.weapons:
            self.weapon_by_name.setdefault(w["name"], w)
        self.artifact_by_name = {a["name"]: a for a in self.artifacts}
        self.card_by_character = {c["character"]: c for c in self.build_cards}
        self.versions = sorted({p["version"] for p in self.patches}, key=version_key)

    @property
    def latest_version(self):
        return self.versions[-1] if self.versions else None


def load_build_cards(folder):
    cards = []
    for path in sorted(Path(folder).glob("*.json")):
        if path.name.startswith("_"):
            continue
        card = _read_json(path)
        card["_file"] = path.name
        cards.append(card)
    return cards


def load_kb(data_dir=DATA_DIR, build_card_dir=None):
    data_dir = Path(data_dir)
    chars = _read_json(data_dir / "characters_ko.json")
    items = _read_json(data_dir / "items_ko.json")
    patches = _read_json(data_dir / "patch_changes.json")
    cards = load_build_cards(build_card_dir or data_dir / "build_cards")
    return KnowledgeBase(
        characters=chars["characters"], weapons=items["weapons"], artifacts=items["artifacts"],
        patches=patches, build_cards=cards, data_version=chars.get("commit", ""),
    )
