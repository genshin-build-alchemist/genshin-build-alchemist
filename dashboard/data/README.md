# dashboard/data — 대시보드가 읽는 결과 파일

팀 드라이브 `Genshin Build Alchemist (팀)/results/`에서 복사한 결과 파일입니다.
대시보드는 이 파일들을 **읽기만** 합니다. 손으로 고치거나 덮어쓰지 마세요. 잘못된 값은 실험 담당(C)에게 다시 받습니다.

> **깃 업로드: 팀 합의로 예외 허용**
> 팀 규칙(`docs/AI_CONTEXT.md` 8장)은 "결과 JSON은 깃에 올리지 않는다"입니다.
> 이 폴더의 결과 파일과 이 README는 대시보드 배포(Streamlit Cloud)에 필요해서, 팀 합의로 예외를 허용했습니다.
> 다른 폴더의 결과 JSON은 그대로 깃에 올리지 않습니다.

## 폴더

| 폴더 | 쓰는 탭 | 문항 | `dataset_version` | 파일 |
|---|---|---|---|---|
| `official/` | 성능 변화 | 평가셋 121문항 | `info_v2` | 단계마다 JSON 1개 (7개) |
| `dev/` | 응답 시간 | DEV 60문항 | `info_v2-dev` | 단계마다 JSON 1개 (7개, 11/17 한 런타임) |
| `aux/` | 보조 지표 | 평가셋 121문항 | (CSV에 없음 → `official/`) | 팀이 정리한 CSV 2개 |
| `model_compare/` | 모델 비교 | DEV 60문항 | `info_v2-dev` | 단계 3개 × 모델 조합 8개 = JSON 24개 |

- 실행 날짜는 각 JSON의 `created_at` 값입니다. 시간대 표시가 없고, 코랩에서 기록한 시각입니다.
- code_version은 `config.code_version`, 문항 수는 `metrics.n` 값입니다.
- `_post`가 붙은 파일(후처리본, `method`가 `rag_v4+post`)은 폴더에 있어도 대시보드가 쓰지 않습니다 (`dashboard/README.md` 2-2).
  `.gitignore`에 등록해서 **깃에도 올리지 않습니다** (로컬 폴더에만 있음, 아래 표의 `_post` 줄은 참고용).

## official과 DEV의 차이

| | official (+ aux) | DEV (dev, model_compare) |
|---|---|---|
| 질문 | 평가셋 121문항 (`info_v2`) | 학습용 질문 60문항 (`info_v2-dev`) |
| 캐릭터 | 평가용 캐릭터 포함 | 평가용 캐릭터는 검색 대상에서 빠짐 |
| 쓰는 곳 | 최종 성능 보고 | 프롬프트·설정·모델 고르기, 응답 시간 측정 (팀 규칙 6장 3-2) |
| 보는 횟수 | 최종 버전을 정한 뒤 한 번만 | 몇 번이든 돌려도 됨 |

- **질문이 달라서 두 세트의 점수는 서로 비교하지 않습니다.**

## official/ (평가셋 121문항, Qwen2.5-3B-Instruct)

| 파일 | method | 실행 날짜 (`created_at`) | code_version | 문항 수 |
|---|---|---|---|---|
| `info10_baseline-V2.json` | baseline | 2026-11-10 06:24:05 | `main@af0c97c` | 121 |
| `info11_prompt_v2-V2.json` | prompt_v2 | 2026-11-10 06:26:10 | `main@af0c97c` | 121 |
| `info12_rag-V2.json` | rag | 2026-11-10 06:29:24 | `main@af0c97c` | 121 |
| `info13_rag_v3-V2.json` | rag_v3 | 2026-11-10 06:33:39 | `main@af0c97c` | 121 |
| `info14_rag_v4-V2.json` | rag_v4 | 2026-11-10 06:38:09 | `main@af0c97c` | 121 |
| `info14_rag_v4-V2_post.json` | rag_v4+post (화면에서 안 씀) | 2026-11-10 06:39:46 | `main@af0c97c` | 121 |
| `info15_rag_v5-V2.json` | rag_v5 | 2026-11-17 06:23:47 | `main@1d1f8c0` | 121 |
| `info16_rag_v5_data-V2.json` | rag_v5_data | 2026-11-17 06:20:25 | `main@1d1f8c0` | 121 |

## dev/ (DEV 60문항, Qwen2.5-3B-Instruct, Colab T4)

응답 시간을 공정하게 비교하려고 **일곱 단계를 한 런타임에서 이어서** 실행한 결과입니다 (2026-11-17 08:17~08:29).

| 파일 | method | 실행 날짜 (`created_at`) | code_version | 문항 수 |
|---|---|---|---|---|
| `dev_baseline-V2_2026.11.17.json` | baseline | 2026-11-17 08:19:32 | `main@3b8aeb5` | 60 |
| `dev_prompt_v2-V2_2026.11.17.json` | prompt_v2 | 2026-11-17 08:20:37 | `main@3b8aeb5` | 60 |
| `dev_rag-V2_2026.11.17.json` | rag | 2026-11-17 08:22:18 | `main@3b8aeb5` | 60 |
| `dev_rag_v3-V2_2026.11.17.json` | rag_v3 | 2026-11-17 08:24:30 | `main@3b8aeb5` | 60 |
| `dev_rag_v4-V2_2026.11.17.json` | rag_v4 | 2026-11-17 08:26:49 | `main@3b8aeb5` | 60 |
| `dev_rag_v5-V2_2026.11.17.json` | rag_v5 | 2026-11-17 08:28:29 | `main@3b8aeb5` | 60 |
| `dev_rag_v5_data-V2_2026.11.17.json` | rag_v5_data | 2026-11-17 08:29:30 | `main@3b8aeb5` | 60 |

## aux/ (평가셋 121문항 보조 지표, CSV)

팀이 공식 결과(`official/`)를 다시 채점해서 정리한 CSV입니다. 대시보드가 JSON과 같은 모양으로 바꿔 읽습니다 (`lib/loader.py`의 `aux_csv_candidates`).

| 파일 | 한 줄 = | 칸 |
|---|---|---|
| `보조지표_요약-info-v2.csv` | 단계 하나 | 방법, 정답률, 정답 문항 수, 거절 정확도, 환각률, 환각 문항 수, 답한 문항 수, 전체 문항 수, 모델, 실험 ID, 비고 |
| `보조지표_환각사례-info-v2.csv` | 환각 문항 하나 | 방법, id, 유형 (유형별 환각 건수를 셀 때 씀) |

- CSV에는 날짜·평가셋 버전이 없어서, **같은 단계의 공식 결과(`official/`)의 `created_at`·`dataset_version`**을 씁니다.
- 환각 사례 건수와 요약의 환각 문항 수가 다르면 노란 경고가 뜹니다.
- 이 폴더에 요약 CSV가 있으면 같은 폴더의 JSON은 읽지 않습니다.

## model_compare/ (DEV 60문항, 단계마다 모델만 바꿈)

- 모델 크기와 GPU는 `experiment_id`(예: `dev_rag_v5_qwen2.5-3b-L4`)에서, 정밀도는 `config.load_4bit`(True면 4bit, 아니면 fp16)에서 읽습니다.
- GPU 메모리는 `config.gpu_memory_gb`에서 읽습니다.
- 같은 모델 조합이라도 단계(`method`)가 다르면 다른 결과입니다. 화면은 왼쪽 "실험 단계" 버튼으로 고른 단계의 8개만 씁니다.

| 단계 | 파일 (모델 조합 8개) | 실행 날짜 (`created_at`) | code_version |
|---|---|---|---|
| rag_v4 | `dev_rag_v4_qwen2.5-{1.5b,3b}-fp16-{L4,T4}.json`, `dev_rag_v4_qwen2.5-7b-{fp16,4bit}-{L4,T4}.json` | 2026-11-10 02:43 ~ 05:04 | `main@af0c97c` |
| rag_v5 | `dev_rag_v5_qwen2.5-{1.5b,3b}-{L4,T4}.json`, `dev_rag_v5_qwen2.5-7b-4bit-{L4,T4}.json`, `dev_rag_v5_qwen2.5-7b-fp16-T4.json`, `dev_rag_v5_qwen2.5-7b-fp16.-L4json.json` | 2026-11-19 03:32 ~ 05:48 | `main@ab603eb` |
| rag_v5_data | `dev_rag_v5_data_qwen2.5-{1.5b,3b}-fp16-{L4,T4}.json`, `dev_rag_v5_data_qwen2.5-7b-{fp16,4bit}-{L4,T4}.json` | 2026-11-19 08:33 ~ 10:34 | `main@ab603eb`, `main@bda1477` |

| 모델 · GPU · 정밀도 | GPU 메모리 (`config.gpu_memory_gb`) |
|---|---|
| 1.5B · fp16 | 2.88GB |
| 3B · fp16 | 5.75GB |
| 7B · 4bit | 5.45GB |
| 7B · fp16 | L4 14.19GB / T4 11.87GB |

- rag_v4는 파일마다 짝이 되는 `_post.json`이 있습니다 (8개, 화면에서 안 씀).
- `dev_rag_v5_qwen2.5-7b-fp16.-L4json.json`은 드라이브 원본 이름 그대로입니다 (이름을 고치지 않음). 대시보드는 `L4`를 정상으로 읽습니다.
- rag_v5 파일 이름에는 `fp16`이 빠진 것이 있지만, 정밀도는 이름이 아니라 `config.load_4bit`로 정합니다.
