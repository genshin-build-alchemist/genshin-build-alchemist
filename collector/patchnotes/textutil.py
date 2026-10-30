"""텍스트 정리와 필드 이름 한글화 도구 (표준 라이브러리만 사용)."""
import re

ANY_TAG = re.compile(r"<[^>]+>")   # <color=#FFD780FF> 같은 게임 서식 태그 전부
SPACES = re.compile(r"[ \t]+")

SKILL_LABELS = {"combat1": "일반 공격", "combat2": "원소 스킬", "combat3": "원소 폭발"}
TOKEN_LABELS = {
    "name": "이름", "description": "설명", "effect": "효과",
    "attributes": "", "labels": "수치 항목", "parameters": "수치",
}


def clean_text(value):
    """게임 서식 태그를 지우고 공백/빈 줄을 정리한다. 문자열이 아니면 그대로 돌려준다."""
    if not isinstance(value, str):
        return value
    text = ANY_TAG.sub("", value)
    lines = [SPACES.sub(" ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def shorten(text, limit=300):
    """줄바꿈을 ' / '로 합치고, 너무 길면 말줄임표로 자른다."""
    text = " / ".join(str(text).splitlines())
    return text if len(text) <= limit else text[:limit] + "…"


def _head_label(head):
    if head in SKILL_LABELS:
        return SKILL_LABELS[head]
    m = re.fullmatch(r"passive(\d+)", head)
    if m:
        return f"고유 특성 {m.group(1)}"
    m = re.fullmatch(r"c(\d+)", head)
    if m:
        return f"명의 자리 {m.group(1)}"
    return head


def humanize_field(path):
    """'combat2/attributes/labels[0]' -> '원소 스킬 수치 항목 #1' 처럼 읽기 쉽게 바꾼다."""
    parts = path.split("/")
    words = [_head_label(parts[0])]
    for seg in parts[1:]:
        m = re.fullmatch(r"(.*?)\[(\d+)\]", seg)
        base, idx = (m.group(1), f" #{int(m.group(2)) + 1}") if m else (seg, "")
        label = TOKEN_LABELS.get(base, base)
        if label or idx:
            words.append(label + idx)
    return " ".join(w for w in words if w)
