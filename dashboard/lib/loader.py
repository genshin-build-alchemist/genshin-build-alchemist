"""결과 JSON 읽기 · 검증 · 지표 계산 (화면과 분리, 표준 라이브러리만).

- 파일은 읽기만 한다. 이 모듈에는 파일을 쓰는 코드가 없다.
- 경로는 모두 이 파일 위치 기준이다 (로컬·Streamlit Cloud 어디서 실행해도 같은 파일을 찾는다).
- 검증 규칙은 dashboard/README.md 2장, 계산 방법은 3-1을 따른다.
"""
import json
import re
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from statistics import mean, median

DASHBOARD_DIR = Path(__file__).resolve().parent.parent   # dashboard/
DATA_DIR = DASHBOARD_DIR / "data"
FOLDERS = ("official", "dev", "aux", "model_compare")

# stages.yaml이 없을 때만 쓰는 기본 단계 순서 (화면에서는 stages.yaml의 order를 넘겨 받는다)
DEFAULT_ORDER = ["baseline", "prompt_v2", "rag", "rag_v3", "rag_v4"]
TYPES = ("lookup", "filter", "unknown")

MACRO_TOLERANCE = 0.00005   # 파일 값은 소수 4자리 반올림이라, 반올림 오차보다 크게 다를 때만 경고
MODEL_ID = re.compile(r"qwen2\.5-(\d+(?:\.\d+)?)b-([a-z0-9]+)-([a-z0-9]+)$", re.IGNORECASE)

RED, YELLOW = "red", "yellow"


# ---------- 읽기 ----------

def read_json(path):
    """결과 JSON 하나를 읽는다 (읽기 전용)."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def is_post(path, data):
    """후처리본인지: 파일 이름이 _post로 끝나거나 method에 +post가 있으면."""
    return Path(path).stem.endswith("_post") or "+post" in str(data.get("method", ""))


def parse_model_id(experiment_id):
    """'dev_rag_v4_qwen2.5-7b-bf16-l4' -> {'size': '7B', 'precision': 'bf16', 'gpu': 'L4', 'size_num': 7.0}.
    형식이 다르면 None."""
    m = MODEL_ID.search(str(experiment_id))
    if not m:
        return None
    size, precision, gpu = m.groups()
    return {"size": f"{size}B", "precision": precision.lower(), "gpu": gpu.upper(), "size_num": float(size)}


def model_label(run):
    """'1.5B · L4 · fp16' 같은 표시 이름 (model_compare용)."""
    m = run["model"]
    return f"{m['size']} · {m['gpu']} · {m['precision']}"


def recompute_macro_f1(per_question):
    """문항별 f1 평균, 소수 4자리 (노트북 01 summarize()와 같은 방식). 문항이 없으면 None."""
    if not per_question:
        return None
    return round(sum(x["f1"] for x in per_question) / len(per_question), 4)


def _file_checks(name, data):
    """파일 하나의 검사: n과 문항 수, macro F1 재계산. -> [(level, msg)]"""
    out = []
    pq = data.get("per_question")
    if pq is None:
        return out
    n = data.get("metrics", {}).get("n")
    if n != len(pq):
        out.append((YELLOW, f"{name}: metrics.n({n})과 per_question 개수({len(pq)})가 다름"))
    saved = data.get("metrics", {}).get("macro_f1")
    again = recompute_macro_f1(pq)
    if again is not None and (saved is None or abs(saved - again) > MACRO_TOLERANCE):
        out.append((YELLOW, f"{name}: macro F1이 다름 (파일 {saved} / 다시 계산 {again})"))
    return out


def load_folder(folder, data_dir=DATA_DIR, order=None):
    """폴더 하나를 읽고 검증한다.

    반환: {
      'folder': 'dev',
      'runs': [{'file', 'key', 'method', 'data', 'model'}...],   # 화면에 쓰는 파일, 순서대로
      'excluded': [{'file', 'reason'}...],                         # 쓰지 않는 파일
      'checks': [{'level': red/yellow/gray, 'msg'}...],            # 문제가 없으면 빈 목록
      'latest_created_at': '2026-11-10T06:05:17' 또는 None,         # runs 중 가장 늦은 created_at
    }
    단계(key)는 method 값이다. model_compare는 모델·GPU·정밀도 조합이 key다.
    """
    order = list(order or DEFAULT_ORDER)
    folder_dir = Path(data_dir) / folder
    is_model = folder == "model_compare"
    checks, excluded, candidates = [], [], []

    for path in sorted(folder_dir.glob("*.json")) if folder_dir.is_dir() else []:
        data = read_json(path)
        name = path.name
        if is_post(path, data):
            excluded.append({"file": name, "reason": "후처리본 (_post)"})
            continue
        # aux 파일은 limit·per_question 칸이 없다 -> limit 검사를 하지 않는다
        if "per_question" in data:
            if "limit" not in data:
                excluded.append({"file": name, "reason": "limit 칸 없음"})
                checks.append((YELLOW, f"{name}: limit 칸이 없어서 뺐어요 (null이어야 전체 문항 결과)"))
                continue
            if data["limit"] is not None:
                excluded.append({"file": name, "reason": f"limit = {data['limit']}"})
                checks.append((YELLOW, f"{name}: limit = {data['limit']} (일부 문항만 돌린 결과)라서 뺐어요"))
                continue
        model = None
        if is_model:
            model = parse_model_id(data.get("experiment_id", ""))
            if model is None:
                excluded.append({"file": name, "reason": "experiment_id 형식이 다름"})
                checks.append((YELLOW, f"{name}: experiment_id에서 모델·GPU·정밀도를 읽지 못해 뺐어요"))
                continue
        checks += _file_checks(name, data)
        key = (model["size"], model["gpu"], model["precision"]) if is_model else data.get("method")
        candidates.append({"file": name, "key": key, "method": data.get("method"), "data": data, "model": model})

    # 같은 key가 여럿이면 created_at이 늦은 파일
    chosen = {}
    for run in candidates:
        old = chosen.get(run["key"])
        if old is None:
            chosen[run["key"]] = run
            continue
        newer, older = sorted([old, run], key=lambda r: r["data"].get("created_at", ""), reverse=True)
        chosen[run["key"]] = newer
        excluded.append({"file": older["file"], "reason": f"같은 단계 중복 ({newer['file']}를 씀)"})
        checks.append((YELLOW, f"같은 단계 {run['key']}가 두 개: 늦게 만든 {newer['file']}를 써요"))
    runs = list(chosen.values())

    # 순서: model_compare는 크기 -> GPU -> 정밀도, 나머지는 stages 순서 (없는 단계는 맨 뒤)
    if is_model:
        runs.sort(key=lambda r: (r["model"]["size_num"], r["model"]["gpu"], r["model"]["precision"]))
    else:
        unknown = [r for r in runs if r["key"] not in order]
        for r in unknown:
            checks.append((YELLOW, f"stages.yaml에 등록되지 않은 단계: {r['key']} (맨 뒤에 붙였어요)"))
        runs = sorted([r for r in runs if r["key"] in order], key=lambda r: order.index(r["key"])) + \
            sorted(unknown, key=lambda r: r["data"].get("created_at", ""))

    versions = sorted({r["data"].get("dataset_version") for r in runs}, key=str)
    if len(versions) > 1:
        checks.append((RED, f"dataset_version이 섞여 있어요: {', '.join(map(str, versions))}"))

    created = [r["data"]["created_at"] for r in runs if r["data"].get("created_at")]
    return {
        "folder": folder,
        "runs": runs,
        "excluded": excluded,
        "checks": [{"level": level, "msg": msg} for level, msg in checks],
        "latest_created_at": max(created) if created else None,
    }


def load_all(data_dir=DATA_DIR, order=None):
    """{'official': {...}, 'dev': {...}, 'aux': {...}, 'model_compare': {...}}"""
    return {f: load_folder(f, data_dir, order) for f in FOLDERS}


# ---------- 계산 ----------

def metric(data, key, qtype=None):
    """metrics.key 또는 by_type.qtype.key. 없으면 None."""
    src = data.get("by_type", {}).get(qtype, {}) if qtype else data.get("metrics", {})
    return src.get(key)


def questions(data, qtype=None):
    pq = data.get("per_question") or []
    return [x for x in pq if qtype is None or x.get("type") == qtype]


def median_seconds(data, qtype=None):
    """문항별 seconds의 중앙값 (JSON에 없어서 직접 계산). 기록이 없으면 None."""
    secs = [x["seconds"] for x in questions(data, qtype) if "seconds" in x]
    return median(secs) if secs else None


def avg_answer_len(data, qtype="filter"):
    """그 유형 문항에서 모델이 낸 답(pred) 개수의 평균."""
    qs = questions(data, qtype)
    return mean(len(x["pred"]) for x in qs) if qs else None


def avg_gold_len(data, qtype="filter"):
    """그 유형 문항의 정답(gold) 개수 평균."""
    qs = questions(data, qtype)
    return mean(len(x["gold"]) for x in qs) if qs else None


def wrong_questions(data, qtype=None):
    """f1이 1이 아닌 문항 -> [{'id', 'question', 'gold', 'pred'}]"""
    return [{"id": x["id"], "question": x["question"], "gold": x["gold"], "pred": x["pred"]}
            for x in questions(data, qtype) if x["f1"] < 1]


def hallucinations_by_type(aux_data):
    """aux hallucinations[].id 앞부분으로 유형 분류 -> {'lookup': n, 'filter': n, 'unknown': n, 'other': n}.
    hallucinations 칸이 없으면 None (화면에서 '유형 구분 없음')."""
    items = aux_data.get("hallucinations")
    if items is None:
        return None
    out = {t: 0 for t in TYPES}
    out["other"] = 0
    for h in items:
        prefix = str(h.get("id", "")).split("_")[0]
        out[prefix if prefix in TYPES else "other"] += 1
    return out


def pearson_r(xs, ys):
    """피어슨 상관계수: 공분산 / (x 표준편차 × y 표준편차). 값이 2개 미만이거나 한쪽이 모두 같으면 None."""
    if len(xs) != len(ys) or len(xs) < 2:
        return None
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    dx = [x - mx for x in xs]
    dy = [y - my for y in ys]
    sxy = sum(a * b for a, b in zip(dx, dy))
    sxx = sum(a * a for a in dx)
    syy = sum(b * b for b in dy)
    if sxx == 0 or syy == 0:
        return None
    return sxy / (sxx * syy) ** 0.5


def round_half_up(value, digits=3):
    """보통 말하는 반올림 (5 이상 올림). round()는 0.8115 -> 0.811로 내려갈 수 있어서 Decimal로 계산한다."""
    q = Decimal(1).scaleb(-digits)   # digits=3 -> 0.001
    return float(Decimal(str(value)).quantize(q, rounding=ROUND_HALF_UP))


def best_of(items, higher=True):
    """[(이름, 값)] 중 1위 -> (이름 목록, 값). 화면 표시(소수 3자리) 기준으로 같으면 공동 1위."""
    items = [(n, v) for n, v in items if v is not None]
    if not items:
        return [], None
    shown = [(n, round_half_up(v)) for n, v in items]
    top = max(v for _, v in shown) if higher else min(v for _, v in shown)
    names = [n for n, v in shown if v == top]
    value = next(v for n, v in items if n == names[0])
    return names, value


def fmt(value, digits=3, missing="기록 없음"):
    """화면 표시: 소수 3자리까지 반올림(5 이상 올림), 원래 3자리 이하면 그대로 (1.0, 6.59). 없으면 '기록 없음'."""
    if value is None:
        return missing
    if isinstance(value, bool) or isinstance(value, int):
        return str(value)
    return str(round_half_up(value, digits))


def all_checks(results):
    """load_all() 결과의 검사를 모은다 -> [{'folder', 'level', 'msg'}]"""
    return [{"folder": f, **c} for f, r in results.items() for c in r["checks"]]
