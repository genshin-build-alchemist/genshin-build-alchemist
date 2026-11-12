"""content/*.yaml 읽기 (사람이 쓰는 글과 수동 값).

글 속 숫자는 사람이 직접 쓴다 (자리표시 없음). 대신 각 yaml 맨 위의 based_on으로
"이 글이 어떤 데이터를 보고 쓴 것인지"를 남기고, 지금 데이터와 다르면 탭에 회색 안내를 띄운다 (README 3-3).
경로는 이 파일 위치 기준이다 (로컬·Streamlit Cloud 공통).
"""
import html
import re
from pathlib import Path

import yaml

from . import loader

CONTENT_DIR = Path(__file__).resolve().parent.parent / "content"
STALE_MSG = "글 작성 이후 데이터가 바뀌었어요. 문장 속 숫자를 확인해 주세요."


def load_content(name, content_dir=CONTENT_DIR):
    """content/{name}.yaml -> dict. 파일이 없으면 빈 dict (화면은 글 없이 숫자만 보여 준다)."""
    path = Path(content_dir) / f"{name}.yaml"
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def stage_order(content_dir=CONTENT_DIR):
    """stages.yaml의 order. 없으면 loader의 기본 순서."""
    return list(load_content("stages", content_dir).get("order") or loader.DEFAULT_ORDER)


def based_on_status(content, folder_result):
    """yaml의 based_on이 지금 데이터와 같으면 None, 다르면 회색 안내 문구."""
    based = (content or {}).get("based_on") or {}
    if not based:
        return "이 글에는 based_on이 없어요. " + STALE_MSG
    if based.get("folder") != folder_result["folder"] or \
            _iso(based.get("created_at")) != _iso(folder_result["latest_created_at"]):
        return STALE_MSG
    return None


def _iso(value):
    """따옴표 없이 쓴 날짜(yaml이 datetime으로 읽음)도 JSON의 '2026-11-10T06:38:09' 형식으로 맞춘다."""
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def rich(text):
    """yaml 글 -> 화면용 HTML 조각. 특수문자는 이스케이프하고,
    **굵게**는 <b>, `코드`는 <code>, 줄바꿈은 <br>로 바꾼다."""
    out = html.escape(str(text).strip(), quote=False)
    out = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", out)
    out = re.sub(r"`(.+?)`", r"<code>\1</code>", out)
    return out.replace("\n", "<br>")
