# 고정 평가셋 (data/eval)

모든 실험(baseline → prompt_v2 → rag → rag_v3 → rag+lora)은 **같은 질문 목록**으로 채점해야 점수를 비교할 수 있습니다.
그래서 질문 목록을 한 번 만들어 고정하고, 지문(sha256)으로 바뀌지 않았는지 확인합니다.

## 현재 고정본

| 항목 | 값 |
|---|---|
| 파일 | `questions_info_v1.json` |
| dataset_version | `info_v1` |
| 지문 (sha256) | `2e5f54373b7ba38551cf401042df1efcde916fba2e0f9df48462c2f3cb5b50c7` |
| 데이터 | genshin-db 한국어 `49a6544` (7.1), 캐릭터 124명 |
| 질문 수 | 611개 = 학습 496 (lookup 397, filter 91, unknown 8) + 평가 115 (lookup 82, filter 25, unknown 8) |
| 평가용 캐릭터 | 22명 (`eval_characters`), 학습용 질문의 정답·캐릭터에 나오지 않음 |

지문은 `questions` 목록을 `json.dumps(qs, ensure_ascii=False, sort_keys=True, separators=(",", ":"))`로 바꾼 뒤 sha256을 구한 값입니다.
키 순서나 들여쓰기가 달라도 내용이 같으면 같은 지문이 나옵니다.

## 어디에 있나

- **저장소** `data/eval/questions_info_v1.json`: 유일한 원본. 테스트(`tests/test_evalset.py`, `tests/test_eval_routing.py`)가 지문, 분리 규칙, 라우터·검색 결과를 검사합니다.
- 노트북(`notebooks/01_eval_info.ipynb`)은 셀 1에서 저장소를 받아 와 이 파일을 읽고, 지문이 다르면 멈춥니다.
- 새 버전 고정본이 아직 저장소에 없을 때만 노트북이 만들어 드라이브 `data/`에 저장합니다. 그 파일을 PR로 이 폴더에 올립니다.

## 규칙

1. **고정본 파일을 손으로 고치지 않습니다.** 고치면 노트북과 테스트가 바로 멈춥니다.
2. 평가 문항(`split: eval`)과 평가용 캐릭터는 프롬프트 예시, 파인튜닝 데이터에 쓰지 않습니다.
3. 질문 생성 규칙이나 데이터를 바꿔야 하면 **새 버전**을 만듭니다.
   - 노트북의 `DATASET_VERSION`을 `info_v2`로 올리고 `EXPECTED_SHA256`을 새 지문으로 바꿉니다.
   - 새 파일 `questions_info_v2.json`을 저장소에 추가하고 이 README와 테스트의 지문을 고칩니다.
   - 이전 버전 결과와 새 버전 결과는 점수를 직접 비교하지 않습니다 (결과 JSON의 `dataset_version`으로 구분).
4. 사람이 만든 질문(`human_questions.csv`)은 이 파일과 따로 관리하고, 평가에만 씁니다.

## 사람이 만든 질문 (human_questions.csv)

자동 생성 질문은 문장이 정형화돼 있어서, 실제 유저 말투(줄임말, 오타, 별명)를 라우터가 알아듣는지는 사람 질문으로 확인합니다.

**쓰는 사람은 질문과 target만 적습니다. 정답은 데이터에서 자동으로 채웁니다.**
양식: `human_questions_template.csv` (구글 스프레드시트에서 써도 되고, 다 쓰면 CSV로 내려받기)

| question | target | 정답 (자동) |
|---|---|---|
| 알베도 속성 뭐임? | `알베도/원소` | 바위 |
| 몬드 5성 누구누구 있어? | `지역=몬드, 성급=5성` | 다이루크, 두린, ... |
| 원신에서 제일 센 캐릭터는? | (빈칸) | [] |

- target 항목 이름: 원소, 무기, 성급, 지역. 값은 `5`, `5성급`, `불원소`, `몬드 출신`처럼 써도 맞춰 줍니다.
- 질문 문장은 해석하지 않고 target만 봅니다. 그래서 라우터가 질문을 잘못 알아들어도 정답이 오염되지 않습니다.
- 다 쓴 CSV를 드라이브 `data/human_questions.csv`로 올리면 노트북 셀 12가 정답을 채워 평가합니다. 이름 오타 같은 오류 줄은 "혹시: 알베도" 식으로 알려 주고 평가에서 뺍니다.
- 미리 확인하려면: `python3 -m core.human_questions human_questions.csv` → `human_questions_filled.csv`와 오류 목록
