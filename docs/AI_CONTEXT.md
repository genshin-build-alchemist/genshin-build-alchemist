# AI 작업용 공통 컨텍스트 (Temp:ZERO)

> **사용법**: Claude, ChatGPT 같은 AI에게 이 프로젝트 작업을 시킬 때, 이 문서 전체를 대화 맨 앞에 붙여 넣고 그 아래에 요청을 적습니다.
> 맨 아래 "요청 템플릿"을 쓰면 더 정확한 답을 받을 수 있습니다.
> 이 문서는 팀 공용입니다. 내용이 바뀌면 PR로 고칩니다.

---

## 1. 프로젝트 한 줄 요약

원신 캐릭터 데이터를 묻고 답하는 **RAG 챗봇**. 캐릭터 정보 조회에서 시작해 패치 변경 분석, 빌드 가이드까지 답한다.
오픈소스 LLM(**Qwen2.5-3B-Instruct**)에 질문에 맞는 근거를 찾아 함께 넘기고, 프롬프트 개선과 **LoRA 파인튜닝**으로 답변 품질을 단계별로 올린다.

- 팀: 4명, 기간 4주, 실험 환경은 **구글 코랩 T4** (fp16, bf16 안 됨)
- 과제 기준: LLM 기본 모델 구축·배포 / 파인튜닝 데이터 준비·최적화 / 프롬프트 엔지니어링 / LLM 답변 품질 평가·개선
- 개선 단계: `baseline → prompt_v2 → rag → rag_v3 → rag_v4 → rag_v5 → rag+lora` (같은 평가셋으로 비교, 결과는 JSON)

## 2. 역할

| 파트 | 하는 일 | 주로 만지는 곳 |
|---|---|---|
| A. 데이터 (+메인 코드 관리) | 수집, 평가셋, 파인튜닝 데이터, 빌드 카드 | `data/`, `collector/`, `core/validate.py` |
| B. RAG | 라우터, 검색, 출처 메타데이터 | `core/router.py`, `core/retrieval.py`, `core/pipeline.py` |
| C. 모델 실험 | 프롬프트, 파인튜닝 데이터, LoRA 학습, 코랩 실험 | `core/answer.py`, `notebooks/` |
| D. 서비스·대시보드 | FastAPI, Gradio 시연, DB, 전후 비교 대시보드 | `api/`, `db/`, `dashboard/`, `demo/` |

## 3. 폴더 구조

```
core/        kb.py(데이터 로드) router.py(경로 판별) retrieval.py(근거 검색)
             answer.py(모의/LLM 답변기, 프롬프트) validate.py(빌드 카드 검사) pipeline.py(ask)
api/         main.py  FastAPI: POST /ask, GET /health
db/          schema.sql(PostgreSQL + pgvector: documents, chunks vector(768), chat_logs), make_*seed.py, queries.sql
data/        characters_ko.json(124명) items_ko.json(무기 255, 성유물 63)
             patch_changes.json(패치 변경 기록) build_cards/(빌드 카드, _로 시작하면 양식)
collector/   genshin-db 깃 이력에서 패치 변경 추출
notebooks/   코랩 평가·학습 노트북
dashboard/   결과 JSON을 읽는 전후 비교 화면 (Streamlit)
demo/        Gradio 시연 화면
tests/       PRD 9장 테스트 시나리오
```

데이터 출처: genshin-db (MIT), 한국어, 커밋 `49a6544` (7.1). 최신 캐릭터 일부는 지역(13명)·원소(4명) 정보가 없다.

## 4. 질문 처리 흐름

```
질문 → router(경로 판별) → retrieval(근거 찾기) → answer(답 만들기) → API 응답
```

| 경로 | 예시 | 근거 |
|---|---|---|
| lookup | 알베도 원소가 뭐야? | 그 캐릭터 문서 1개 |
| filter | 몬드 출신 5성 캐릭터 누구 있어? | 조건을 모두 만족하는 캐릭터 (`FILTER_MODE = "all"`, 예전 실험 재현은 `"any"`) |
| patch | 7.0에서 사유 뭐 바뀌었어? | 그 버전의 변경 기록 |
| build | 알베도 추천 성유물은? | 빌드 카드 + 무기·성유물 정보 + 재확인 표시 |
| unknown | 원신에서 제일 센 캐릭터는? | 없음 → **모델을 부르지 않고** "찾지 못했어요" |

- 이름 매칭은 경계 정규식으로 한다. 한 글자 이름(소, 진)이 단어 안에서 잡히면 안 된다 ("원소"의 "소" X).
- 패치 단어가 있으면 patch 경로가 우선한다.

## 5. 고정된 형식 (칸 이름 바꾸지 말 것, 필요하면 추가만)

### API 응답 (`POST /ask`)

```json
{
  "question": "7.0에서 사유 뭐 바뀌었어?",
  "route": "patch",
  "answer": ["고유 특성 1", "명의 자리 4"],
  "message": "7.0 버전 사유의 바뀐 부분: 고유 특성 1, 명의 자리 4",
  "evidence": [{"kind": "patch", "title": "사유", "text": "..."}],
  "found": true,
  "needs_recheck": false,
  "model": "mock-rule",
  "method": "rag",
  "data_version": "49a6544 2026-09-21 7.1 assemble"
}
```

- `answer`는 채점용 목록, 화면에는 `message`를 보여 준다.
- `found=false`면 `answer`는 `[]`.

### 결과 JSON (실험 1회 = 파일 1개, 드라이브 `results/{experiment_id}.json`)

```json
{
  "experiment_id": "info13_rag_v3",
  "method": "rag_v3",
  "model": "Qwen/Qwen2.5-3B-Instruct",
  "dataset_version": "...",
  "created_at": "2026-11-03T10:00:00",
  "seconds": 312.4,
  "limit": null,
  "config": {},
  "metrics": {"n": 115, "macro_f1": 0.0, "micro_precision": 0.0, "micro_recall": 0.0, "micro_f1": 0.0, "empty_answers": 0,
              "avg_seconds": 0.0, "max_seconds": 0.0},
  "by_type": {},
  "by_field": {},
  "per_question": [{"id": "...", "question": "...", "type": "lookup", "field": "element", "gold": [], "pred": [], "raw": "...", "f1": 1.0, "seconds": 1.2}],
  "notes": ""
}
```

- `method` 값: `baseline` / `prompt_v2` / `rag` / `rag_v3` / `rag+lora`
- `per_question.raw`에는 모델 원문을 그대로 남긴다 (오답 분석용).

## 6. 꼭 지킬 규칙

1. **근거가 없으면 모델을 부르지 않는다.** 지어내지 않는 게 이 프로젝트의 핵심이다.
2. **학습/평가 분리**: 평가용 캐릭터(22명)는 프롬프트 예시, 파인튜닝 데이터 어디에도 넣지 않는다. 캐릭터 단위로 나눈다.
3. **사람이 만든 질문**은 평가에만 쓴다. 학습·프롬프트 고르기에 쓰지 않는다.
3-1. **평가셋은 고정본**(`data/eval/questions_info_v1.json`, 지문 sha256 `2e5f5437…`)을 쓴다. 파일을 손으로 고치지 않고, 생성 규칙을 바꾸려면 `DATASET_VERSION`을 올린다.
3-2. **프롬프트·설정은 DEV 세트(학습 질문 60개)로만 고른다.** 평가 115문항과 사람 질문은 최종 버전을 한 번 돌릴 때만 본다.
4. 정답은 **집합 F1**로 채점한다 (macro F1이 주 지표). 보조 지표: 거절 정확도, 환각률, 검색 Hit@k, 경로 판별 정확도.
5. 빌드 카드는 외부 가이드를 복사하지 않고 팀이 요약해서 쓴다. 출처 링크와 확인 버전을 꼭 적는다.

## 7. 코드 규칙

- Python 3.10 이상. 테스트는 표준 `unittest` (`python3 -m unittest discover -s tests -t .`)
- 새 기능에는 테스트를 같이 추가하고, PR 전에 전체 테스트를 통과시킨다.
- 주석과 docstring은 한국어로 짧게.
- 코랩 코드: T4라서 `torch_dtype=torch.float16`. 결과와 체크포인트는 드라이브에 저장 (세션이 끊겨도 남게).
- 드라이브 경로는 띄어쓰기가 있어서 따옴표로 감싼다: `"/content/drive/MyDrive/Genshin Build Alchemist (팀)/results"`
- 비밀값(API 키, DB 비밀번호)은 코드에 쓰지 않고 `.env`에 둔다.

## 8. 깃 규칙

- main에 직접 push하지 않는다. 브랜치 `파트/작업내용` (예: `rag/embedding-search`) → PR.
- 파트별 할 일은 코드 안 `TODO(B)`, `TODO(C)`, `TODO(D)` 주석에 있다. 끝낸 항목은 `[x]`로 바꿔 같은 PR에 올린다.
- 결과 JSON, LoRA 체크포인트(`*.safetensors`, `*.bin`), 캐시는 깃에 올리지 않는다 (.gitignore에 있음).

## 9. AI에게 부탁할 때 주의

- 위 형식의 **칸 이름을 바꾸거나 빼는 코드**를 받으면 그대로 쓰지 말고 다시 요청한다.
- 파일을 고칠 때는 **바뀐 부분만이 아니라 파일 전체 코드**를 달라고 한다 (붙여 넣다가 꼬이는 걸 막기 위해).
- 모르는 라이브러리 버전이나 함수는 지어낼 수 있으니, 받은 코드는 꼭 실행해 보고 테스트를 돌린다.

---

## 요청 템플릿

```
[내 파트] B. RAG / C. 모델 실험 / D. 서비스·대시보드 중 하나
[할 일] 무엇을 만들거나 고치고 싶은지
[관련 파일] 예: core/retrieval.py (파일 내용을 아래에 붙여 넣음)
[조건] 예: 기존 테스트 통과 유지, API 응답 칸 이름 유지
[원하는 결과] 예: 파일 전체 코드 + 추가할 테스트 코드
```
