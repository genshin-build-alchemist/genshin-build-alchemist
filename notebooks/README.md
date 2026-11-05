# notebooks (FR-E1~E3, FR-M1~M3 · C. 모델 실험)

코랩에서 돌리는 평가·학습 노트북을 둡니다. 결과 JSON은 깃이 아니라 구글 드라이브 팀 폴더 `results/`에 저장됩니다.

노트북은 라우터·검색·데이터를 **저장소의 `core/`, `data/`에서 그대로 가져다 씁니다.** 셀 1이 코랩에 저장소를 받아 옵니다.
그래서 노트북 평가와 실제 챗봇(FastAPI)이 같은 코드로 동작하고, 라우터·검색을 고칠 때는 노트북이 아니라 `core/`를 고쳐 PR로 올립니다.

## 노트북 목록

| 파일 | 하는 일 | 상태 |
|---|---|---|
| `01_eval_info.ipynb` | 1단계 캐릭터 정보 평가: 고정 평가셋(611문항), baseline · prompt_v2 · rag · rag_v3 · rag_v4 비교, 사람 질문 평가, 파인튜닝용 학습 질문 저장 | 사용 가능 |
| `02_model_compare.ipynb` | 모델 비교: rag_v4 프롬프트 고정, 모델만 바꿔 DEV로 macro F1·응답 시간 비교 | 예정 |
| `04_gradio_demo.ipynb` | 실제 모델 Gradio 시연 (D) | 예정 |

## 처음 한 번만 하는 준비

1. **드라이브 바로가기**: 팀 폴더 `Genshin Build Alchemist (팀)` 우클릭 → 정리 → 바로가기 추가 → 내 드라이브
2. **GitHub 토큰** (저장소가 비공개라 코랩에서 코드를 받을 때 필요. 공개로 바뀌면 필요 없음)
   - GitHub → Settings → Developer settings → Personal access tokens → **Fine-grained tokens** → Generate new token
   - Resource owner: `genshin-build-alchemist`, Repository access: `genshin-build-alchemist`만, Permissions → Contents: **Read-only**
   - 조직 설정 때문에 fine-grained 토큰이 막히면 Tokens (classic)에서 `repo` 권한으로 만들어도 됩니다
   - 코랩 왼쪽 **열쇠 아이콘(보안 비밀)** → 새 보안 비밀 추가 → 이름 `GITHUB_TOKEN`, 값에 토큰 붙여 넣기 → **노트북 액세스 켜기**
   - 토큰은 코드나 노트북 셀에 직접 쓰지 않습니다 (노트북은 출력에서도 토큰을 가립니다)

## 01_eval_info.ipynb 쓰는 법

1. 코랩에서 노트북 열기: 파일 → 노트북 열기 → GitHub 탭 → 저장소 선택 (비공개라 GitHub 로그인 필요). 또는 파일을 내려받아 업로드
2. 런타임 → 런타임 유형 변경 → T4 GPU
3. 위에서부터 차례로 실행
   - 셀 1: `저장소 코드: ... (main @ 커밋)`, `팀 드라이브 사용`이 나와야 정상
   - 셀 2: `고정 평가셋 사용: .../data/eval/questions_info_v1.json (지문 2e5f54373b7b)`가 나와야 정상
   - 셀 5: 가짜 모델 점검에서 oracle 점수가 1.0이 나와야 정상
4. 셀 10: 처음에는 `LIMIT = 20`으로 시간을 재 보고, 괜찮으면 `None`(전체 115문항)으로 다시 실행

## 프롬프트 개선할 때 (DEV 세트)

- 새 프롬프트(예: rag_v4)는 셀 7의 `METHODS`와 `make_prompt()`에 추가하고, **셀 10-1에서 DEV 세트(학습 질문 60개)로만 비교**합니다. 결과는 `results/dev_*.json`
- DEV에서 고른 최종 프롬프트만 셀 10에서 평가 115문항으로 **한 번** 돌립니다. 평가 결과나 사람 질문 결과를 보고 프롬프트를 다시 고치지 않습니다 (PRD 4.3).
- DEV 세트는 학습용 질문에서 few-shot 예시를 빼고 해시 순서로 뽑아서, 누가 돌려도 같은 60문항입니다 (lookup 항목별 10, filter 16, unknown 4).
- 새 예시를 더할 때는 DEV와 겹치지 않는 학습용 질문에서 고릅니다 (예: rag_v4의 `few_shot_v4()`). 셀 8이 겹침을 검사합니다.

### 프롬프트 실험 기록

| 방법 | 바꾼 것 | DEV macro F1 | 평가 115문항 macro F1 | 결과 파일 |
|---|---|---|---|---|
| rag_v3 | (기준) 예시 3개에 근거를 붙임 | 0.486 | 0.563 | `results/baseline/info13_rag_v3.json` |
| rag_v4 | 성급·지역 예시 1개씩 추가, 규칙 2줄 추가 (근거의 5성/4성 = 성급, '지역' = 출신 지역 / 조건 모두 만족) | 0.814 | 0.845 | `results/dev_rag_v4.json`, `results/info14_rag_v4.json` |
| rag_v4+post | rag_v4 모델 원문에 후처리: 근거에 있는 이름·값으로 맞추기 (cutoff 0.6), 근거에 없는 이름은 버림 | 0.816 | 0.846 | `results/dev_rag_v4_post.json`, `results/info14_rag_v4_post.json` |


- rag_v4: 캐릭터 조회 82문항 전부 정답 (성급 0.08 → 1.0, 지역 0.50 → 1.0). 조건 검색은 0.309 → 0.288로 개선되지 않음.
- 조건 검색은 근거 문서가 평균 29개(최대 30개)라서, 조건에 안 맞는 캐릭터까지 답에 섞이는 것이 남은 문제입니다. 프롬프트만으로 줄일지, 검색에서 근거를 미리 줄일지 확인이 필요합니다.
- 결과 JSON에는 질문별 응답 시간(`per_question[].seconds`)과 평균·최대 시간(`metrics.avg_seconds`, `max_seconds`)이 남습니다.
- rag_v4+post: 이름 오류를 바로잡음 (DEV 4건, 평가 9건: 일본어 섞임 '라이デン 쇼군', 오타 '쿠피시노부'·'네프르', 지어낸 이름 '베티'·'세탄'·'세타'). 잘못 바꾼 경우 0건. 틀린 이름 대부분이 원래 정답이 아닌 캐릭터라 점수 변화는 작음 (평가 0.8453 → 0.8455).

주의
- 평가셋은 고정돼 있습니다 (`data/eval/README.md`). 셀 2에서 지문이 다르다고 멈추면 고정본이 바뀐 것이니 손대지 말고 알려 주세요.
- 결과 JSON의 `config.code_version`에 어느 브랜치·커밋 코드로 돌렸는지 자동으로 남습니다.
- PR 브랜치의 코드로 평가해 보고 싶으면 셀 1의 `REPO_BRANCH`를 그 브랜치 이름으로 바꿉니다.
- 사람이 만든 질문은 드라이브 `data/human_questions.csv`에 두면 셀 12가 평가합니다. `question,target` 형식이면 정답을 데이터에서 자동으로 채웁니다 (`data/eval/README.md`).
- 셀 13은 학습용 질문을 드라이브 `data/train_questions_info_v1.json`으로 저장합니다. LoRA는 하지 않기로 해서 지금은 참고용입니다.
- 같은 `experiment_id`로 다시 돌리면 드라이브의 결과 파일을 덮어씁니다. 남기고 싶으면 ID를 바꿉니다.
- 코랩에서 고친 노트북은 "드라이브에 사본 저장" 후 내려받아 PR로 올립니다 (main 직접 push 금지).

## 로컬에서 돌리기 (GPU 없이 셀 1~5, 8~9 점검)

저장소 안에서 주피터로 열면 셀 1이 저장소를 자동으로 찾습니다. 다른 위치에서 열 때는 `GBA_REPO` 환경변수에 저장소 경로를 넣습니다.

## 라우터·검색을 고칠 때

`tests/test_eval_routing.py`가 고정 평가셋 611문항을 `core/` 라우터·검색으로 돌려서 경로가 맞는지, 검색 결과에 정답이 다 들어 있는지(점수 상한 1.0)를 확인합니다.
`core/`를 고친 PR은 이 테스트를 통과해야 합니다.
