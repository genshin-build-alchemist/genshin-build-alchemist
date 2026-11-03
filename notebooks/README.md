# notebooks (FR-E1~E3, FR-M1~M3 · C. 모델 실험)

코랩에서 돌리는 평가·학습 노트북을 둡니다. 결과 JSON은 깃이 아니라 구글 드라이브 팀 폴더 `results/`에 저장됩니다.

## 노트북 목록

| 파일 | 하는 일 | 상태 |
|---|---|---|
| `01_eval_info.ipynb` | 1단계 캐릭터 정보 평가: 질문 611개 자동 생성, 라우터·검색, baseline · prompt_v2 · rag · rag_v3 비교, 사람 질문 평가, 파인튜닝용 질문 파일 저장 | 사용 가능 |
| `02_finetune_data.ipynb` | 파인튜닝 데이터셋 정제 ("근거 + 질문 → 정답", 평가셋과 분리) | 예정 |
| `03_lora_train.ipynb` | LoRA 학습과 rag+lora 평가 | 예정 |
| `04_gradio_demo.ipynb` | 실제 모델 Gradio 시연 (D) | 예정 |

## 01_eval_info.ipynb 쓰는 법

1. 드라이브 팀 폴더 `Genshin Build Alchemist (팀)`을 우클릭 → 정리 → 바로가기 추가 → 내 드라이브 (처음 한 번만)
2. 코랩에서 이 노트북 열기: 파일 → 노트북 열기 → GitHub 탭 → 저장소 주소 입력 (비공개라 GitHub 로그인 필요). 또는 파일을 내려받아 업로드
3. 런타임 → 런타임 유형 변경 → T4 GPU
4. 위에서부터 차례로 실행. 드라이브 연결을 허용하면 `data/characters_ko.json`을 읽고 결과를 `results/`에 저장
5. 셀 2에서 "고정 평가셋 저장" 또는 "고정 평가셋 사용"이 나와야 정상 (처음 실행한 사람이 드라이브에 `data/questions_info_v1.json`을 만들고, 그다음부터는 모두 그 파일을 읽음)
6. 셀 5(가짜 모델 점검)에서 oracle 점수가 1.0이 나와야 파이프라인이 정상

주의
- 평가셋은 고정돼 있습니다 (`data/eval/README.md`). 셀 2에서 지문이 다르다고 멈추면 고정본 파일이 바뀐 것이니 손대지 말고 알려 주세요.
- 파인튜닝용 학습 질문은 셀 13에서 드라이브 `data/train_questions_info_v1.json`으로 저장됩니다.
- 같은 `experiment_id`로 다시 돌리면 드라이브의 결과 파일을 덮어씁니다. 남기고 싶으면 ID를 바꿉니다.
- 처음에는 셀 10의 `LIMIT = 20`으로 시간을 재 보고, 괜찮으면 `None`(전체 115문항)으로 돌립니다.
- 코랩에서 고친 노트북은 "드라이브에 사본 저장" 후 내려받아 PR로 올립니다 (main 직접 push 금지).

## 다음에 할 일

- 노트북의 라우터·검색을 `core.router` / `core.retrieval`을 가져다 쓰도록 정리합니다. 노트북 평가와 실제 챗봇(FastAPI)이 같은 코드를 써야 점수와 동작이 어긋나지 않습니다.
- 결과 JSON의 칸 이름은 바꾸지 말고 추가만 합니다. 샘플은 드라이브 `results/sample01_random.json`, `sample02_oracle.json` (가짜 모델, 형식 확인용).
