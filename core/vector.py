"""아이템(무기·성유물) 질문 벡터 검색 (기본 과업 2-1). 담당: 한동우 (B)

retrieval.py의 item 경로가 질문에 무기·성유물 이름이 없을 때 item_vector_search()를 부른다.

약속 (테스트: tests/test_item_route.py)
  load_item_index(folder) -> True/False
      드라이브 data/embeddings/doc__granite-r2__weapon-artifact.{npy,jsonl} 을 읽고 같은 모델로 질문 encode 함수를 만든다.
      실행 노트북(notebooks/run_chatbot.ipynb) 2번 칸에서 부른다. 파일·패키지가 없으면 False (챗봇은 그대로 뜬다)
  set_item_index(encode, vectors, doc_ids)
      검색 재료 넣기. encode(문장 목록) -> (문장 수, 차원) 정규화 벡터. 테스트는 가짜 encode로 부른다
  item_vector_search(question, k=5) -> doc_id 목록, 가까운 순 (예: ["weapon:skywardharp", ...])
      무기·성유물 문서만, 같은 doc_id는 한 번만. 재료가 없거나 오류가 나면 []
  item_index_size() -> 지금 들어 있는 문서 수 (0이면 벡터 검색 꺼짐)

numpy, sentence_transformers 같은 import는 함수 안에서 한다 (GPU·패키지 없는 환경에서도 API가 떠야 한다).
"""

import json
from pathlib import Path

_INDEX = {
    "encode": None,
    "vectors": None,
    "doc_ids": [],
}


def set_item_index(encode, vectors, doc_ids):
    """검색에 사용할 임베딩 모델과 벡터 인덱스를 등록한다."""
    import numpy as np

    # 인덱스 초기화
    if encode is None and vectors is None and not doc_ids:
        _INDEX.update(
            encode=None,
            vectors=None,
            doc_ids=[],
        )
        return

    vectors = np.asarray(vectors, dtype=np.float32)

    if vectors.ndim != 2:
        raise ValueError("vectors는 2차원 배열이어야 합니다.")

    if len(vectors) != len(doc_ids):
        raise ValueError("vectors와 doc_ids의 개수가 다릅니다.")

    _INDEX.update(
        encode=encode,
        vectors=vectors,
        doc_ids=list(doc_ids),
    )

def load_item_index(folder):
    """저장된 무기·성유물 임베딩 파일을 불러온다."""
    import numpy as np
    
    _INDEX.update(encode=None, vectors=None, doc_ids=[])

    try:
        folder = Path(folder)

        vector_path = folder / "doc__granite-r2__weapon-artifact.npy"
        doc_path = folder / "doc__granite-r2__weapon-artifact.jsonl"

        if not vector_path.exists() or not doc_path.exists():
            return False

        vectors = np.load(vector_path, allow_pickle=False)

        doc_ids = []
        with open(doc_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    item = json.loads(line)
                    doc_ids.append(item["doc_id"])

        if vectors.ndim != 2 or len(vectors) != len(doc_ids):
            return False

        if not np.isfinite(vectors).all():
            return False

        # 무기와 성유물 문서만 사용
        valid_indices = [
            i for i, doc_id in enumerate(doc_ids)
            if doc_id.startswith(("weapon:", "artifact:"))
        ]

        vectors = vectors[valid_indices]
        doc_ids = [doc_ids[i] for i in valid_indices]

        if not doc_ids:
            return False

        # 무거운 라이브러리는 실제 로드 시점에 import
        from sentence_transformers import SentenceTransformer

        model = SentenceTransformer(
            "ibm-granite/granite-embedding-311m-multilingual-r2"
        )

        def encode(texts):
            return model.encode(
                texts,
                normalize_embeddings=True,
                convert_to_numpy=True,
            )

        set_item_index(encode, vectors, doc_ids)
        return True

    except Exception:
        _INDEX.update(encode=None, vectors=None, doc_ids=[])
        return False


def item_index_size():
    """지금 들어 있는 검색 문서 수. 0이면 벡터 검색이 꺼진 상태."""
    return len(_INDEX["doc_ids"])


def item_vector_search(question, k=5):
    """질문과 유사한 무기·성유물 문서 ID를 반환한다."""
    import numpy as np
    
    try:
        encode = _INDEX["encode"]
        vectors = _INDEX["vectors"]
        doc_ids = _INDEX["doc_ids"]

        if encode is None or vectors is None or not doc_ids:
            return []

        if not isinstance(question, str) or not question.strip():
            return []

        k = int(k)
        if k <= 0:
            return []

        query_vector = np.asarray(
            encode([question]),
            dtype=np.float32,
        )

        if query_vector.ndim == 1:
            query_vector = query_vector.reshape(1, -1)

        if query_vector.shape[0] != 1:
            return []

        if query_vector.shape[1] != vectors.shape[1]:
            return []

        if not np.isfinite(query_vector).all():
            return []

        # 정규화된 벡터의 내적 = 코사인 유사도
        scores = np.dot(vectors, query_vector[0])

        top_indices = np.argsort(scores)[::-1]

        results = []
        seen = set()

        for i in top_indices:
            doc_id = doc_ids[i]
            if doc_id in seen:
                continue
            seen.add(doc_id)
            results.append(doc_id)
            if len(results) == k:
                break

        return results
            
    except Exception:
        return []
