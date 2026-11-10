"""변경 기록에서 '내용은 그대로이고 표기만 바뀐' 변경(잡음)을 걸러 낸다.

genshin-db는 버전마다 데이터 형식을 고치기도 해서, 그대로 두면 패치 내용과 무관한 기록이 섞인다.
예) 5.6에서 일반 공격 이름 102개가 '일반 공격·페보니우스 검술·백' -> '페보니우스 검술·백'으로 바뀜 (내용 변경 아님)

규칙은 변경(field 1개) 단위로 적용하고, 수정 기록에 남은 변경이 하나도 없으면 그 기록을 뺀다.
신규(added)·삭제(removed) 기록은 그대로 둔다.
"""
from collections import Counter

NORMAL_ATTACK_PREFIX = "일반 공격·"
EMPTY_LIKE = {None, "", "NaN", "0%"}


def _is_name_prefix_change(c):
    """'일반 공격·XX' <-> 'XX' 처럼 앞말만 붙거나 빠진 이름."""
    old, new = c["before"], c["after"]
    if not (c["field"].endswith("/name") and isinstance(old, str) and isinstance(new, str)):
        return False
    return old.removeprefix(NORMAL_ATTACK_PREFIX) == new.removeprefix(NORMAL_ATTACK_PREFIX)


def _is_label_rename(c):
    """수치 표 항목 이름의 글자만 바뀜 (예: '기본 피해 증가' -> '기존 피해 증가').
    항목이 새로 생기거나(None -> 값) 없어진 것은 공격·효과가 추가·삭제된 것이라 남긴다."""
    return "/attributes/labels[" in c["field"] and c["before"] is not None and c["after"] is not None


# (이름, 판별 함수). 위에서부터 먼저 맞는 규칙 이름으로 센다
NOISE_RULES = (
    ("성우 정보", lambda c: c["field"].startswith("cv/")),
    ("수치 표 항목 이름 수정", _is_label_rename),
    ("소개 문구", lambda c: c["field"].endswith("flavorText")),
    ("일반 공격 이름 표기", _is_name_prefix_change),
    ("빈 값 표기 (NaN·0%)", lambda c: c["before"] in EMPTY_LIKE and c["after"] in EMPTY_LIKE),
    ("생일 정보", lambda c: c["field"] in ("birthday", "birthdaymmdd")),
)


def noise_rule(change):
    """잡음이면 규칙 이름, 아니면 None."""
    for name, is_noise in NOISE_RULES:
        try:
            if is_noise(change):
                return name
        except (TypeError, AttributeError):    # 값이 숫자 목록 등이면 그 규칙은 해당 없음
            continue
    return None


def drop_noise(records):
    """-> (남긴 기록 목록, 규칙별로 걸러 낸 변경 수 Counter, 통째로 빠진 기록 수)."""
    kept, by_rule, dropped = [], Counter(), 0
    for r in records:
        if r["change_type"] != "modified":
            kept.append(r)
            continue
        changes = []
        for c in r["changes"]:
            rule = noise_rule(c)
            if rule:
                by_rule[rule] += 1
            else:
                changes.append(c)
        if changes:
            kept.append({**r, "changes": changes})
        else:
            dropped += 1
    return kept, by_rule, dropped
