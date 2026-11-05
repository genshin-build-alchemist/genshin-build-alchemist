"""검색 평가 (RAG의 R): 문항별 정답 근거 문서와 Hit@k / Recall@k.

답이 틀렸을 때 '검색이 근거를 못 찾았는지(검색 실패)'와 '근거는 찾았는데 모델이 틀렸는지(답변 오류)'를
나눠 보려면, 문항마다 어떤 문서가 정답 근거인지 알아야 한다. 그 목록과 채점 함수를 둔다.

정답 근거 문서 (data/docs/documents_ko.jsonl 의 doc_id)
  lookup  : 질문한 캐릭터의 문서 1개          예) '알베도의 원소는 뭐야?' -> character:albedo
  filter  : 정답 캐릭터 전부의 문서           예) '4성 물 원소 캐릭터' -> character:barbara, character:candace, ...
  unknown : 없음 (빈 목록). 검색 점수에서 뺀다
  질문 문장은 보지 않고 정답(gold)과 캐릭터 이름으로만 정한다. 그래서 라우터·검색을 고쳐도 정답 근거는 그대로다.

지표 (상위 k개 = 검색 결과 앞에서부터 k개)
  hit@k    : 정답 문서가 상위 k개 안에 하나라도 있으면 1   -> lookup의 주 지표
  recall@k : 정답 문서 중 상위 k개 안에 든 비율           -> filter의 주 지표
  all@k    : 정답 문서가 상위 k개 안에 모두 있으면 1        -> filter에서 '빠짐없이 찾았나'
  precision@k : 상위 k개(결과가 k개보다 적으면 결과 전부) 중 정답 문서 비율 -> filter에서 '쓸데없는 근거가 섞였나'

사용 (코랩·로컬 공통)
  from core.retrieval_eval import dev_questions, evaluate_retrieval, print_report

  def my_search(question, pool):        # 직접 만든 검색 함수
      ...                                # pool: 검색해도 되는 doc_id 집합 (None이면 전체)
      return ["character:albedo", ...]   # doc_id 목록, 1등부터 순서대로

  report = evaluate_retrieval(my_search, dev_questions())   # 검색 방식을 고를 때는 DEV 60문항만
  print_report(report)

  - 학습용(DEV) 질문의 pool에는 평가용 캐릭터 22명의 문서가 빠져 있다. 검색 결과는 반드시 pool 안에서 고른다.
  - 평가 115문항(eval_questions())은 최종 방식을 정한 뒤 한 번만 본다.

  - 말투 변형 질문: csv_questions(STYLE_DEV) 로 같은 방식으로 잰다 (띄어쓰기 없음, 존댓말 등 note 칸으로 나눠 보기)

실행: python3 -m core.retrieval_eval           -> 지금 키워드 검색(core/retrieval.py)의 기준점 출력
      python3 -m core.retrieval_eval --write   -> data/eval/evidence_info_v1.json 다시 만들기
"""
import hashlib
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

from core.human_questions import answer_for_target
from core.kb import load_kb

ROOT = Path(__file__).resolve().parent.parent
EVALSET = ROOT / "data" / "eval" / "questions_info_v1.json"
EVIDENCE = ROOT / "data" / "eval" / "evidence_info_v1.json"
DOCS = ROOT / "data" / "docs" / "documents_ko.jsonl"
STYLE_DEV = ROOT / "data" / "eval" / "style_questions_dev.csv"     # 학습용 캐릭터, 마음껏 봐도 됨
STYLE_EVAL = ROOT / "data" / "eval" / "style_questions_v1.csv"     # 평가용 캐릭터, 마지막에 한 번만
KS = (1, 3, 5, 10, 30)          # 30 = 지금 filter 검색이 넘기는 최대 개수 (retrieval.FILTER_TOP_K)


# ─────────────────────────────────────────────────────────────
# 질문 목록 (노트북 01_eval_info.ipynb 와 같은 규칙)
# ─────────────────────────────────────────────────────────────
def load_evalset(path=EVALSET):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def eval_questions(data=None):
    """평가 115문항. 최종 방식을 정한 뒤 한 번만 본다."""
    data = data or load_evalset()
    return [q for q in data["questions"] if q["split"] == "eval"]


def few_shot_examples(questions):
    """노트북 셀 7과 같다: 학습용 질문에서 lookup(원소) 1개, filter(정답 2~3명) 1개, unknown 1개."""
    train = [q for q in questions if q["split"] == "train"]
    return [next(q for q in train if q["type"] == "lookup" and q["field"] == "element"),
            next(q for q in train if q["type"] == "filter" and 2 <= len(q["gold"]) <= 3),
            next(q for q in train if q["type"] == "unknown")]


def dev_questions(data=None, n_per_field=10, n_filter=16, n_unknown=4):
    """노트북 build_dev_set()과 같은 DEV 60문항 (학습용 질문에서, few-shot 예시 제외, id 해시 순서)."""
    questions = (data or load_evalset())["questions"]
    shot_ids = {ex["id"] for ex in few_shot_examples(questions)}
    pool = sorted((q for q in questions if q["split"] == "train" and q["id"] not in shot_ids),
                  key=lambda q: hashlib.md5(("dev-" + q["id"]).encode("utf-8")).hexdigest())
    dev = []
    for field in ("element", "weapon", "rarity", "region"):
        dev += [q for q in pool if q["type"] == "lookup" and q["field"] == field][:n_per_field]
    dev += [q for q in pool if q["type"] == "filter"][:n_filter]
    dev += [q for q in pool if q["type"] == "unknown"][:n_unknown]
    return sorted(dev, key=lambda q: hashlib.md5(q["id"].encode("utf-8")).hexdigest())


# ─────────────────────────────────────────────────────────────
# 정답 근거 문서
# ─────────────────────────────────────────────────────────────
def load_documents(path=DOCS):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def character_doc_ids(kb):
    """캐릭터 이름 -> 문서 id. 예) '알베도' -> 'character:albedo'."""
    return {c["name"]: f"character:{c['key']}" for c in kb.characters}


def gold_doc_ids(q, name_to_doc):
    """질문(평가셋 형식) -> 정답 근거 doc_id 목록."""
    if q["type"] == "lookup":
        return [name_to_doc[q["character"]]]
    if q["type"] == "filter":
        return sorted(name_to_doc[n] for n in q["gold"])
    return []


def gold_doc_ids_for_target(target, kb):
    """사람·말투 질문의 target -> 정답 근거 doc_id 목록. '알베도/원소', '지역=몬드, 성급=5성', 빈칸."""
    target = (target or "").strip()
    name_to_doc = character_doc_ids(kb)
    if "/" in target and "=" not in target:
        name = target.rsplit("/", 1)[0].strip()
        if name not in name_to_doc:
            raise ValueError(f"캐릭터 '{name}' 없음")
        return [name_to_doc[name]]
    names, message = answer_for_target(target, kb)
    if names is None:
        raise ValueError(message)
    return sorted(name_to_doc[n] for n in names)


def csv_questions(path, kb=None):
    """말투·사람 질문 CSV(question,target,note) -> 평가셋과 같은 모양의 질문 목록 (정답 근거 gold_docs 포함).

    파일 이름에 '_dev'가 있으면 학습용(split=train, 평가용 캐릭터 문서 제외), 아니면 평가용(split=eval).
    """
    import csv
    kb = kb or load_kb()
    split = "train" if "_dev" in Path(path).stem else "eval"
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = [r for r in csv.DictReader(f) if (r.get("question") or "").strip()]
    out = []
    for i, r in enumerate(rows, 2):                 # 2행부터 (1행은 제목)
        target = (r.get("target") or "").strip()
        qtype = "filter" if "=" in target else "lookup" if "/" in target else "unknown"
        out.append({"id": f"{Path(path).stem}:{i}", "type": qtype, "question": r["question"].strip(),
                    "split": split, "note": (r.get("note") or "").split(" (")[0].strip(),
                    "gold_docs": gold_doc_ids_for_target(target, kb)})
    return out


def allowed_doc_ids(q, docs, eval_names):
    """검색해도 되는 doc_id 집합. 학습용 질문은 평가용 캐릭터 이름이 붙은 문서를 뺀다. 평가 질문은 None(전체)."""
    if q["split"] != "train":
        return None
    return {d["doc_id"] for d in docs if d["metadata"].get("name") not in eval_names}


def build_evidence(data=None, kb=None):
    """평가셋 611문항 전체의 정답 근거 + DEV id 목록 (data/eval/evidence_info_v1.json 내용)."""
    data = data or load_evalset()
    kb = kb or load_kb()
    name_to_doc = character_doc_ids(kb)
    evidence = {q["id"]: gold_doc_ids(q, name_to_doc) for q in data["questions"]}
    return {
        "dataset_version": data["dataset_version"],
        "questions_sha256": data["sha256"],
        "rule": "lookup = 질문한 캐릭터 문서 1개, filter = 정답 캐릭터 전부의 문서, unknown = 없음. "
                "doc_id는 data/docs/documents_ko.jsonl 기준. 만드는 코드: core/retrieval_eval.py",
        "counts": {t: sum(1 for q in data["questions"] if q["type"] == t) for t in ("lookup", "filter", "unknown")},
        "dev_ids": [q["id"] for q in dev_questions(data)],
        "evidence": evidence,
    }


def write_evidence(path=EVIDENCE):
    out = build_evidence()
    Path(path).write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return out


# ─────────────────────────────────────────────────────────────
# 채점
# ─────────────────────────────────────────────────────────────
def score(retrieved, gold, ks=KS):
    """검색 결과(순위순 doc_id) vs 정답 근거 -> {'hit@1': 1.0, 'recall@5': 0.6, ...}. 정답이 없으면 None."""
    if not gold:
        return None
    ranked = list(dict.fromkeys(retrieved))          # 같은 문서가 여러 번(청크 여러 개) 나오면 처음 것만
    gold = set(gold)
    out = {}
    for k in ks:
        found = gold & set(ranked[:k])
        out[f"hit@{k}"] = 1.0 if found else 0.0
        out[f"recall@{k}"] = len(found) / len(gold)
        out[f"all@{k}"] = 1.0 if found == gold else 0.0
        out[f"precision@{k}"] = len(found) / min(k, len(ranked)) if ranked else 0.0
    return out


def evaluate_retrieval(search_fn, questions, ks=KS, kb=None, docs=None, eval_names=None):
    """search_fn(question, pool) -> doc_id 목록. 반환: 유형별 평균 지표 + 문항별 결과 (결과 JSON에 넣기 좋게)."""
    kb = kb or load_kb()
    docs = docs or load_documents()
    eval_names = set(eval_names if eval_names is not None else load_evalset()["eval_characters"])
    name_to_doc = character_doc_ids(kb)
    known = {d["doc_id"] for d in docs}
    per_question, sums, counts = [], defaultdict(lambda: defaultdict(float)), defaultdict(int)
    for q in questions:
        pool = allowed_doc_ids(q, docs, eval_names)
        start = time.perf_counter()
        retrieved = list(search_fn(q["question"], pool))
        seconds = time.perf_counter() - start
        unknown_ids = [d for d in retrieved if d not in known]
        if unknown_ids:
            raise ValueError(f"{q['id']}: documents_ko.jsonl에 없는 doc_id {unknown_ids[:3]}")
        if pool is not None and any(d not in pool for d in retrieved):
            raise ValueError(f"{q['id']}: 학습용 질문인데 평가용 캐릭터 문서를 검색함 (pool 밖)")
        gold = q["gold_docs"] if "gold_docs" in q else gold_doc_ids(q, name_to_doc)
        s = score(retrieved, gold, ks)
        per_question.append({"id": q["id"], "type": q["type"], "question": q["question"], "gold_docs": gold,
                             "retrieved": retrieved[:max(ks)], "scores": s, "seconds": round(seconds, 4),
                             **({"note": q["note"]} if q.get("note") else {})})
        if s is not None:
            counts[q["type"]] += 1
            for m, v in s.items():
                sums[q["type"]][m] += v
                sums["all"][m] += v
            counts["all"] += 1
    by_type = {t: {m: round(v / counts[t], 4) for m, v in metrics.items()} for t, metrics in sums.items()}
    return {"n": len(questions), "scored": dict(counts), "ks": list(ks), "by_type": by_type,
            "avg_seconds": round(sum(p["seconds"] for p in per_question) / max(len(per_question), 1), 4),
            "per_question": per_question}


def print_report(report, metrics=("hit@1", "hit@5", "recall@5", "recall@10", "all@30", "precision@30")):
    print(f"문항 {report['n']}개 (채점 {report['scored'].get('all', 0)}개, unknown은 정답 근거가 없어 제외)"
          f", 평균 {report['avg_seconds'] * 1000:.1f}ms")
    print(f"{'유형':<8}" + "".join(f"{m:>13}" for m in metrics))
    for t in ("lookup", "filter", "all"):
        if t in report["by_type"]:
            row = report["by_type"][t]
            print(f"{t:<8}" + "".join(f"{row.get(m, float('nan')):>13.3f}" for m in metrics))


def by_note(report, metric="hit@1"):
    """말투 질문을 note(짧은 반말 / 존댓말 / 띄어쓰기 없음)별로 나눈 지표 평균."""
    groups = defaultdict(list)
    for p in report["per_question"]:
        if p["scores"] and p.get("note"):
            groups[p["note"]].append(p["scores"][metric])
    return {note: round(sum(v) / len(v), 4) for note, v in sorted(groups.items())}


def misses(report, metric="hit@1", max_items=10):
    """지표가 1이 아닌 문항 (검색 실패) 앞에서부터."""
    out = [p for p in report["per_question"] if p["scores"] and p["scores"].get(metric, 1.0) < 1.0]
    return out[:max_items]


# ─────────────────────────────────────────────────────────────
# 기준점: 지금 키워드 검색 (core/router.py + core/retrieval.py)
# ─────────────────────────────────────────────────────────────
def keyword_search_fn(kb=None, filter_mode=None):
    """filter_mode: None(챗봇 기본 = 'all') / 'any'(예전 rag~rag_v4 방식). core/retrieval.py FILTER_MODE 참고."""
    from core.retrieval import retrieve
    from core.router import Router
    kb = kb or load_kb()
    router = Router(kb)
    name_to_doc = character_doc_ids(kb)

    def search(question, pool):
        chars = kb.characters if pool is None else [c for c in kb.characters if name_to_doc[c["name"]] in pool]
        evidence = retrieve(router.route(question), kb, chars, filter_mode=filter_mode)
        return [name_to_doc[e["data"]["name"]] for e in evidence if e["kind"] == "character"]
    return search


def main(argv):
    if "--write" in argv:
        out = write_evidence()
        print(f"{EVIDENCE.relative_to(ROOT)} 저장: {len(out['evidence'])}문항, DEV {len(out['dev_ids'])}개")
        return 0
    kb = load_kb()
    search = keyword_search_fn(kb)
    for label, qs in (("DEV 60문항", dev_questions()), ("평가 115문항", eval_questions())):
        print(f"\n[키워드 검색 기준점 / {label}]")
        print_report(evaluate_retrieval(search, qs, kb=kb))
    print("\n[참고: 예전 filter 방식(any, rag~rag_v4) / DEV 60문항]")
    print_report(evaluate_retrieval(keyword_search_fn(kb, "any"), dev_questions(), kb=kb))
    print("\n[키워드 검색 기준점 / 말투 변형 질문 개발용 1,748문항]")
    report = evaluate_retrieval(search, csv_questions(STYLE_DEV, kb), kb=kb)
    print_report(report)
    print("말투별 hit@1:", by_note(report))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
