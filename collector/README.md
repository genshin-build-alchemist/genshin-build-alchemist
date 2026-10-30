# 원신 패치 변경 이력 수집기

genshin-db(GitHub)의 **커밋 이력**에서 버전별 변경 이력을 뽑아, RAG에 넣을 한국어 문서로 만든다.
표준 라이브러리 + git만 사용한다. (Python 3.9 이상, git 설치 필요, 인터넷 필요)

## 실행 (한 줄)

    python3 collect_patchnotes.py --last 3

처음 실행할 때는 저장소를 받느라 1~2분 걸린다(`cache/genshin-db`에 저장, 이후에는 갱신만).
결과는 `out/patch_changes.json`(구조화 기록)과 `out/patch_docs.jsonl`(RAG용 문서)에 저장된다.

## 테스트

    python3 -m unittest discover -s tests -t . -v

- 인터넷 없이 돌아가는 테스트(임시 git 저장소 사용)가 기본이다.
- 실제 데이터 점검은 `RUN_NETWORK_TESTS=1 python3 -m unittest tests.test_real_data -v`

## 구조

| 파일 | 역할 |
|---|---|
| `collect_patchnotes.py` | 실행 진입점(CLI) |
| `patchnotes/collector.py` | git 이력에서 버전 찾기, 연속된 두 버전 비교 |
| `patchnotes/differ.py` | 두 JSON 비교(순수 함수, 서식만 바뀐 건 무시) |
| `patchnotes/textutil.py` | 게임 태그 제거, 필드 이름 한글화 |
| `patchnotes/documents.py` | 변경 기록 -> RAG 문서 변환 |
| `tests/` | 단위 테스트와 실제 데이터 점검 |

## 알아둘 점

- 이것은 **데이터가 어떻게 바뀌었는지**이지 공식 패치노트 본문이 아니다. 개발사의 설명(의도)은 없다.
- 무기 이야기(story), 지역(region), 육성 재료(costs)는 패치 내용과 무관한 변경이 많아 일부러 비교에서 뺐다. `differ.py`의 `IGNORE_KEYS`에서 바꿀 수 있다.
- 수치 표(배율) 변경은 숫자 목록 전체를 전/후로 보여 준다.
- 게임 업데이트 직후에는 genshin-db가 아직 갱신되지 않았을 수 있다.
