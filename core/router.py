"""조건부 워크플로: 질문을 보고 처리 경로를 고른다 (FR-W1).

경로 5개 (판별 순서대로)
  patch   : 버전 또는 '패치·바뀐·변경·신규' 같은 말이 있음      -> 패치 변경 기록 검색
  build   : '추천·빌드·성유물·세팅' 같은 말 + 캐릭터 이름        -> 빌드 카드 검색
  lookup  : 캐릭터 이름이 있음                                  -> 그 캐릭터 문서 1개
  filter  : '불 원소', '5성', '몬드 출신' 같은 조건이 있음        -> 조건으로 여러 캐릭터 검색
  unknown : 위 어디에도 해당하지 않음                            -> 근거 없음 (지어내지 않기)

규칙 기반이라 빠르고 결과를 설명할 수 있다. 나중에 LLM 분류기로 바꿔도
route() 의 반환 형식(RouteResult)만 지키면 나머지 코드는 그대로 쓴다.
"""
import re
from dataclasses import dataclass, field

ROUTES = ("patch", "build", "lookup", "filter", "unknown")

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


@dataclass
class RouteResult:
    route: str
    character: str = None                       # 질문에 나온 캐릭터 이름
    conditions: dict = field(default_factory=dict)   # filter 조건 {항목: 값}
    version: str = None                         # patch 질문의 버전
    asked_field: str = None                     # lookup에서 물은 항목 (없으면 전체)


class Router:
    def __init__(self, kb):
        self.kb = kb
        names = sorted(kb.char_by_name, key=len, reverse=True)   # 긴 이름부터 (예: '여행자 (얼음 원소)')
        self.name_patterns = [(n, re.compile(r"(?:^|[\s\"'“‘(])" + re.escape(n) + NAME_END)) for n in names]
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

    def find_character(self, text):
        for name, pattern in self.name_patterns:
            if pattern.search(text):
                return name
        return None

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
            return RouteResult("patch", character=character, version=version)
        if any(w in text for w in BUILD_WORDS):
            return RouteResult("build" if character else "unknown", character=character)
        if character:
            return RouteResult("lookup", character=character, asked_field=self.find_field(text))
        conditions = self.find_conditions(text)
        if conditions:
            return RouteResult("filter", conditions=conditions)
        return RouteResult("unknown")
