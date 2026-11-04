# DB (PostgreSQL + pgvector)

PRD 8장 결정: 벡터 DB와 대화 기록을 PostgreSQL 하나에서 관리합니다. 코랩(실제 모델)과 로컬 PC(개발) 모두 접속해야 하므로 **클라우드 DB(Supabase 또는 Neon 무료)** 에 둡니다. 둘 다 pgvector를 지원합니다.

## 표 구성

| 표 | 내용 | 누가 채우나 |
|---|---|---|
| `documents` | 검색용 문서 1,430개 (`data/docs/documents_ko.jsonl`). 조건 검색용 칸(name, element, weapon, rarity, region, version)은 metadata에서 자동 계산 | A (시드 SQL) |
| `chunks` | 청크 + 임베딩 `vector(768)` (granite-embedding-311m-multilingual-r2). `strategy`(청킹 방식)와 `embedding_model`로 여러 버전을 같이 보관 | B (코랩에서 임베딩) |
| `characters` | 캐릭터 124명 (SQL 조건 검색) | A (시드 SQL) |
| `chat_logs` | 대화 기록 (질문, 경로, 답, 근거, 응답 시간, 검색 문서) | D (API) |

`documents`와 `chunks`를 나눈 이유: 청킹 방식(문서 단위 vs 길이 기준)이나 임베딩 모델을 바꿔 비교할 때 문서를 다시 넣지 않고 청크만 추가하면 됩니다 (도전 과제·심화 대비).

## 처음 설정 (D가 DB를 만든 뒤 한 번)

1. Supabase 또는 Neon에서 DB 만들기 → 접속 주소(`postgresql://...`)를 팀에 공유 (코드·노트북에 직접 쓰지 말고 `.env`와 코랩 보안 비밀 `DATABASE_URL`로)
2. 표 만들고 데이터 넣기 (여러 번 실행해도 안전):

```bash
python3 db/make_seed.py && python3 db/make_documents_seed.py && psql "$DATABASE_URL" -f db/schema.sql && psql "$DATABASE_URL" -f db/seed_characters.sql && psql "$DATABASE_URL" -f db/seed_documents.sql
```

3. B가 코랩에서 `documents`를 읽어 임베딩하고 `chunks`에 넣기 (임베딩이 없는 문서 찾기: `db/queries.sql` 5번)

## 검색 쿼리

`db/queries.sql`에 예시가 있습니다: 기본 벡터 검색, 조건 + 벡터, 캐릭터별 문서, 버전별 패치, 임베딩이 없는·다시 만들 문서, 청킹 방식별 개수.
코사인 거리 `<=>`는 작을수록 비슷하고, 유사도는 `1 - 거리`입니다.

## 문서가 바뀌었을 때

`data/docs`를 다시 만들고 시드를 다시 넣으면, **본문이 바뀐 문서만** `updated_at`이 갱신됩니다. `db/queries.sql` 6번으로 임베딩을 다시 만들 문서만 골라낼 수 있습니다.

## 임베딩 차원을 바꿀 때

granite 모델은 768차원을 384·256으로 줄여 쓸 수 있습니다(Matryoshka). 줄이면 `schema.sql`의 `vector(768)`과 HNSW 인덱스를 함께 바꾸고 `chunks`를 다시 만들어야 합니다.

## 테스트

- DB 없이: `python3 -m unittest tests.test_db_schema`
- 실제 DB로 (빈 테스트 DB만! 표를 지우고 다시 만듦): `TEST_DATABASE_URL=postgresql://... python3 -m unittest tests.test_db_schema`
- 로컬 PostgreSQL 16 + pgvector 0.6.0으로 스키마 적용, 시드, 벡터 검색, 변경 감지까지 확인했습니다.
