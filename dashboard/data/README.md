# dashboard/data — 대시보드가 읽는 결과 JSON

팀 드라이브 `Genshin Build Alchemist (팀)/results/`에서 복사한 결과 파일입니다.
대시보드는 이 파일들을 **읽기만** 합니다. 손으로 고치거나 덮어쓰지 마세요. 잘못된 값은 실험 담당(C)에게 다시 받습니다.

> **깃 업로드: 팀 합의로 예외 허용**
> 팀 규칙(`docs/AI_CONTEXT.md` 8장)은 "결과 JSON은 깃에 올리지 않는다"입니다.
> 이 폴더의 공식 결과 JSON과 이 README는 대시보드 배포(Streamlit Cloud)에 필요해서, 팀 합의로 예외를 허용했습니다.
> 다른 폴더의 결과 JSON은 그대로 깃에 올리지 않습니다.

## 폴더

| 폴더 | 쓰는 탭 | 드라이브 원본 위치 | 만든 노트북 | 문항 | `dataset_version` |
|---|---|---|---|---|---|
| `official/` | ① 성능 변화 | `results/` | 01_eval_info | 평가셋 121문항 | `info_v2` |
| `dev/` | ② 응답 시간 | `results/` | 01_eval_info | DEV 60문항 | `info_v2-dev` |
| `aux/` | ③ 보조 지표 | `results/aux/` | 03_aux_metrics | DEV 60문항 (보조 지표만) | `info_v2-dev` |
| `model_compare/` | ④ 모델 비교 | `results/Model compare/` | 02_model_compare | DEV 60문항 | `info_v1-dev` |

- 실행 날짜는 각 JSON의 `created_at` 값입니다. 시간대 표시가 없고, 코랩에서 기록한 시각입니다.
- code_version은 `config.code_version`, 문항 수는 `metrics.n` 값입니다.
- `_post`가 붙은 파일(후처리본, `method`가 `rag_v4+post`)은 폴더에 있어도 대시보드가 쓰지 않습니다 (`dashboard/README.md` 2-2).
  `.gitignore`에 등록해서 **깃에도 올리지 않습니다** (로컬 폴더에만 있음, 아래 표의 `_post` 줄은 참고용).

## official과 DEV의 차이

| | official | DEV (dev, aux, model_compare) |
|---|---|---|
| 질문 | 평가셋 121문항 (`info_v2`) | 학습용 질문 60문항 (`info_v2-dev`, 모델 비교는 `info_v1-dev`) |
| 캐릭터 | 평가용 캐릭터 포함 | 평가용 캐릭터는 검색 대상에서 빠짐 |
| 쓰는 곳 | 최종 성능 보고 | 프롬프트·설정·모델 고르기 (팀 규칙 6장 3-2) |
| 보는 횟수 | 최종 버전을 정한 뒤 한 번만 | 몇 번이든 돌려도 됨 |

- **질문이 달라서 두 세트의 점수는 서로 비교하지 않습니다.**
- 모델 비교(`model_compare/`)는 `info_v1-dev` 기준이라 `dev/`(`info_v2-dev`)와도 점수를 직접 비교하지 않습니다.

## official/ (평가셋 121문항, Qwen2.5-3B-Instruct)

| 파일 | method | 실행 날짜 (`created_at`) | code_version | 문항 수 |
|---|---|---|---|---|
| `info10_baseline-V2.json` | baseline | 2026-11-10 06:24:05 | `main@af0c97c` | 121 |
| `info11_prompt_v2-V2.json` | prompt_v2 | 2026-11-10 06:26:10 | `main@af0c97c` | 121 |
| `info12_rag-V2.json` | rag | 2026-11-10 06:29:24 | `main@af0c97c` | 121 |
| `info13_rag_v3-V2.json` | rag_v3 | 2026-11-10 06:33:39 | `main@af0c97c` | 121 |
| `info14_rag_v4-V2.json` | rag_v4 | 2026-11-10 06:38:09 | `main@af0c97c` | 121 |
| `info14_rag_v4-V2_post.json` | rag_v4+post (화면에서 안 씀) | 2026-11-10 06:39:46 | `main@af0c97c` | 121 |

## dev/ (DEV 60문항, Qwen2.5-3B-Instruct, Colab T4)

| 파일 | method | 실행 날짜 (`created_at`) | code_version | 문항 수 |
|---|---|---|---|---|
| `dev_baseline-V2.json` | baseline | 2026-11-10 06:00:17 | `main@af0c97c` | 60 |
| `dev_prompt_v2-V2.json` | prompt_v2 | 2026-11-10 06:01:20 | `main@af0c97c` | 60 |
| `dev_rag-V2.json` | rag | 2026-11-10 06:03:04 | `main@af0c97c` | 60 |
| `dev_rag_v3-V2.json` | rag_v3 | 2026-11-10 06:05:17 | `main@af0c97c` | 60 |
| `dev_rag_v4-V2.json` | rag_v4 | 2026-11-10 05:54:38 | `main@af0c97c` | 60 |
| `dev_rag_v4-V2_post.json` | rag_v4+post (화면에서 안 씀) | 2026-11-10 06:17:13 | `main@af0c97c` | 60 |

rag_v4를 먼저 실행하고 나머지 네 방법을 이어서 실행해서, rag_v4의 날짜가 가장 이릅니다.

## aux/ (DEV 60문항 보조 지표)

노트북 03이 `dev/` 결과(`source_experiment`)를 다시 읽어 정답률, 거절 정확도, 환각률을 계산한 파일입니다.
문항별 기록(`per_question`)과 `limit` 칸이 없습니다. 그래서 대시보드의 limit 검사에서 빠집니다.
code_version은 **보조 지표를 계산한 시점**의 커밋입니다.

| 파일 | method | 원본 (`source_experiment`) | 실행 날짜 (`created_at`) | code_version | 문항 수 |
|---|---|---|---|---|---|
| `aux_dev_baseline-V2.json` | baseline | `dev_baseline-V2` | 2026-11-10 07:17:47 | `main@0e126c2` | 60 |
| `aux_dev_prompt_v2-V2.json` | prompt_v2 | `dev_prompt_v2-V2` | 2026-11-10 07:17:47 | `main@0e126c2` | 60 |
| `aux_dev_rag-V2.json` | rag | `dev_rag-V2` | 2026-11-10 07:17:48 | `main@0e126c2` | 60 |
| `aux_dev_rag_v3-V2.json` | rag_v3 | `dev_rag_v3-V2` | 2026-11-10 07:17:48 | `main@0e126c2` | 60 |
| `aux_dev_rag_v4-V2.json` | rag_v4 | `dev_rag_v4-V2` | 2026-11-10 07:17:48 | `main@0e126c2` | 60 |

## model_compare/ (DEV 60문항 `info_v1-dev`, rag_v4 프롬프트 고정, 모델만 바꿈)

모델·GPU·정밀도는 `experiment_id`에서 읽습니다. 화면에는 `_post`가 없는 8개 파일만 씁니다.
`_post` 파일은 같은 실행의 모델 원문에 후처리만 적용한 것이라, 원본과 날짜·code_version이 같습니다.

| 파일 | 모델 | GPU · 정밀도 | 실행 날짜 (`created_at`) | code_version | 문항 수 |
|---|---|---|---|---|---|
| `dev_rag_v4_qwen2.5-1.5b-fp16-L4.json` | 1.5B | L4 · fp16 | 2026-11-06 05:22:39 | `main@a51a088` | 60 |
| `dev_rag_v4_qwen2.5-1.5b-fp16-T4.json` | 1.5B | T4 · fp16 | 2026-11-06 05:14:13 | `main@43a02af` | 60 |
| `dev_rag_v4_qwen2.5-3b-fp16-L4.json` | 3B | L4 · fp16 | 2026-11-06 05:26:07 | `main@a51a088` | 60 |
| `dev_rag_v4_qwen2.5-3b-fp16-T4.json` | 3B | T4 · fp16 | 2026-11-06 05:08:37 | `main@f4e2b52` | 60 |
| `dev_rag_v4_qwen2.5-7b-4bit-T4.json` | 7B | T4 · 4bit | 2026-11-06 05:02:41 | `main@f4e2b52` | 60 |
| `dev_rag_v4_qwen2.5-7b-bf16-l4.json` | 7B | L4 · bf16 | 2026-11-06 03:10:31 | `main@f4e2b52` | 60 |
| `dev_rag_v4_qwen2.5-7b-fp16-T4.json` | 7B | T4 · fp16 | 2026-11-06 03:50:55 | `main@f4e2b52` | 60 |
| `dev_rag_v4_qwen2.5-7b-fp16-l4.json` | 7B | L4 · fp16 | 2026-11-06 03:14:06 | `main@f4e2b52` | 60 |

- 각 파일에 짝이 되는 `_post.json`이 하나씩 있습니다 (8개, 화면에서 안 씀).
- 파일 이름의 GPU 표기가 `L4`와 `l4`로 섞여 있습니다. 대시보드는 대소문자를 구분하지 않고 읽습니다.
- code_version이 파일마다 다릅니다 (대시보드는 이 차이를 따로 안내하지 않습니다).
