"""결과 JSON 읽기 · 검증 · 지표 계산 (화면과 분리, 표준 라이브러리만).

- 파일은 읽기만 한다. 이 모듈에는 파일을 쓰는 코드가 없다.
- 경로는 모두 이 파일 위치 기준이다 (로컬·Streamlit Cloud 어디서 실행해도 같은 파일을 찾는다).
- 검증 규칙은 dashboard/README.md 2장, 계산 방법은 3-1을 따른다.
"""
import csv
import json
import re
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from statistics import mean, median

DASHBOARD_DIR = Path(__file__).resolve().parent.parent   # dashboard/
DATA_DIR = DASHBOARD_DIR / "data"
FOLDERS = ("official", "dev", "aux", "model_compare")

# stages.yaml이 없을 때만 쓰는 기본 단계 순서 (화면에서는 stages.yaml의 order를 넘겨 받는다)
DEFAULT_ORDER = ["baseline", "prompt_v2", "rag", "rag_v3", "rag_v4", "rag_v5", "rag_v5_data"]
TYPES = ("lookup", "filter", "unknown")

MACRO_TOLERANCE = 0.00005   # 파일 값은 소수 4자리 반올림이라, 반올림 오차보다 크게 다를 때만 경고
# experiment_id에서 모델 크기를 뽑는 정규식: "qwen2.5-" + (크기: 7 또는 1.5) + "b"
#   파일마다 뒷부분 순서가 달라서(…-7b-fp16-L4 / …-7b-L4-fp16 / …-1.5b-L4) GPU·정밀도는 따로 찾는다
MODEL_ID = re.compile(r"qwen2\.5-(\d+(?:\.\d+)?)b", re.IGNORECASE)
# 크기 뒤에서 GPU 이름 찾기: 영문 1글자 + 숫자 (L4, T4, A100). 앞뒤가 영문·숫자가 아니어야 한다 (fp16은 안 잡힘)
GPU_TOKEN = re.compile(r"(?<![a-z0-9])([a-z]\d{1,3})(?![a-z0-9])", re.IGNORECASE)
PRECISIONS = ("bf16", "fp16", "fp32", "8bit", "4bit")   # 이름에 적힌 정밀도 (config.load_4bit가 우선)

RED, YELLOW = "red", "yellow"


# ---------- 읽기 ----------

def read_json(path):
    """결과 JSON 하나를 읽는다 (읽기 전용)."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def is_post(path, data):
    """후처리본인지: 파일 이름이 _post로 끝나거나 method에 +post가 있으면."""
    return Path(path).stem.endswith("_post") or "+post" in str(data.get("method", ""))


def parse_model_id(experiment_id, config=None):
    """'dev_rag_v4_qwen2.5-7b-fp16-L4' -> {'size': '7B', 'precision': 'fp16', 'gpu': 'L4', 'size_num': 7.0}.
    - 크기: 'qwen2.5-7b', GPU: 크기 뒤의 'L4'·'T4' 같은 글자 (순서는 상관없음)
    - 정밀도: config.load_4bit가 True면 '4bit', 아니면 이름에 적힌 정밀도, 둘 다 없으면 'fp16'
    크기나 GPU를 못 찾으면 None."""
    eid = str(experiment_id)
    m = MODEL_ID.search(eid)
    if not m:
        return None
    rest = eid[m.end():]
    gpu = GPU_TOKEN.search(rest)
    if not gpu:
        return None
    named = next((p for p in PRECISIONS if re.search(rf"(?<![a-z0-9]){p}(?![a-z0-9])", rest, re.IGNORECASE)), None)
    precision = "4bit" if (config or {}).get("load_4bit") is True else (named or "fp16")
    size = m.group(1)
    return {"size": f"{size}B", "precision": precision, "gpu": gpu.group(1).upper(), "size_num": float(size)}


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
    """파일 하나의 검사: n과 문항 수, macro F1 재계산. -> [(level, msg)]
    파일에 적힌 점수를 그대로 믿지 않고, 문항별 결과로 다시 계산해서 맞는지 확인한다."""
    out = []
    pq = data.get("per_question")
    if pq is None:            # aux 파일처럼 문항별 결과가 없으면 검사할 게 없다
        return out
    n = data.get("metrics", {}).get("n")
    if n != len(pq):
        out.append((YELLOW, f"{name}: metrics.n({n})과 per_question 개수({len(pq)})가 다름"))
    saved = data.get("metrics", {}).get("macro_f1")
    again = recompute_macro_f1(pq)
    if again is not None and (saved is None or abs(saved - again) > MACRO_TOLERANCE):
        out.append((YELLOW, f"{name}: macro F1이 다름 (파일 {saved} / 다시 계산 {again})"))
    return out


AUX_SUMMARY = "보조지표_요약-info-v2.csv"      # 보조 지표 요약 (단계마다 한 줄)
AUX_CASES = "보조지표_환각사례-info-v2.csv"    # 환각 사례 (문항마다 한 줄, 유형별 건수를 셀 때 씀)


def read_csv(path):
    """CSV 하나를 읽는다 (읽기 전용). 엑셀에서 저장한 BOM이 있어도 칸 이름이 깨지지 않게 utf-8-sig."""
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _num(row, key, kind=float):
    """CSV 칸 -> 숫자. 비었으면 None."""
    value = (row.get(key) or "").strip()
    return kind(value) if value else None


def aux_csv_candidates(folder_dir, ref=None):
    """보조 지표 CSV 2개 -> 단계별 결과 (aux JSON과 같은 모양) + 검사 목록.
    날짜·평가셋 버전은 CSV에 없어서 같은 단계의 공식 결과(ref: method -> official data)에서 가져온다."""
    ref = ref or {}
    checks, candidates = [], []
    cases_path = Path(folder_dir) / AUX_CASES
    cases = read_csv(cases_path) if cases_path.exists() else None
    if cases is None:
        checks.append((YELLOW, f"{AUX_CASES}가 없어서 환각을 유형별로 나누지 못해요"))
    for row in read_csv(Path(folder_dir) / AUX_SUMMARY):
        method = (row.get("방법") or "").strip()
        base = ref.get(method) or {}
        hal = None if cases is None else [{"id": c.get("id"), "type": c.get("유형")} for c in cases
                                          if (c.get("방법") or "").strip() == method]
        hn = _num(row, "환각 문항 수", int)
        if hal is not None and hn is not None and len(hal) != hn:
            checks.append((YELLOW, f"{method}: 환각 사례 {len(hal)}건과 요약의 환각 문항 수 {hn}이 달라요"))
        data = {
            "method": method, "model": row.get("모델"), "experiment_id": row.get("실험 ID"), "notes": row.get("비고"),
            "dataset_version": base.get("dataset_version"), "created_at": base.get("created_at"),
            "metrics": {"n": _num(row, "전체 문항 수", int), "accuracy": _num(row, "정답률"),
                        "correct": _num(row, "정답 문항 수", int), "refusal_accuracy": _num(row, "거절 정확도"),
                        "hallucination_rate": _num(row, "환각률"), "hallucinated_questions": hn,
                        "answered": _num(row, "답한 문항 수", int)},
            "hallucinations": hal,
        }
        candidates.append({"file": AUX_SUMMARY, "key": method, "method": method, "data": data, "model": None})
    return candidates, checks


def load_folder(folder, data_dir=DATA_DIR, order=None, ref=None):
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

    # 0) 보조 지표는 팀이 만든 CSV를 그대로 읽는다 (있으면 같은 폴더의 JSON은 쓰지 않음)
    use_csv = folder == "aux" and (folder_dir / AUX_SUMMARY).exists()
    if use_csv:
        candidates, csv_checks = aux_csv_candidates(folder_dir, ref)
        checks += csv_checks

    # 1) 파일마다: 쓰지 않을 파일(후처리본, 일부 문항만 돌린 결과 등)을 거르고, 나머지는 후보로 모은다
    for path in sorted(folder_dir.glob("*.json")) if folder_dir.is_dir() and not use_csv else []:
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
            model = parse_model_id(data.get("experiment_id", ""), data.get("config"))
            if model is None:
                excluded.append({"file": name, "reason": "experiment_id 형식이 다름"})
                checks.append((YELLOW, f"{name}: experiment_id에서 모델·GPU·정밀도를 읽지 못해 뺐어요"))
                continue
        checks += _file_checks(name, data)
        key = (data.get("method"), model["size"], model["gpu"], model["precision"]) if is_model else data.get("method")
        candidates.append({"file": name, "key": key, "method": data.get("method"), "data": data, "model": model})

    # 2) 같은 key가 여럿이면 created_at이 늦은 파일 (같은 실험을 다시 돌린 경우 최신 결과를 쓴다)
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

    # 3) 순서: model_compare는 단계 -> 크기 -> GPU -> 정밀도, 나머지는 stages 순서 (없는 단계는 맨 뒤)
    if is_model:
        rank = lambda m: order.index(m) if m in order else len(order)   # noqa: E731
        runs.sort(key=lambda r: (rank(r["method"]), r["model"]["size_num"], r["model"]["gpu"], r["model"]["precision"]))
    else:
        unknown = [r for r in runs if r["key"] not in order]
        for r in unknown:
            checks.append((YELLOW, f"stages.yaml에 등록되지 않은 단계: {r['key']} (맨 뒤에 붙였어요)"))
        runs = sorted([r for r in runs if r["key"] in order], key=lambda r: order.index(r["key"])) + \
            sorted(unknown, key=lambda r: r["data"].get("created_at", ""))

    # 4) 폴더 전체 검사: 평가셋 버전이 다르면 점수를 나란히 비교하면 안 되므로 빨간 경고
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
    """{'official': {...}, 'dev': {...}, 'aux': {...}, 'model_compare': {...}}
    보조 지표 CSV에는 날짜·평가셋 버전이 없어서, 공식 결과를 먼저 읽어 단계별로 넘겨 준다."""
    out = {"official": load_folder("official", data_dir, order)}
    ref = {r["key"]: r["data"] for r in out["official"]["runs"]}
    for f in FOLDERS:
        if f not in out:
            out[f] = load_folder(f, data_dir, order, ref=ref if f == "aux" else None)
    return out


# ---------- 계산 ----------

def metric(data, key, qtype=None):
    """metrics.key 또는 by_type.qtype.key. 없으면 None.
    예: metric(d, "macro_f1") = 전체 점수, metric(d, "macro_f1", "filter") = 조건 검색 문항만의 점수."""
    src = data.get("by_type", {}).get(qtype, {}) if qtype else data.get("metrics", {})
    return src.get(key)


def questions(data, qtype=None):
    """문항별 결과 목록. qtype(lookup / filter / unknown)을 주면 그 유형 문항만, 안 주면 전부."""
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


def exact_counts(data, qtype=None, examples=2):
    """완전 정답(f1 = 1) 수 · 오답 수 · 오답 문항 예시 -> {'n', 'correct', 'wrong', 'examples': [질문, ...]}.
    예시는 결과 파일의 문항 순서대로 앞에서 examples개."""
    qs = questions(data, qtype)
    wrong = [x for x in qs if x["f1"] < 1]
    return {"n": len(qs), "correct": len(qs) - len(wrong), "wrong": len(wrong),
            "examples": [x["question"] for x in wrong[:examples]]}


def slowest(data, k=3):
    """응답 시간이 가장 긴 문항 k개 -> [{'question', 'seconds', 'pred_n', 'gold_n'}] (느린 순)."""
    qs = sorted((x for x in questions(data) if "seconds" in x), key=lambda x: -x["seconds"])[:k]
    return [{"question": x["question"], "seconds": x["seconds"], "pred_n": len(x["pred"]), "gold_n": len(x["gold"])}
            for x in qs]


def short_date(created_at):
    """'2026-11-17T06:23:47' -> '11/17'. 형식이 다르면 None."""
    m = re.match(r"\d{4}-(\d{2})-(\d{2})", str(created_at or ""))
    return f"{int(m.group(1))}/{int(m.group(2))}" if m else None


def data_badge(data, data_version=None):
    """데이터 배지 글: 'Info_v2 · 평가 121문항 · 데이터 7.2' (DEV면 'Info_v2 · Dev · 60문항 · 데이터 7.2')."""
    ds = str(data.get("dataset_version") or "")
    dev = ds.endswith("-dev")
    name = ds.removesuffix("-dev")
    parts = [name[:1].upper() + name[1:]] if name else []
    n = metric(data, "n")
    if dev:
        parts += ["Dev"] + ([f"{n}문항"] if n else [])
    elif n:
        parts.append(f"평가 {n}문항")
    if data_version:
        parts.append(str(data_version))
    return " · ".join(parts)


def hallucinations_by_type(aux_data):
    """aux hallucinations[].id 앞부분으로 유형 분류 -> {'lookup': n, 'filter': n, 'unknown': n, 'other': n}.
    hallucinations 칸이 없으면 None (화면에서 '유형 구분 없음')."""
    items = aux_data.get("hallucinations")
    if items is None:
        return None
    out = {t: 0 for t in TYPES}
    out["other"] = 0
    for h in items:
        prefix = str(h.get("id", "")).split("_")[0]     # "filter_012" -> "filter"
        out[prefix if prefix in TYPES else "other"] += 1
    return out


def pearson_r(xs, ys):
    """피어슨 상관계수: 공분산 / (x 표준편차 × y 표준편차). 값이 2개 미만이거나 한쪽이 모두 같으면 None.
    -1 ~ 1 사이 값. 1에 가까우면 "x가 클수록 y도 크다" (② 탭: 빈 답이 많을수록 빨라지는지 확인)."""
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
    shown = [(n, round_half_up(v)) for n, v in items]    # 화면에 보이는 값으로 비교해야 "왜 같은데 1위가 하나지?"가 안 생긴다
    top = max(v for _, v in shown) if higher else min(v for _, v in shown)
    names = [n for n, v in shown if v == top]
    value = next(v for n, v in items if n == names[0])
    return names, value


def fmt(value, digits=3, missing="기록 없음"):
    """화면 표시: 소수 3자리까지 반올림(5 이상 올림), 원래 3자리 이하면 그대로 (1.0, 6.59). 없으면 '기록 없음'."""
    if value is None:
        return missing
    if isinstance(value, bool) or isinstance(value, int):     # 정수(문항 수 등)는 반올림 없이 그대로
        return str(value)
    return str(round_half_up(value, digits))


def fix(value, digits=3, missing="기록 없음"):
    """표·카드용 고정 자릿수 표시: 0.75 -> '0.750', 1.43 -> '1.430' (5 이상 올림). 정수는 그대로."""
    if value is None:
        return missing
    if isinstance(value, bool) or isinstance(value, int):
        return str(value)
    return f"{round_half_up(value, digits):.{digits}f}"


def pct(value, digits=1, missing="기록 없음"):
    """비율(0~1) -> 퍼센트 글자: 0.76 -> '76.0%'."""
    return missing if value is None else f"{round_half_up(value * 100, digits):.{digits}f}%"


def all_checks(results):
    """load_all() 결과의 검사를 모은다 -> [{'folder', 'level', 'msg'}]"""
    return [{"folder": f, **c} for f, r in results.items() for c in r["checks"]]
