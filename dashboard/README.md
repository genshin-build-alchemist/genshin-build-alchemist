# dashboard (FR-E4, 서비스 담당 D)

챗봇 성능 개선 과정을 결과 JSON으로 비교해 보여주는 Streamlit 대시보드입니다.
화면 설계는 `docs/dashboard/genshin_dashboard_wireframe.html`(와이어프레임 확정본)을 따릅니다.

- **숫자는 전부 결과 JSON에서 읽습니다.** 화면 코드에 점수·시간을 직접 쓰지 않습니다.
- **글(요약, 발견, 결정 사항)은 `content/` 폴더의 YAML에 둡니다.** 글 안의 숫자는 사람이 직접 쓰고, 어떤 데이터를 보고 썼는지 `based_on`에 남깁니다 (3-3).
- 코랩·GPU·DB·비밀값 없이 결과 JSON만으로 동작합니다.

---

## 1. 폴더 구조

```
dashboard/
├── app.py                  # 진입점: 머리말 + 탭 4개
├── summary.py              # 주요 수치 요약표 출력 (yaml 글을 다시 쓸 때 참고)
├── requirements.txt        # streamlit, plotly, pyyaml
├── README.md               # 이 문서
├── lib/
│   ├── loader.py           # JSON 읽기 · 검증 · 지표 계산 (화면과 분리)
│   ├── text.py             # content/*.yaml 읽기
│   ├── charts.py           # Plotly 그래프 함수 (그래프 모양 숫자는 맨 위 상수, 3-4)
│   └── ui.py               # 다크 CSS · 숫자 카드 · 💡 요약 상자 · 실험 기록 · 툴팁 스크립트 같은 공통 부품
├── content/                # 사람이 쓰는 글과 수동 값 (JSON에 없는 것)
│   ├── stages.yaml         # 단계 순서 · 표시 이름 · 개선점/알게 된 것/문제점
│   ├── performance.yaml    # ① 성능 변화 글
│   ├── response_time.yaml  # ② 응답 시간 글 + 실험 조건
│   ├── aux.yaml            # ③ 보조 지표 글 + 지표 정의
│   └── model_compare.yaml  # ④ 모델 비교 글 + GPU 메모리 같은 수동 값
├── data/                   # 결과 JSON (드라이브 results/에서 복사)
│   ├── official/           # ① 공식 평가 문항 결과
│   ├── dev/                # ② DEV 60문항 결과 (응답 시간)
│   ├── aux/                # ③ 보조 지표 결과
│   └── model_compare/      # ④ 모델·GPU·정밀도 비교 결과
└── tests/
    ├── test_loader.py      # 검증 규칙 · 계산 테스트
    ├── test_text.py        # yaml 읽기 · based_on 테스트
    ├── test_charts.py      # 그래프 구성 · 툴팁 내용 테스트
    └── test_ui.py          # 화면 부품 + app.py 실행 테스트 (브라우저 없이 탭 4개의 카드·표 값 확인)
```

## 2. 데이터 파일 규칙

### 2-1. 어떤 파일을 어디에 넣나

| 폴더 | 쓰는 탭 | 드라이브 원본 위치 | 파일 이름 (예) | `dataset_version` |
|---|---|---|---|---|
| `data/official/` | ① 성능 변화 | `results/` | `info10_baseline-V2.json` ~ `info14_rag_v4-V2.json` | `info_v2` |
| `data/dev/` | ② 응답 시간 | `results/` | `dev_baseline-V2.json` ~ `dev_rag_v4-V2.json` | `info_v2-dev` |
| `data/aux/` | ③ 보조 지표 | `results/aux/` | `aux_dev_baseline-V2.json` ~ `aux_dev_rag_v4-V2.json` | `info_v2-dev` |
| `data/model_compare/` | ④ 모델 비교 | `results/Model compare/` | `dev_rag_v4_qwen2.5-3b-fp16-L4.json` | `info_v1-dev` |

### 2-2. 지켜야 할 규칙

1. **결과 JSON은 손으로 고치지 않습니다.** 드라이브에서 복사만 합니다. 잘못된 값은 실험 담당(C)에게 다시 받아요.
   `data/`의 JSON은 배포에 필요해서 **팀 합의로 깃에 올립니다** (팀 규칙 8장의 예외, `data/README.md` 참고).
2. **한 폴더 안의 파일은 `dataset_version`이 모두 같아야 합니다.** 다르면 화면 위에 빨간 경고가 뜹니다.
3. **`limit`이 `null`인 파일만 씁니다.** `limit: 20` 같은 테스트 실행 파일은 자동으로 빠지고 경고가 뜹니다.
4. **후처리 파일(`_post`가 붙은 것)은 ①~③에서 쓰지 않습니다.** 폴더에 있어도 무시합니다. ④는 후처리 전 파일만 씁니다. `.gitignore`에 등록되어 있어 깃에도 올라가지 않습니다.
5. **단계는 파일 이름이 아니라 JSON의 `method` 값으로 구분합니다.** (`baseline`, `prompt_v2`, `rag`, `rag_v3`, `rag_v4` …)
6. **같은 `method`가 한 폴더에 두 개 있으면** `created_at`이 늦은 파일을 쓰고 경고를 띄웁니다.
7. **④ 모델 비교의 모델·GPU·정밀도는 `experiment_id`에서 읽습니다.** 형식: `dev_rag_v4_qwen2.5-{크기}-{정밀도}-{GPU}`. 대소문자는 구분하지 않습니다 (`l4`, `L4` 모두 됨).

### 2-3. 자동 검증 (그 폴더를 쓰는 탭의 탭 줄 아래에 표시, 문제가 없으면 아무것도 안 보임)

`lib/loader.py`가 파일을 읽을 때 확인합니다.

| 검사 | 실패하면 |
|---|---|
| `limit`이 `null`인가 (aux는 `limit`·`per_question` 칸이 없어서 검사 안 함) | 그 파일 제외 + 노란 경고 |
| 폴더 안 `dataset_version`이 같은가 | 빨간 경고 |
| `metrics.n`이 `per_question` 개수와 같은가 | 노란 경고 |
| `per_question`의 F1 평균을 다시 계산하면 `metrics.macro_f1`과 같은가 | 노란 경고 |
| yaml의 `based_on.created_at`이 지금 데이터와 같은가 (3-3) | 그 탭에 회색 안내 |

## 3. 화면에 나오는 값은 어디서 오나

### 3-1. JSON에서 자동으로 계산하는 값

| 값 | 계산 방법 |
|---|---|
| Macro F1, 유형별 점수 | `metrics.macro_f1`, `by_type.{lookup,filter,unknown}.macro_f1` |
| 평균·최대 응답 시간 | `metrics.avg_seconds`, `metrics.max_seconds`, `by_type.*.avg_seconds` |
| 중앙값 응답 시간 | `per_question[].seconds`의 중앙값 (JSON에 없어서 직접 계산) |
| 빈 답 수 | `metrics.empty_answers` |
| 정밀도·재현율 | `metrics.micro_precision`, `metrics.micro_recall` |
| 조건 검색 평균 답 길이 | 조건 검색 문항의 `len(pred)` 평균 |
| 정답률 · 거절 정확도 · 환각률 · 답한 문항 · 환각 건수 | aux JSON의 `metrics` |
| 유형별 환각 건수 | aux JSON `hallucinations[].id`의 앞부분(`lookup_`, `filter_`, `unknown_`)으로 분류. `hallucinations` 칸이 없는 단계만 ③ c3c에 점선 "유형 구분 없음" |
| 빈 답 ↔ 응답 시간 상관계수 | 단계별 (빈 답 수, 평균 응답 시간)로 피어슨 r 계산 |
| 숫자 카드의 1위 모델 | ④ `baseline_setup`(L4·fp16) 조합 중 최고값을 자동 선택 (소수 3자리로 같으면 함께 표시) |
| 실험 조건의 코드·모델·평가셋·생성 설정 | `config.code_version`, `model`, `dataset_version`, `config.max_new_tokens` |

**표시 규칙:** 소수점은 3자리까지 반올림. 원래 3자리 이하면 그대로 (`1.0`, `6.59`).

### 3-2. JSON에 없어서 `content/`에 직접 쓰는 값

| 값 | 파일 | 바뀌는 경우 |
|---|---|---|
| 단계 순서 · 표시 이름 | `stages.yaml` | 새 단계 추가 |
| 단계별 개선점 · 알게 된 것 · 문제점 | `stages.yaml` | 새 단계 추가, 보고서 수정 |
| 탭 상단 요약 · 💡 요약 · 주요 발견 · 다음 과제 | 탭별 yaml | 결론이 바뀔 때 |
| 조건 표시 문구 (노란 칸) | 탭별 yaml | 실험 조건이 바뀔 때 |
| ② 실험 조건 중 GPU 종류 · 실행 시각 · 실행 순서 · 준비 실행 | `response_time.yaml` | 응답 시간 재측정 |
| ③ 지표 정의 문구 | `aux.yaml` | 지표 정의 변경 |
| ④ GPU 메모리 (1.5B 2.9GB / 3B 5.8GB / 7B 5.5~14.2GB) | `model_compare.yaml` | 모델 비교 재실험 |
| ④ 최종 선택 모델 · 팀 결정 사항 · 문제점 | `model_compare.yaml` | 팀 결정 변경 |

각 수동 값 옆에는 **출처(보고서 이름·날짜)를 주석으로** 적습니다.

```yaml
manual:
  gpu_memory:            # 출처: 디스코드 모델 비교 보고서 (11/6, 임준규)
    1.5B: "2.9GB"
    3B: "5.8GB"
    7B: "5.5~14.2GB"
```

### 3-3. 글 속 숫자는 직접 쓰고, `based_on`으로 확인

결론 문장은 단계가 추가될 때마다 사람이 다시 씁니다. 그래서 **글 속 숫자는 자리표시 없이 값을 글자로 직접** 씁니다.
대신 각 yaml 맨 위에 그 글이 어떤 데이터를 보고 쓴 것인지 `based_on`으로 남깁니다.

```yaml
based_on:
  folder: dev                        # 이 글이 참고한 data/ 폴더
  created_at: "2026-11-10T06:05:17"  # 그 폴더에서 화면이 쓰는 파일 중 가장 늦은 created_at
summary:
  - "⏱️ rag_v4는 평균 2.384초로 응답하면서 Macro F1 0.796 달성"   # 요약 상자의 숫자는 굵게 쓰지 않음
```

| yaml | `based_on.folder` |
|---|---|
| `stages.yaml`, `performance.yaml` | `official` |
| `response_time.yaml` | `dev` |
| `aux.yaml` | `aux` |
| `model_compare.yaml` | `model_compare` |

- `created_at`은 화면이 실제로 쓰는 파일(`_post`나 `limit`이 있는 파일 제외) 중 가장 늦은 값입니다. 요약표 명령이 그대로 붙여 넣을 수 있게 출력합니다.
- 지금 데이터와 다르면 그 탭 위에 회색 안내 **"글 작성 이후 데이터가 바뀌었어요. 문장 속 숫자를 확인해 주세요."**가 뜹니다.
- 숫자 카드·그래프·결과 표·툴팁은 계속 JSON에서 자동으로 읽습니다. 사람이 쓰는 것은 글뿐입니다.

**요약표 명령** (글을 다시 쓸 때 참고)

```bash
python dashboard/summary.py              # 네 폴더 전부
python dashboard/summary.py official     # 폴더 하나만 (official / dev / aux / model_compare)
```

단계별(④는 모델별) Macro F1, 유형별 점수, 응답 시간(평균·중앙값·최대), 빈 답, 보조 지표를 소수 3자리 마크다운 표로 출력합니다.
맨 위에는 yaml에 붙여 넣을 `based_on`이 함께 나옵니다.

### 3-4. 그래프·툴팁 모양 규칙

**툴팁 (마우스를 따라다니는 상자)**

- Plotly 기본 툴팁은 데이터 점에 고정되고 테두리·여백을 바꿀 수 없어서, `lib/ui.py`의 `TIP_SCRIPT`가 직접 띄웁니다.
  `app.py`가 `st.html(ui.TIP_SCRIPT, unsafe_allow_javascript=True)`로 한 번 넣습니다 (우리가 쓴 코드만 들어감, 외부 스크립트 없음).
- 툴팁 내용은 그래프 함수가 점마다 `customdata`에 HTML로 넣습니다 (`charts.tip_html`). 단계 이름·개선점처럼 사람이 쓴 글은 이스케이프합니다.
- 스크립트가 하는 일: 커서 옆에 툴팁 (오른쪽·아래에 자리가 없으면 왼쪽·위로), 커서를 `?` 모양으로, `layout.meta.spike`가 있는 꺾은선 그래프에는 세로 점선, 범례 ⓘ(`data-tip`)에도 같은 툴팁.
- 스크립트가 안 도는 환경에서는 Plotly 기본 툴팁(`hovertext`)이 대신 보입니다.

**그래프 공통**

- 그림 영역 뒤에 둥근 박스(`charts.round_box`)를 깔고 축 테두리 선은 쓰지 않습니다. 단위가 다른 두 값은 y축 두 개를 겹치지 않고 위아래 박스로 나눕니다 (② c2a).
- 막대·점에 숫자 라벨이 있으면 y축 숫자·눈금선을 빼고, 라벨이 없으면(선이 여러 개) y축 숫자와 가로 눈금선을 남깁니다.
- 간격은 `lib/charts.py` 맨 위 상수 한 곳에서 바꿉니다:
  `X_LABEL_GAP`(x축 범주명 위 15px), `X_TITLE_GAP`(x축 이름 위 15px), `Y_LABEL_GAP`(y축 숫자 오른쪽 8px), `Y_TITLE_GAP`(y축 숫자 ↔ 제목 12px).
- 범례·안내 문장은 그림 영역(둥근 박스) 왼쪽 선에 맞춥니다 (`app.chart_panel`이 그래프 왼쪽 여백만큼 들여씀).
- 색은 와이어프레임 색을 그대로 씁니다. 조건 검색(주황)과 데이터 없음·거절 정확도(초록)는 적록색약에서 비슷해 보여서, 숫자 라벨·툴팁·칸 사이 틈으로 함께 구분합니다.

## 4. 실행 방법

```bash
# 저장소 루트에서
python3 -m venv .venv && source .venv/bin/activate
pip install -r dashboard/requirements.txt
streamlit run dashboard/app.py                                  # 브라우저에서 http://localhost:8501
python -m unittest discover -s dashboard/tests     # 검증 규칙 테스트 (표준 unittest)
python dashboard/summary.py                                     # 주요 수치 요약표
```

다크 모드는 `lib/ui.py`의 CSS(`ui.CSS`)로 고정합니다 (데모 앱 설정과 겹치지 않게).

---

## 5. 배포 (Streamlit Community Cloud)

로컬뿐 아니라 Streamlit Community Cloud에 배포해서 **항상 접속할 수 있는 주소**로 씁니다.

**배포 주소:** `https://______.streamlit.app` ← 배포 후 채우기

### 5-1. 처음 배포하기 (PR이 main에 머지된 뒤)

1. Streamlit Community Cloud → **Create app** → 이 저장소 선택
2. **Branch:** `main`
3. **Main file path:** `dashboard/app.py`
4. **App URL:** 원하는 subdomain 입력 (예: `genshin-dashboard` → `https://genshin-dashboard.streamlit.app`)
5. **Advanced settings → Secrets: 비워 둡니다.** 대시보드는 비밀값이 필요 없습니다.
6. Deploy → 배포 로그에서 **`dashboard/requirements.txt`가 쓰였는지** 확인
   - streamlit, plotly, pyyaml만 설치되어야 합니다. 루트 `requirements.txt`의 torch 등이 설치되면 잘못 잡힌 것입니다.
7. 위 **배포 주소** 칸을 채우고 커밋

### 5-2. 배포에서도 동작하게 지키는 규칙 (코드 작성 규칙)

- **파일 경로는 모두 `app.py` 위치 기준**으로 만듭니다: `BASE = Path(__file__).parent` → `BASE / "data"`, `BASE / "content"`
  - 실행 위치(`os.getcwd()`)나 `/Users/...` 같은 로컬 전용 경로는 쓰지 않습니다. 실행한 폴더가 달라도, Cloud에서도 같은 파일을 찾습니다.
- **필요한 패키지는 모두 `dashboard/requirements.txt`에** 적습니다. 새 라이브러리를 쓰면 여기에도 추가합니다.
- **비밀값·`.env`·`st.secrets`를 쓰지 않습니다.** 결과 JSON과 yaml만 읽습니다.
- 화면에 쓰는 파일(`data/`, `content/`)은 모두 깃에 올라가 있어야 합니다. 깃에 없는 파일은 Cloud에 없습니다.

### 5-3. 운영

- **데이터 갱신:** 새 JSON(과 고친 yaml)을 **main에 머지하면 자동으로 반영**됩니다. 다시 배포할 필요가 없습니다.
- **앱이 잠들었을 때:** 한동안 접속이 없으면 앱이 잠듭니다. 주소에 들어가서 **깨우기 버튼**을 누르면 다시 켜집니다.
- **배포 브랜치를 바꾸려면:** 이미 만든 앱의 브랜치는 바꿀 수 없어서, **앱을 지우고 새로 만들어야** 합니다. 지운 앱의 subdomain은 새 앱에 다시 쓸 수 있습니다.

---

## 6. 데이터가 바뀔 때 관리 가이드

### 먼저: 무엇이 자동이고 무엇을 직접 고치나

**그래프·숫자 카드·결과 표·툴팁은 코드를 고치지 않습니다.** JSON을 넣고 `stages.yaml`에 단계를 등록하면 자동으로 바뀝니다.
사람이 고치는 것은 **글(yaml)과 `based_on`** 뿐입니다.

| 화면 요소 | 어디서 오나 | 데이터가 바뀌면 |
|---|---|---|
| 그래프 (선·막대·점, 상관계수 "(N개 단계)") | 결과 JSON | ✅ 자동 |
| 숫자 카드 (마지막 단계 기준, baseline 대비 변화 / ④ 1위 모델) | 결과 JSON | ✅ 자동 |
| 📊 결과 표, 강조 줄 (마지막 단계 / ④ `highlight_model`) | 결과 JSON (+ ① 표의 글은 `stages.yaml`) | ✅ 자동 |
| 툴팁 숫자 · 개선점 | 결과 JSON · `stages.yaml`의 `change` | ✅ 자동 (개선점 글만 직접) |
| 단계 순서 · 개선점 · 알게 된 것 · 문제점 | `stages.yaml` | ✏️ 직접 |
| 상단 요약 · 💡 요약 · 주요 발견 · 다음 과제 (글 속 숫자 포함) | 탭별 yaml | ✏️ 직접 (`summary.py` 표 보고) |
| `based_on.created_at` | 탭별 yaml | ✏️ 직접 (안 고치면 회색 안내가 떠서 놓치지 않음) |
| ② 단계 선택 칩 · 단계별 주요 발견 | `response_time.yaml`의 `findings`, `planned_stages` | ✏️ 직접 |
| ④ GPU 메모리 · 모델 색 · 결정 사항 | `model_compare.yaml` | ✏️ 직접 |

### 상황 A. 같은 단계를 다시 돌려서 결과 파일이 바뀌었다

1. 드라이브의 새 JSON을 같은 폴더에 **덮어쓰기** 복사
2. `streamlit run dashboard/app.py`로 확인. 탭 줄 아래에 빨강·노랑 경고가 없는지 확인 (그 탭에 "글 작성 이후 데이터가 바뀌었어요" 회색 안내가 뜨는 것은 정상)
3. `python dashboard/summary.py <폴더>`로 요약표를 보고, 그 탭 yaml의 **문장과 숫자를 직접 수정**
4. 같은 yaml 맨 위의 `based_on.created_at`을 요약표에 나온 값으로 갱신 → 회색 안내가 사라지는지 확인
5. 커밋: `data: rag_v4 결과 갱신 (재실행 11/xx)`

### 상황 B. 새 단계(예: rag_v5)가 추가됐다

1. 새 JSON을 폴더별로 복사 (`official/`, `dev/`, `aux/` 중 있는 것만)
2. `content/stages.yaml`의 `order`에 `rag_v5` 한 줄 추가, 개선점·알게 된 것·문제점 작성
3. 화면 확인: 그래프·표·카드·툴팁에 rag_v5가 자동으로 붙음. 글이 있는 탭에는 회색 안내가 뜸
4. `python dashboard/summary.py`로 요약표를 보고, 탭별 yaml의 요약·💡·주요 발견·다음 과제의 **문장과 숫자를 직접 수정**
5. 고친 yaml마다 `based_on.created_at`을 요약표에 나온 값으로 갱신 → 회색 안내가 사라지는지 확인
6. ② 실험 기록의 **단계 선택**에 rag_v5가 생김: `response_time.yaml`의 `findings`에 `rag_v5:` 항목을 추가하고, `planned_stages`(흐리게 보이는 "예정" 단계)에서 rag_v5를 뺌
   - `findings`에 `rag_v5:`를 안 넣으면, 데이터가 있어도 칩이 흐린 "rag_v5 (예정)"으로 남아 누를 수 없습니다 (`planned_stages`에 남아 있을 때). 칩은 결과 JSON이 아니라 yaml의 `findings`로 만들어집니다.

> `order`에 없는 `method`가 폴더에 있으면 맨 뒤에 붙이고 "stages.yaml에 등록되지 않은 단계" 경고를 띄웁니다.

> **rag_v5가 일부 폴더에만 먼저 들어와도 정상입니다.** 예: 공식 결과(`official/`)만 있고 `dev/`·`aux/`는 아직 없으면
> ① 탭만 rag_v5까지 보이고 ②·③ 탭은 rag_v4에서 끝납니다. 숫자 카드도 탭마다 "그 폴더의 마지막 단계" 기준입니다.
> 나머지 폴더 파일이 들어오면 그 탭에 자동으로 붙습니다. 글은 파일이 들어온 탭의 yaml만 고칩니다.

### 상황 C. 평가셋 버전이 바뀌었다 (예: info_v2 → info_v3)

1. 이전 버전 파일을 `data/archive/info_v2/`로 옮김 (화면에서는 안 읽음)
2. 새 버전 파일을 각 폴더에 복사
3. 머리말의 평가셋·데이터 버전은 JSON의 `dataset_version`에서 자동 표시. 데이터 버전 문구(예: "데이터 7.2")만 `content/performance.yaml`의 `header`에서 수정
4. 버전이 섞이면 빨간 경고가 뜨므로, 경고가 사라질 때까지 파일 정리

### 상황 D. 모델 비교를 다시 했다 (rag_v5 이후 재비교)

1. `data/model_compare/`의 이전 파일을 `data/archive/`로 옮기고 새 파일 복사
2. 파일 이름이 `dev_rag_v{N}_qwen2.5-{크기}-{정밀도}-{GPU}` 형식인지 확인 (다르면 `lib/loader.py`의 정규식 수정)
3. `model_compare.yaml`의 GPU 메모리·결정 사항·조건 문구 수정
4. 새 모델(예: Kanana)이 들어오면 `model_compare.yaml`의 `models`에 표시 이름과 색을 추가

### 상황 E. 문구만 바꾸고 싶다

해당 탭의 `content/*.yaml`만 수정합니다. 코드는 건드리지 않습니다.

### 코드를 고쳐야 하는 경우 (드묾)

위 상황 A~E는 JSON과 yaml만으로 됩니다. 아래 경우만 코드를 고칩니다.

| 경우 | 고칠 곳 |
|---|---|
| 새 질문 유형이 생김 (lookup / filter / unknown 말고) | `lib/loader.py`의 `TYPES`, `lib/ui.py`의 `TYPE_LABEL`·`COLOR`, 유형별 그래프(`charts.py`의 `PERF_SERIES`, `hal_by_type`) |
| ④ 모델 결과 파일 이름 형식이 바뀜 | `lib/loader.py`의 모델 이름 정규식 (상황 D) |
| 결과 JSON의 칸 이름이 바뀜 (예: `metrics.avg_seconds`) | `lib/loader.py`와 `app.py`의 `*_rows` 함수. 팀 고정 형식이라 먼저 팀과 상의 |
| 그래프 모양·간격을 바꾸고 싶음 | `lib/charts.py` 맨 위 상수 (3-4) |

코드를 고쳤으면 `python -m unittest discover -s dashboard/tests`를 돌립니다.

### 변경 후 체크리스트

- [ ] 탭마다 탭 줄 아래에 경고가 없음
- [ ] "글 작성 이후 데이터가 바뀌었어요" 회색 안내가 없음 (yaml 문장·`based_on` 갱신 완료)
- [ ] 숫자 카드와 결과 표의 값이 같음, 글 속 숫자가 요약표와 같음
- [ ] 그래프에 마우스를 올리면 툴팁이 커서를 따라다니고 새 단계의 개선점이 보임
- [ ] `python -m unittest discover -s dashboard/tests` 통과
- [ ] `git status`에 `.env`, `secrets.toml`, `CLAUDE.md`가 없음
- [ ] 커밋 메시지에 무엇을 왜 바꿨는지 한 줄

---

## 7. TODO(D)

1. [x] 결과 JSON을 `data/` 폴더별로 복사 (2-1 표)
2. [x] `lib/loader.py`: 읽기 · 검증 · 지표 계산 + 테스트, `summary.py` 요약표
3. [x] `content/*.yaml`: 와이어프레임 문구 옮기기 (숫자는 V2 값을 직접, `based_on` 기록)
4. [x] 공통 레이아웃 (머리말, 탭, 카드, 💡 요약, 실험 기록)
5. [x] ② 응답 시간 탭
6. [x] ③ 보조 지표 탭
7. [x] ④ 모델 비교 탭
8. [x] ① 성능 변화 탭 (공식 info_v2 결과 파일 받은 뒤)
9. [ ] Streamlit Cloud 배포 (5장, PR 머지 후 직접) + 배포 주소 기록
