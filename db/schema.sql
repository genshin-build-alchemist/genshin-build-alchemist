-- Genshin Build Alchemist DB 스키마 (PostgreSQL 16 + pgvector 0.5 이상)
-- 벡터 DB(문서·청크·임베딩)와 대화 기록을 한 DB에서 관리한다. (PRD 8장: PostgreSQL + pgvector 결정)
--
-- 적용 (여러 번 실행해도 안전):
--   psql "$DATABASE_URL" -f db/schema.sql
--   python3 db/make_seed.py && psql "$DATABASE_URL" -f db/seed_characters.sql
--   python3 db/make_documents_seed.py && psql "$DATABASE_URL" -f db/seed_documents.sql
-- 임베딩(chunks 표)은 B(RAG)가 코랩에서 granite 모델로 만들어 넣는다. 예시 쿼리는 db/queries.sql

CREATE EXTENSION IF NOT EXISTS vector;

-- ─────────────────────────────────────────────────────────────
-- 1. 캐릭터 정보 (조건 검색을 SQL로 할 수 있다: WHERE region = '몬드' AND rarity = '5성')
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS characters (
    key      TEXT PRIMARY KEY,          -- genshin-db 파일 이름 (예: albedo)
    name     TEXT NOT NULL UNIQUE,      -- 한국어 이름 (예: 알베도)
    element  TEXT,                      -- 원소 (정보 없으면 NULL)
    weapon   TEXT,                      -- 무기 종류
    rarity   TEXT,                      -- '4성' / '5성'
    region   TEXT                       -- 지역 (정보 없으면 NULL)
);

-- ─────────────────────────────────────────────────────────────
-- 2. 검색용 문서 원본 (data/docs/documents_ko.jsonl 과 같은 형식, 1,430개)
--    임베딩은 여기 넣지 않고 chunks 표에 넣는다 (청킹 방식·임베딩 모델을 바꿔 비교할 수 있게)
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS documents (
    doc_id       TEXT PRIMARY KEY,                       -- 예: character:albedo, talent:albedo:combat2
    kind         TEXT NOT NULL CHECK (kind IN
                 ('character', 'talent', 'constellation', 'weapon', 'artifact', 'patch', 'build_card')),
    title        TEXT NOT NULL,
    text         TEXT NOT NULL,
    metadata     JSONB NOT NULL DEFAULT '{}'::jsonb,     -- name, element, weapon, rarity, region, version, source ...
    -- 조건 검색 필터에 자주 쓰는 값은 metadata에서 꺼내 칸으로 둔다 (자동 계산, 직접 넣지 않음)
    name         TEXT GENERATED ALWAYS AS (metadata ->> 'name') STORED,
    element      TEXT GENERATED ALWAYS AS (metadata ->> 'element') STORED,
    weapon       TEXT GENERATED ALWAYS AS (metadata ->> 'weapon') STORED,
    rarity       TEXT GENERATED ALWAYS AS (metadata ->> 'rarity') STORED,
    region       TEXT GENERATED ALWAYS AS (metadata ->> 'region') STORED,
    version      TEXT GENERATED ALWAYS AS (metadata ->> 'version') STORED,
    content_hash TEXT GENERATED ALWAYS AS (md5(kind || E'\n' || text)) STORED,  -- 본문 지문 (자동 계산)
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS documents_kind_idx ON documents (kind);
CREATE INDEX IF NOT EXISTS documents_name_idx ON documents (name);
CREATE INDEX IF NOT EXISTS documents_filter_idx ON documents (element, weapon, rarity, region);
CREATE INDEX IF NOT EXISTS documents_metadata_idx ON documents USING gin (metadata jsonb_path_ops);

-- ─────────────────────────────────────────────────────────────
-- 3. 청크 + 임베딩 (벡터 검색 대상)
--    strategy: 청킹 방식. 기본은 'doc' (문서 1개 = 청크 1개). 도전 과제에서 'len200', 'len500' 등을 추가해 비교
--    embedding_model: 같은 문서를 다른 모델로 임베딩해 비교할 때 구분 (심화: 임베딩 모델 비교)
--    vector(768): granite-embedding-311m-multilingual-r2 기본 차원.
--                 Matryoshka로 줄여 쓰면 이 숫자와 아래 인덱스를 함께 바꾼다
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS chunks (
    chunk_id        TEXT PRIMARY KEY,                    -- 예: doc|granite-r2|character:albedo#0
    doc_id          TEXT NOT NULL REFERENCES documents (doc_id) ON DELETE CASCADE,
    strategy        TEXT NOT NULL DEFAULT 'doc',
    chunk_index     INT  NOT NULL DEFAULT 0,             -- 문서 안에서 몇 번째 조각인지
    text            TEXT NOT NULL,                       -- 임베딩한 글 (strategy가 'doc'이면 문서 본문과 같음)
    embedding_model TEXT NOT NULL,                       -- 예: ibm-granite/granite-embedding-311m-multilingual-r2
    embedding       vector(768) NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (strategy, embedding_model, doc_id, chunk_index)
);
CREATE INDEX IF NOT EXISTS chunks_doc_idx ON chunks (doc_id);
CREATE INDEX IF NOT EXISTS chunks_strategy_model_idx ON chunks (strategy, embedding_model);
-- 코사인 거리(<=>) 근사 검색 인덱스. 문서가 수천 개 수준이라 없어도 정확 검색으로 충분히 빠르다.
-- 결과를 정확 검색과 비교하고 싶으면 이 인덱스를 지우고 다시 재면 된다.
CREATE INDEX IF NOT EXISTS chunks_embedding_hnsw_idx ON chunks USING hnsw (embedding vector_cosine_ops);

-- ─────────────────────────────────────────────────────────────
-- 4. 챗봇 대화 기록 (시연과 오류 분석용). API 응답 형식과 칸 이름을 맞췄다.
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS chat_logs (
    id            BIGSERIAL PRIMARY KEY,
    asked_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    question      TEXT NOT NULL,
    route         TEXT NOT NULL,        -- lookup / filter / patch / build / item / unknown
    answer        JSONB NOT NULL,       -- ["..."]
    message       TEXT,
    evidence      JSONB,                -- [{"kind", "title", "text"}]
    found         BOOLEAN NOT NULL,
    needs_recheck BOOLEAN NOT NULL DEFAULT FALSE,
    model         TEXT,
    method        TEXT,
    data_version  TEXT
);
-- 응답 시간·검색 문서 기록 (가이드 기본 3-2 응답 시간, 오류 분석용). 예전에 만든 표에도 붙도록 따로 추가한다
ALTER TABLE chat_logs ADD COLUMN IF NOT EXISTS seconds DOUBLE PRECISION;
ALTER TABLE chat_logs ADD COLUMN IF NOT EXISTS retrieved_doc_ids TEXT[];
CREATE INDEX IF NOT EXISTS chat_logs_asked_at_idx ON chat_logs (asked_at);
CREATE INDEX IF NOT EXISTS chat_logs_route_idx ON chat_logs (route);
