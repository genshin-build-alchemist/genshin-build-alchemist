# dashboard (FR-E4, 서비스 담당)

다음 단계에서 결과 JSON(results/*.json)을 읽는 Streamlit 화면을 만듭니다.

- 방법별 점수 (baseline vs rag), 질문 유형별 점수, 틀린 질문 표
- 결과 JSON만 읽으므로 코랩 없이 로컬 PC에서 실행

## TODO(D) 끝나면 [ ] -> [x]

1. [ ] 드라이브 `results/`의 JSON을 로컬에 내려받아 읽기 (형식: `docs/AI_CONTEXT.md` 5장 결과 JSON)
2. [ ] 방법별 비교표: macro F1, micro P/R/F1, 빈 답, 평균 응답 시간 (노트북 셀 10 출력과 같은 숫자가 나와야 정답)
3. [ ] 질문 유형별(lookup/filter/unknown) 점수 막대그래프
4. [ ] 틀린 질문 표: 질문, 정답(gold), 모델 답(pred), 모델 원문(raw)
5. [ ] 응답 시간 분포 (최대 10초 안팎인 문항이 있음)
6. [ ] `results/baseline/`(원본)과 새 결과를 나란히 비교
