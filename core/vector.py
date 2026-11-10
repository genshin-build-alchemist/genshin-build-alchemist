"""아이템(무기·성유물) 질문 벡터 검색 (기본 과업 2-1). 담당: 한동우 (B)

retrieval.py의 item 경로가 질문에 무기·성유물 이름이 없을 때 이 파일의 item_vector_search()를 부른다.
이 파일만 채우면 되고, 라우터·검색·답변 쪽은 이미 연결돼 있다 (core/router.py, core/retrieval.py).

지켜야 할 약속 (테스트: tests/test_item_route.py)
  item_vector_search(question, k=5) -> doc_id 목록, 가까운 순
      예: ["weapon:dragonsbane", "weapon:kitaincrossspear", ...]
      - doc_id는 data/docs/documents_ko.jsonl 과 같은 형식 ("weapon:{key}", "artifact:{key}")
      - 무기·성유물 문서만 돌려준다 (캐릭터·패치 문서는 빼기)
      - 임베딩 파일·모델·패키지가 없거나 오류가 나면 예외를 던지지 말고 [] 를 돌려준다
        (그러면 챗봇은 '찾지 못했어요'라고 답한다. GPU·DB 없는 환경에서도 API가 떠야 한다)
  set_item_index(encode, vectors, doc_ids)
      - 검색에 쓸 재료를 넣는 함수. 테스트는 가짜 encode와 작은 벡터로 이 함수를 부른다
      - encode(문장 목록) -> numpy 배열 (문장 수, 차원), 길이 1로 정규화된 벡터

TODO(B) 위에서부터 순서대로, 끝나면 [ ] -> [x]
 1. [ ] 무기·성유물 임베딩 파일 만들기: embed_and_save 셀에서 KINDS = ["weapon", "artifact"]
        -> 드라이브 data/embeddings/doc__granite-r2__weapon-artifact.{npy,jsonl,meta.json}
 2. [ ] load_item_index(folder): 위 .npy(벡터)와 .jsonl(doc_id)을 읽고, 같은 모델로 encode 함수를 만들어 set_item_index() 호출
        모델: ibm-granite/granite-embedding-311m-multilingual-r2, normalize_embeddings=True, 앞말 없이 (문서와 똑같이)
        torch, sentence_transformers 같은 무거운 import는 함수 안에서 한다
 3. [ ] item_vector_search(): 질문 벡터와 문서 벡터의 내적(정규화돼 있으니 코사인) 상위 k개 doc_id
        어제 만드신 vector_search()의 numpy 검색을 그대로 쓰면 된다
 4. [ ] tests/test_item_route.py 의 ItemVectorSearchTest 위 @unittest.skip 줄을 지우고 통과시키기
 5. [ ] 비교표: 아이템 질문 20~30개 + 정답 doc_id로 이름 매칭 vs 벡터 Hit@1, Hit@5 (core/retrieval_eval.py의 evaluate_retrieval)
        질문 형식 {"id", "type": "item", "split": "eval", "question", "gold_docs": ["weapon:..."]}
 막히면: A에게 질문
"""

_INDEX = {"encode": None, "vectors": None, "doc_ids": []}


def set_item_index(encode, vectors, doc_ids):
    """검색 재료 넣기. encode(문장 목록) -> (n, d) 배열, vectors: (문서 수, d) 배열, doc_ids: 문서 id 목록 (vectors와 같은 순서)."""
    _INDEX.update(encode=encode, vectors=vectors, doc_ids=list(doc_ids))


def item_vector_search(question, k=5):
    """질문 -> 비슷한 무기·성유물 문서 doc_id 상위 k개. 재료가 없거나 실패하면 []."""
    # TODO(B) 3번: 여기를 채운다. 지금은 비어 있어서 이름 없는 아이템 질문은 '찾지 못했어요'로 답한다
    return []
