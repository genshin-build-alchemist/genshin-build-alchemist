
"""동의어·줄임 이름 표 (rag_v5). 라우터가 질문을 판별할 때 정식 이름으로 바꿔 읽는다.

캐릭터
  - 성 + 이름 꼴(이나즈마 캐릭터 등)은 이름만 불러도 알아듣는다: '카즈하' -> '카에데하라 카즈하' (자동)
  - 자동으로 못 만드는 별명은 CHARACTER_ALIASES에 직접 적는다: '라이덴' -> '라이덴 쇼군'
  - 같은 줄임 이름이 두 캐릭터에 걸리면(예: '카미사토' = 아야카/아야토) 쓰지 않는다
아이템 (무기·성유물, rag_v5)
  - 줄임 이름은 ITEM_ALIASES에 직접 적는다: '회광' -> '안개를 가르는 회광' (담당: 한동우)
  - 한 별명은 아이템 하나만: '천공'처럼 여러 개(천공의 검·날·활 ...)에 걸리는 말은 넣지 않는다
  - 정식 이름이 데이터(data/items_ko.json)에 없거나, 캐릭터 이름·별명과 겹치면 테스트가 실패한다 (tests/test_rag_v5.py)
조건 (filter)
  - 무기 종류 동의어: '창' -> 장병기, '대검' -> 양손검, '카탈리스트' -> 법구
  - 성급·원소·지역은 표기 차이가 거의 없어서 아직 표가 없다

추가 방법: 아래 표에 한 줄 넣고 python3 -m core.route_check data/eval/style_questions_dev.csv 로 확인한다.
평가용(style_questions_v1.csv)은 고친 뒤 한 번만 확인한다.
"""

# 별명 -> 정식 이름 (data/characters_ko.json의 name). 자동 규칙(성 + 이름)으로 안 되는 것만
CHARACTER_ALIASES = {
    "라이덴": "라이덴 쇼군",
    "야에": "야에 미코",
}

# 아이템 별명 -> 정식 이름 (무기·성유물 data/items_ko.json의 name). 무기 '종류' 동의어는 아래 CONDITION_ALIASES
ITEM_ALIASES = {
    # 무기
    "매검": "매의 검",
    "천공검": "천공의 검",
    "회광": "안개를 가르는 회광",
    "페보검": "페보니우스 검",
    "용포": "용의 포효",
    "늑말": "늑대의 말로",
    "송뢰": "송뢰가 울릴 무렵",
    "휴지": "천공의 두루마리",
    "사풍": "사풍 원서",
    "호마창": "호마의 지팡이",
    "호마봉": "호마의 지팡이",
    "천날": "천공의 날개",
    "예초": "예초의 번개",
    "예초기": "예초의 번개",
    "비뢰": "비뢰의 고동",

    # 성유물
    "절연": "절연의 기치",
    "시메": "추억의 시메나와",
    "청록": "청록색 그림자",
    "악단": "대지를 유랑하는 악단",
    "검투": "검투사의 피날레",
    "소녀": "사랑받는 소녀",
    "마녀": "불타오르는 화염의 마녀",
    "번분": "번개 같은 분노",
    "왕실": "옛 왕실의 의식",
    "천암": "견고한 천암",
}

# 줄임 이름이 다른 뜻으로 더 자주 쓰여서 자동 별명에서 빼는 낱말
ALIAS_STOPWORDS = set()

# 조건 값 동의어 {항목: {동의어: 정식 값}}
CONDITION_ALIASES = {
    "weapon": {
        "창": "장병기",
        "대검": "양손검",
        "카탈리스트": "법구",
        "카탈": "법구",
        "한손": "한손검",
    },
}


def character_aliases(names):
    """정식 이름 목록 -> {별명: 정식 이름}. 정식 이름과 같은 별명, 두 캐릭터에 걸리는 별명은 뺀다."""
    names = set(names)
    candidates = {}
    for name in names:
        parts = name.split()
        if len(parts) == 2 and "(" not in name:
            candidates.setdefault(parts[1], set()).add(name)
    out = {alias: next(iter(full)) for alias, full in candidates.items()
           if len(full) == 1 and alias not in names and alias not in ALIAS_STOPWORDS and len(alias) >= 2}
    for alias, full in CHARACTER_ALIASES.items():
        if full in names and alias not in names:
            out[alias] = full
    return out


def item_aliases(weapon_names, artifact_names, exclude=()):
    """ITEM_ALIASES -> {별명: (정식 이름, 'weapon'/'artifact')}. 데이터에 없는 이름, 정식 이름과 같은 별명,
    exclude(캐릭터 이름·별명)와 겹치는 별명은 뺀다. 빠진 것은 tests/test_rag_v5.py가 잡는다."""
    weapons, artifacts, exclude = set(weapon_names), set(artifact_names), set(exclude)
    out = {}
    for alias, full in ITEM_ALIASES.items():
        if alias in weapons or alias in artifacts or alias in exclude:
            continue
        if full in weapons:
            out[alias] = (full, "weapon")
        elif full in artifacts:
            out[alias] = (full, "artifact")
    return out
