# Genshin Build Alchemist

원신 캐릭터 데이터를 묻고 답하는 **챗봇형 백과사전**에서 시작해, 패치 변경을 반영한 **빌드 가이드**까지 답하는 RAG 챗봇입니다.
오픈소스 LLM(Qwen2.5-3B-Instruct)에 질문에 맞는 근거를 찾아 함께 넘겨 주는 방식(RAG)으로 동작하고, 프롬프트와 검색을 개선하며 답변 품질을 단계별로 올립니다 (LoRA 파인튜닝은 하지 않기로 함).
단계: baseline → prompt_v2 → rag → rag_v3 → rag_v4 (같은 평가셋으로 비교, 결과는 JSON). 지금 챗봇은 rag_v4.

## 빠르게 실행해 보기 (GPU 없이 로컬 PC에서)

```bash
pip install -r requirements.txt && python3 -m unittest discover -s tests -t . && uvicorn api.main:app --reload
```

브라우저에서 http://127.0.0.1:8000/docs 를 열면 `/ask`에 질문을 직접 보내 볼 수 있습니다.
지금은 **모의 답변기**(근거에서 규칙으로 답을 뽑는 가짜 모델)가 붙어 있습니다. 실제 LLM은 코랩에서 연결합니다(아래).

## 폴더 구조와 담당

| 폴더 | 하는 일 | PRD | 담당 |
|---|---|---|---|
| `data/` | 캐릭터 126명, 무기 256개·성유물 63세트, 패치 변경 기록, 빌드 카드 | FR-01·02·06 | A. 데이터 |
| `collector/` | genshin-db 깃 이력에서 패치 변경 기록 추출 | FR-03·04 | A. 데이터 |
| `core/router.py` | 질문 종류 판별 (경로 5개) | FR-W1 | B. RAG |
| `core/retrieval.py` | 경로별 근거 검색 | RAG | B. RAG |
| `core/answer.py` | 모의 답변기 / LLM 답변기, 프롬프트 | - | C. 모델 실험 |
| `core/validate.py` | 빌드 카드 이름 검사, 패치 후 재확인 판정 | FR-06 | A. 데이터 |
| `core/pipeline.py` | 위를 이어 붙인 `ask()` → API 응답 형식 | FR-08 | B. RAG |
| `api/main.py` | FastAPI `POST /ask`, `GET /health` | FR-07 | D. 서비스 |
| `db/` | PostgreSQL 스키마, 캐릭터 시드 SQL 생성 | FR-09 | D. 서비스 |
| `notebooks/` | 코랩 단계별 평가, 프롬프트·모델 비교 (결과 JSON) | FR-E1~E3, FR-M1~M3 | C. 모델 실험 |
| `dashboard/` | 결과 JSON을 읽는 전후 비교 화면 | FR-E4 | D. 서비스 |
| `demo/` | Gradio 시연 화면 (코랩, 실제 모델) | FR-M4 | D. 서비스 |
| `tests/` | PRD 9장 테스트 시나리오 | 9장 | 전원 |

`notebooks/`, `dashboard/`, `demo/`는 다음 단계에서 채웁니다.

## 할 일 (TODO)

각자 할 일은 **작업할 파일 안에 `TODO(파트)` 주석**으로 적어 두었습니다. 위에서부터 순서대로 하고, 끝난 항목은 `[ ]`를 `[x]`로 바꿔 PR에 같이 올립니다. `[-]`는 하지 않기로 했거나 다른 파트로 넘긴 항목입니다.

| 파트 | 어디에 있나 |
|---|---|
| B. RAG | `core/retrieval.py` 맨 위 (벡터 검색), `core/router.py` (나중: 이름 인식) |
| C. 모델 실험 | `core/answer.py` 맨 위 (프롬프트 후처리, 모델 비교) |
| D. 서비스 | `api/main.py` 맨 위와 `ask()` 안 (DB, 웹 화면), `dashboard/README.md` |

찾는 법: VS Code에서 전체 검색(맥 `Cmd+Shift+F`, 윈도우 `Ctrl+Shift+F`)에 `TODO(B)`처럼 자기 파트를 넣으면 다 나옵니다.

## 작업 규칙

- **main에 직접 push하지 않습니다.** 각자 브랜치에서 작업하고 PR로 합칩니다.
- 브랜치 이름: `파트/작업내용` (예: `rag/embedding-search`, `model/model-compare`, `service/dashboard`)
- PR을 올리기 전에 테스트를 통과시킵니다: `python3 -m unittest discover -s tests -t .`
- 결과 JSON은 깃에 올리지 않고 구글 드라이브 팀 폴더 `results/`에 저장합니다.
- API 응답과 결과 JSON의 칸 이름은 바꾸지 말고 필요하면 추가만 합니다.
- AI(Claude, ChatGPT 등)에게 작업을 시킬 때는 [docs/AI_CONTEXT.md](docs/AI_CONTEXT.md)를 맨 앞에 붙여 넣습니다.

## 질문이 처리되는 흐름

```
질문 → router (경로 판별) → retrieval (근거 찾기) → answer (답 만들기) → API 응답
```

| 경로 | 예시 질문 | 근거 |
|---|---|---|
| lookup | 알베도 원소가 뭐야? | 그 캐릭터 문서 1개 |
| filter | 몬드 출신 5성 캐릭터 누구 있어? | 조건 키워드로 찾은 캐릭터 최대 30명 (모델이 조건을 직접 거름) |
| patch | 7.0에서 사유 뭐 바뀌었어? | 그 버전의 변경 기록 |
| build | 알베도 추천 성유물은? | 빌드 카드 + 무기·성유물 정보 + 재확인 표시 |
| unknown | 원신에서 제일 센 캐릭터는? | 없음 → **모델을 부르지 않고** "찾지 못했어요"라고 답함 |

## API 응답 형식

```json
{
  "question": "7.0에서 사유 뭐 바뀌었어?",
  "route": "patch",
  "answer": ["고유 특성 1", "명의 자리 4"],
  "message": "7.0 버전 사유의 바뀐 부분: 고유 특성 1, 명의 자리 4",
  "evidence": [{"kind": "patch", "title": "사유", "doc_id": "patch:7.0:constellations:sayu", "text": "7.0 사유: 명의 자리 수정, 바뀐 부분 = 명의 자리 4"}],
  "found": true,
  "needs_recheck": false,
  "model": "mock-rule",
  "method": "rag",
  "data_version": "8e5badd 2026-11-04 7.2 actual"
}
```

- `answer`는 평가(F1 채점)와 같은 목록 형식이고, 화면에는 `message`를 보여 줍니다.
- `evidence`의 `doc_id`는 검색용 문서 id입니다 (`data/docs/documents_ko.jsonl`, DB `documents` 표와 같은 규칙). 빌드 카드·재확인 표시처럼 문서가 아닌 근거는 `null`이고, 대화 기록의 `retrieved_doc_ids`에 저장됩니다.
- 칸 이름은 바꾸지 말고 필요하면 **추가만** 합니다 (팀 합의 사항).

## 빌드 카드 (FR-06)

1. `data/build_cards/_template.json`을 복사해 `캐릭터키.json`으로 저장하고 채웁니다 (예: `albedo.json`).
2. 아래 명령으로 검사합니다. 이름 오타, 무기 종류 불일치, 빈 칸, 패치 후 재확인 필요 여부를 알려 줍니다.

```bash
python3 -m core.validate
```

외부 가이드는 참고·링크만 하고, 내용은 직접 요약해서 씁니다. 이름이 `_`로 시작하는 파일은 양식이라 챗봇이 읽지 않습니다.

## DB (PostgreSQL + pgvector)

벡터 DB와 대화 기록을 PostgreSQL 하나에서 관리합니다. 코랩에서도 접속해야 해서 클라우드 DB(Supabase 또는 Neon)에 둡니다. 자세한 건 [db/README.md](db/README.md).

```bash
python3 db/make_seed.py && python3 db/make_documents_seed.py && psql "$DATABASE_URL" -f db/schema.sql && psql "$DATABASE_URL" -f db/seed_characters.sql && psql "$DATABASE_URL" -f db/seed_documents.sql
```

- `documents`: 검색용 문서 1,696개 (`data/docs/documents_ko.jsonl`), `chunks`: 청크 + 임베딩 `vector(768)`
- `characters`: 캐릭터 표, `chat_logs`: 대화 기록 (API 응답과 칸 이름을 맞춤)
- API에서 대화 기록을 DB에 저장하는 부분은 아직 연결하지 않았습니다 (`api/main.py`의 TODO).

## 실제 모델로 API 실행하기

API는 환경변수 `GBA_ANSWERER`로 답변기를 고릅니다. 기본(`mock`)은 규칙 기반 모의 답변기라 GPU 없이 돌고, `llm`이면 실제 모델(Qwen2.5-3B + rag_v4 프롬프트 + 후처리, 평가 macro F1 0.846과 같은 설정)을 씁니다. 다른 설정은 `core/llm.py` 맨 위에 있습니다.

**내 PC (맥 애플 실리콘, 메모리 8GB 이상 권장)**: 처음 한 번은 모델(약 6GB)을 내려받느라 몇 분 걸립니다.

```bash
pip install -r requirements.txt -r requirements-llm.txt && GBA_ANSWERER=llm uvicorn api.main:app
```

`/health`의 `model`이 `Qwen/Qwen2.5-3B-Instruct`면 실제 모델로 뜬 것입니다. 맥은 장치가 `mps`로 잡히고, 코랩(T4)과 숫자 계산 방식이 조금 달라 답이 드물게 다를 수 있습니다.

**코랩 (T4)**: 파이썬에서 바로 쓰기

```python
from core.kb import load_kb
from core.llm import answerer_from_env
from core.pipeline import Chatbot

bot = Chatbot(load_kb(), answerer_from_env({"GBA_ANSWERER": "llm"}))
bot.ask("알베도 원소가 뭐야?")
```

**코랩 + ngrok으로 API 띄우기 (D)**: 코랩 보안 비밀에 `NGROK_TOKEN`(ngrok 가입 후 받는 토큰)을 넣고, 저장소를 받은 셀 다음에 실행합니다.

```python
!pip -q install pyngrok
import os, subprocess, time
from google.colab import userdata
from pyngrok import ngrok

env = {**os.environ, "GBA_ANSWERER": "llm"}
api = subprocess.Popen(["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"],
                       cwd="/content/genshin-build-alchemist", env=env)
time.sleep(120)   # 모델 불러오는 시간. !curl -s localhost:8000/health 로 확인
ngrok.set_auth_token(userdata.get("NGROK_TOKEN"))
print("API 주소:", ngrok.connect(8000).public_url)   # 이 주소 + /docs 로 접속
```

## 패치 변경 기록 다시 모으기

```bash
cd collector && python3 collect_patchnotes.py --since 5.0 && cp out/patch_changes.json ../data/ && cd .. && python3 -m core.documents --fetch && python3 -m core.kb_data && python3 db/make_documents_seed.py && python3 db/make_seed.py
```

- 지금 데이터는 **5.0~7.2** (변경 기록 325건)입니다. 처음 실행할 때 genshin-db 저장소를 내려받느라 시간이 걸립니다.
- 표기만 바뀐 변경(성우 정보, 5.6의 일반 공격 이름 표기 102건 등)은 수집할 때 자동으로 거릅니다 (`collector/patchnotes/noise.py`). 5.0~7.2 기준 453건 → 325건
- 패치 기록을 바꾸면 검색 문서(`data/docs/documents_ko.jsonl`)와 DB 시드(`db/seed_documents.sql`)도 같이 다시 만듭니다 (위 명령에 포함)
- 캐릭터·무기·성유물 데이터(`data/characters_ko.json`, `data/items_ko.json`)는 `core/kb_data.py`가 같은 genshin-db 커밋(`core/documents.py`의 `DATA_COMMIT`, 지금 7.2)에서 만듭니다. 이 커밋을 바꾸면 평가셋도 새 버전(`info_v3` …)으로 만들어야 합니다 (`data/eval/README.md`)

## 데이터 출처

- [genshin-db](https://github.com/theBowja/genshin-db) (MIT), 한국어 데이터, 커밋 `8e5badd` (7.2)
- 최신 캐릭터 일부는 지역(8명)·원소(4명) 정보가 없어서 해당 질문은 답하지 않습니다.
