# RAG 검색용 문서 (data/docs)

벡터 DB(PostgreSQL pgvector)에 넣을 문서입니다. **B(RAG)는 이 파일을 읽어 임베딩해서 저장**하면 됩니다.

| 파일 | 내용 |
|---|---|
| `documents_ko.jsonl` | 문서 1,696개, 한 줄에 문서 1개 (JSON) |
| `preprocess_report.md` | 전처리 전후 비교표 (가이드 기본 단계 1-1 결과물) |

## 문서 형식

```json
{"doc_id": "character:albedo", "kind": "character", "title": "알베도",
 "text": "알베도 (백악의 아이)\n원소: 바위 / 무기: 한손검 / 성급: 5성 / 지역: 몬드\n...",
 "metadata": {"kind": "character", "name": "알베도", "element": "바위", "weapon": "한손검",
              "rarity": "5성", "region": "몬드", "source": "genshin-db 8e5badd"}}
```

| kind | 개수 | 1문서 = | 메타데이터 |
|---|---|---|---|
| character | 126 | 캐릭터 1명 프로필 | name, element, weapon, rarity, region |
| talent | 797 | 스킬·고유 특성 1개 | name(캐릭터), slot, skill_name |
| constellation | 129 | 캐릭터 1명의 명의 자리 1~6 | name |
| weapon | 256 | 무기 1개 | name, weapon(종류), rarity, main_stat |
| artifact | 63 | 성유물 세트 1개 | name, rarity |
| patch | 325 | 패치 변경 기록 1건 (5.0~7.2) | name, version, folder, change_type |

- `text`를 임베딩하고, `metadata`는 조건 검색 필터(원소=바위 등)와 출처 표시에 씁니다.
- 정보가 없는 값은 `text`에는 "정보 없음", `metadata`에는 `null`입니다 (`characters_ko.json`과 같은 규칙).
- 청킹: 지금은 **문서 1개 = 청크 1개**입니다. 길이는 대부분 짧고(평균 150~670자), 긴 것은 명의 자리·패치 기록(최대 약 3,300자)입니다. 길이 기준 분할 비교는 도전 과제입니다.

## 다시 만들기

```
python3 -m core.documents --fetch && python3 -m unittest tests.test_documents
```

`--fetch`는 genshin-db에서 필요한 폴더만 `collector/cache/genshin-db`에 받습니다(처음 한 번, 수 MB). 그다음부터는 `python3 -m core.documents`만 실행하면 됩니다.
데이터 커밋(`8e5badd`, 7.2)을 바꾸면 평가셋(`data/eval`)의 정답 출처와 어긋날 수 있으니, 바꿀 때는 `characters_ko.json`과 평가셋도 같이 확인합니다.
