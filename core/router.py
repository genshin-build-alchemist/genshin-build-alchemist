"""조건부 워크플로: 질문을 보고 처리 경로를 고른다 (FR-W1).

경로 6개 (판별 순서대로)
  patch   : 버전 또는 '패치·바뀐·변경·신규' 같은 말이 있음      -> 패치 변경 기록 검색
  build   : '추천·빌드·성유물·세팅' 같은 말 + 캐릭터 이름        -> 빌드 카드 검색
  lookup  : 캐릭터 이름이 있음                                  -> 그 캐릭터 문서 1개
  item    : 무기·성유물 이름이 있음                             -> 그 문서 1개
  filter  : '불 원소', '5성', '몬드 출신' 같은 조건이 있음        -> 조건으로 여러 캐릭터 검색
  item    : 이름은 없지만 '무기·성유물·창·활' 같은 말이 있음     -> 벡터 검색 (core/vector.py)
  unknown : 위 어디에도 해당하지 않음                            -> 근거 없음 (지어내지 않기)
  ('캐릭터'라는 말이 있으면 조건 질문으로 본다: "활을 쓰는 4성 캐릭터" = filter)

규칙 기반이라 빠르고 결과를 설명할 수 있다. 나중에 LLM 분류기로 바꿔도
route() 의 반환 형식(RouteResult)만 지키면 나머지 코드는 그대로 쓴다.
"""
import re
from dataclasses import dataclass, field

ROUTES = ("patch", "build", "lookup", "item", "filter", "unknown")

PATCH_WORDS = ("패치", "바뀐", "바뀌", "변경", "신규", "새로 나온", "새로 추가", "추가된", "상향", "하향", "너프", "버프")
BUILD_WORDS = ("추천", "빌드", "성유물", "세팅", "육성", "주옵", "부옵", "주스탯", "부스탯")

# lookup 질문에서 무엇을 물었는지
FIELD_WORDS = {
    "element": ("원소", "속성"),
    "weapon": ("무기",),
    "rarity": ("몇 성", "몇성", "성급", "등급", "레어"),
    "region": ("지역", "출신", "나라", "어디"),
}

# 이름 앞은 문장 시작/공백/따옴표, 뒤는 조사·공백·문장부호일 때만 이름으로 본다.
# (한 글자 이름 '소', '진'이 '원소', '진짜' 같은 단어 안에서 잡히지 않게)
NAME_END = r"(?=$|[\s?!.,\"'”’)]|의|은|는|이|가|을|를|도|랑|와|과|한테|에게|에서|추천|빌드)"
WORD_END = r"(?=$|[\s?!.,\"'”’)]|의|은|는|이|가|을|를|도|에서|출신|지역|캐릭터|쓰는|사용)"
VERSION_RE = re.compile(r"(?<![\d.])(\d+\.\d+)(?![\d.])")

# patch 질문에서 무엇의 변경을 물었는지 (patch_changes.json의 folder). 앞에서부터 먼저 맞는 것
PATCH_FOLDER_WORDS = (
    ("constellations", ("별자리", "명의 자리", "운명의 자리", "명좌")),
    ("talents", ("스킬", "특성", "재능", "일반 공격", "원소 폭발")),
    ("weapons", ("무기",)),
    ("characters", ("캐릭터", "신캐")),
)
ADDED_WORDS = ("신규", "새로", "추가", "신캐", "출시")

# item 질문 낱말: 이름이 없어도 무기·성유물을 묻는 말. 한 글자 낱말(창, 검, 활)은 앞뒤가 한글이 아닐 때만
# ('창고', '검색', '활동' 같은 단어 안에서 잡히지 않게)
ITEM_WORDS_RE = re.compile(r"무기|성유물|재련|[24]세트|세트 효과|장병기|한손검|양손검|대검|법구|"
                           r"(?<![가-힣])(?:창|검|활)(?=$|[\s?!.,]|은|는|이|가|을|를|도|으로|로|중|좀|추천|뭐)")
# '카덴로우는 어떤 무기를 써?'는 아이템이 아니라 캐릭터(모르는 이름)의 무기를 묻는 질문 -> item으로 보내지 않는다
CHARACTER_WEAPON_RE = re.compile(r"무기\s?(를|는|가)?\s?(뭐\s?)?(써|쓰|사용)")
# 이름 없는 추천 질문('성유물 추천해줘')은 누구에게 맞는지 몰라 답할 근거가 없다 -> unknown (빌드 카드는 캐릭터별)
RECOMMEND_WORDS = tuple(w for w in BUILD_WORDS if w != "성유물")


@dataclass
class RouteResult:
    route: str
    character: str = None                       # 질문에 나온 캐릭터 이름
    conditions: dict = field(default_factory=dict)   # filter 조건 {항목: 값}
    version: str = None                         # patch 질문의 버전
    asked_field: str = None                     # lookup에서 물은 항목 (없으면 전체)
    patch_folder: str = None                    # patch 질문에서 물은 종류 (characters/weapons/talents/constellations)
    patch_added: bool = False                   # patch 질문이 '신규·추가'를 물었는지
    item: str = None                            # item 질문에 나온 무기·성유물 이름 (없으면 벡터 검색)
    item_kind: str = None                       # 'weapon' / 'artifact'
    question: str = ""                          # 질문 원문 (item 벡터 검색에 쓴다)


class Router:
    def __init__(self, kb):
        self.kb = kb
        names = sorted(kb.char_by_name, key=len, reverse=True)   # 긴 이름부터 (예: '여행자 (얼음 원소)')
        self.name_patterns = [(n, re.compile(r"(?:^|[\s\"'“‘(])" + re.escape(n) + NAME_END)) for n in names]
        items = [(n, "weapon") for n in kb.weapon_by_name] + [(n, "artifact") for n in kb.artifact_by_name]
        items.sort(key=lambda x: len(x[0]), reverse=True)              # 긴 이름부터 ('페보니우스 검' > '검')
        self.item_patterns = [(n, k, re.compile(r"(?:^|[\s\"'“‘(「])" + re.escape(n) + NAME_END)) for n, k in items]
        self.condition_patterns = []
        for f in ("region", "weapon", "rarity", "element"):
            for value in sorted({c[f] for c in kb.characters if c[f]}):
                self.condition_patterns.append((f, value, self._condition_pattern(f, value)))

    @staticmethod
    def _condition_pattern(field_name, value):
        v = re.escape(value)
        if field_name == "element":            # '불 원소', '불원소', '불 속성'
            return re.compile(r"(?<![가-힣])" + v + r"\s?(원소|속성)")
        if field_name == "rarity":             # '5성', '5성급'
            return re.compile(r"(?<!\d)" + re.escape(value[0]) + r"\s?성")
        return re.compile(r"(?<![가-힣])" + v + WORD_END)

    # TODO(A) rag_v5: 이름·낱말 인식 개선. 확인: python3 -m core.route_check data/eval/style_questions_dev.csv
    #  [ ] 띄어쓰기 없는 질문 ('알하이탐몇성임'): 지금 0%
    #  [ ] 줄임 이름·별명 ('카즈하', '이토', '헤이조'): 별명 표를 만들어 정식 이름으로 바꾸기
    #  [ ] 무기 종류 동의어 ('창' -> 장병기, '대검' -> 양손검, '카탈리스트' -> 법구): 지금 '창 쓰는 5성 캐릭터'가 무기 조건을 놓침
    #  평가용(style_questions_v1.csv)은 고친 뒤 한 번만 확인한다
    def find_character(self, text):
        for name, pattern in self.name_patterns:
            if pattern.search(text):
                return name
        return None

    def find_item(self, text):
        """무기·성유물 이름 -> (이름, 'weapon'/'artifact'). 없으면 (None, None)."""
        for name, kind, pattern in self.item_patterns:
            if pattern.search(text):
                return name, kind
        return None, None

    def find_conditions(self, text):
        return {f: v for f, v, p in self.condition_patterns if p.search(text)}

    @staticmethod
    def find_field(text):
        for f, words in FIELD_WORDS.items():
            if any(w in text for w in words):
                return f
        return None

    def route(self, text):
        text = text.strip()
        character = self.find_character(text)
        m = VERSION_RE.search(text)
        version = m.group(1) if m else None

        if version or any(w in text for w in PATCH_WORDS):
            folder = next((f for f, words in PATCH_FOLDER_WORDS if any(w in text for w in words)), None)
            return RouteResult("patch", character=character, version=version, patch_folder=folder,
                               patch_added=any(w in text for w in ADDED_WORDS))
        if character:
            if any(w in text for w in BUILD_WORDS):
                return RouteResult("build", character=character)
            return RouteResult("lookup", character=character, asked_field=self.find_field(text))
        item, item_kind = self.find_item(text)
        if item:
            return RouteResult("item", item=item, item_kind=item_kind, question=text)
        if any(w in text for w in RECOMMEND_WORDS) or ("성유물" in text and "추천" in text):
            return RouteResult("unknown")
        conditions = self.find_conditions(text)
        item_words = bool(ITEM_WORDS_RE.search(text)) and not CHARACTER_WEAPON_RE.search(text)
        if conditions and ("캐릭터" in text or not item_words):
            return RouteResult("filter", conditions=conditions)
        if item_words:
            return RouteResult("item", question=text)
        return RouteResult("unknown")
