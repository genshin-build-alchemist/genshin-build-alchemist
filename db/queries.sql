-- 자주 쓸 검색 쿼리 예시 (B: RAG, D: 서비스). $1 은 질문 임베딩(vector(768)), $2 는 k.
-- 코사인 거리 <=> 는 0에 가까울수록 비슷하다. 유사도 = 1 - 거리.

-- 1) 기본 벡터 검색: 질문과 가장 비슷한 청크 k개 + 문서 정보 (출처 표시에 필요한 title·metadata 포함)
SELECT c.doc_id, d.kind, d.title, c.text, d.metadata, 1 - (c.embedding <=> $1) AS similarity
FROM chunks c
JOIN documents d USING (doc_id)
WHERE c.strategy = 'doc'
  AND c.embedding_model = 'ibm-granite/granite-embedding-311m-multilingual-r2'
ORDER BY c.embedding <=> $1
LIMIT $2;

-- 2) 조건 검색 + 벡터: 메타데이터로 먼저 거르고 그 안에서 비슷한 순서 (예: 몬드 출신 5성 캐릭터 문서만)
SELECT c.doc_id, d.title, 1 - (c.embedding <=> $1) AS similarity
FROM chunks c
JOIN documents d USING (doc_id)
WHERE c.strategy = 'doc'
  AND d.kind = 'character' AND d.region = '몬드' AND d.rarity = '5성'
ORDER BY c.embedding <=> $1
LIMIT $2;

-- 3) 특정 캐릭터 문서만 (줄임 이름을 라우터가 찾은 경우 등): 프로필·스킬·명의 자리·패치 기록
SELECT doc_id, kind, title FROM documents WHERE name = '카에데하라 카즈하' ORDER BY kind, doc_id;

-- 4) 특정 버전의 패치 기록
SELECT doc_id, title FROM documents WHERE kind = 'patch' AND version = '7.0' ORDER BY doc_id;

-- 5) 임베딩을 아직 안 만든 문서 (B가 코랩에서 이것만 임베딩)
SELECT d.doc_id FROM documents d
LEFT JOIN chunks c ON c.doc_id = d.doc_id AND c.strategy = 'doc'
WHERE c.doc_id IS NULL;

-- 6) 본문이 바뀌어 임베딩을 다시 만들어야 하는 문서
SELECT DISTINCT d.doc_id FROM documents d JOIN chunks c USING (doc_id) WHERE d.updated_at > c.created_at;

-- 7) 청킹 방식·임베딩 모델별 청크 수 (도전 과제 비교표용)
SELECT strategy, embedding_model, count(*) AS chunks FROM chunks GROUP BY 1, 2 ORDER BY 1, 2;
