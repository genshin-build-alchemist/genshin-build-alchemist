-- Genshin Build Alchemist DB 스키마 (FR-09, PostgreSQL)
-- 적용: psql "$DATABASE_URL" -f db/schema.sql && psql "$DATABASE_URL" -f db/seed_characters.sql
-- 시드 파일 만들기: python3 db/make_seed.py

-- 캐릭터 정보 (조건 검색을 SQL로 할 수 있다: WHERE region = '몬드' AND rarity = '5성')
CREATE TABLE IF NOT EXISTS characters (
    key      TEXT PRIMARY KEY,          -- genshin-db 파일 이름 (예: albedo)
    name     TEXT NOT NULL UNIQUE,      -- 한국어 이름 (예: 알베도)
    element  TEXT,                      -- 원소 (정보 없으면 NULL)
    weapon   TEXT,                      -- 무기 종류
    rarity   TEXT,                      -- '4성' / '5성'
    region   TEXT                       -- 지역 (정보 없으면 NULL)
);

-- 챗봇 대화 기록 (시연과 오류 분석용). API 응답 형식과 칸 이름을 맞췄다.
CREATE TABLE IF NOT EXISTS chat_logs (
    id            BIGSERIAL PRIMARY KEY,
    asked_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    question      TEXT NOT NULL,
    route         TEXT NOT NULL,        -- lookup / filter / patch / build / unknown
    answer        JSONB NOT NULL,       -- ["..."]
    message       TEXT,
    evidence      JSONB,                -- [{"kind", "title", "text"}]
    found         BOOLEAN NOT NULL,
    needs_recheck BOOLEAN NOT NULL DEFAULT FALSE,
    model         TEXT,
    method        TEXT,
    data_version  TEXT
);
CREATE INDEX IF NOT EXISTS chat_logs_asked_at_idx ON chat_logs (asked_at);
CREATE INDEX IF NOT EXISTS chat_logs_route_idx ON chat_logs (route);

-- (선택) 임베딩 검색을 pgvector로 할 경우. 검색 방식이 정해지면 주석을 푼다.
-- 벡터 차원(아래 384)은 사용할 임베딩 모델에 맞춰 바꾼다.
-- CREATE EXTENSION IF NOT EXISTS vector;
-- CREATE TABLE IF NOT EXISTS documents (
--     id         BIGSERIAL PRIMARY KEY,
--     kind       TEXT NOT NULL,         -- character / patch / build_card
--     title      TEXT NOT NULL,
--     text       TEXT NOT NULL,
--     embedding  vector(384)
-- );
