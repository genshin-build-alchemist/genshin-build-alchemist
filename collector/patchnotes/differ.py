"""두 JSON(변경 전/후)을 비교해 '의미 있는 변경'만 뽑아내는 순수 함수들. git과 무관."""
from .textutil import clean_text

# 비교할 필요 없는 필드: 식별자/이미지 + 패치 내용과 무관한 설정 텍스트(무기 이야기, 지역) + 육성 재료(데이터 구조 개편으로 자주 바뀜)
IGNORE_KEYS = {"id", "images", "url", "story", "region", "costs"}


def _skip_key(key):
    return key in IGNORE_KEYS or key.endswith("Raw")   # xxxRaw 는 태그가 섞인 중복 필드


def _is_number_list(items):
    return all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in items)


def flatten(obj, prefix=""):
    """JSON을 {경로: 값} 딕셔너리로 펼친다. 숫자만 든 리스트(배율 표 등)는 통째로 한 값으로 취급."""
    out = {}
    if isinstance(obj, dict):
        for key, value in obj.items():
            if _skip_key(key):
                continue
            out.update(flatten(value, f"{prefix}/{key}" if prefix else key))
    elif isinstance(obj, list):
        if _is_number_list(obj):
            out[prefix] = obj
        else:
            for i, value in enumerate(obj):
                out.update(flatten(value, f"{prefix}[{i}]"))
    else:
        out[prefix] = obj
    return out


def diff_json(before, after):
    """바뀐 필드 목록 [{field, before, after}] 을 돌려준다. 서식만 바뀐 경우는 무시."""
    a, b = flatten(before or {}), flatten(after or {})
    changes = []
    for path in sorted(set(a) | set(b)):
        old, new = clean_text(a.get(path)), clean_text(b.get(path))
        if old == new:
            continue
        changes.append({"field": path, "before": old, "after": new})
    return changes
