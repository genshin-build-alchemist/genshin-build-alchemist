
"""
아이템(무기·성유물) 질문 벡터 검색 (기본 과업 2-1). 담당: 한동우 (B)

retrieval.py의 item 경로가 질문에 무기·성유물 이름이 없을 때
item_vector_search()를 호출한다.

load_item_index(folder) -> True/False
set_item_index(encode, vectors, doc_ids, metadata=None)
item_index_size() -> int
item_metadata_size() -> int

item_vector_search(
    question, k=5, kind=None, weapon_type=None,
    main_stat=None, rarity=None, return_info=False
)
"""

import json
import re
from pathlib import Path


# ============================================================
# 1. 검색 인덱스
# ============================================================

_INDEX = {
    "encode": None,
    "vectors": None,
    "doc_ids": [],
    "metadata": None,
}


def _clear_item_index():
    """검색 인덱스를 초기화한다."""
    _INDEX.update(
        encode=None,
        vectors=None,
        doc_ids=[],
        metadata=None,
    )


def set_item_index(encode, vectors, doc_ids, metadata=None):
    """
    검색에 사용할 임베딩 모델, 벡터, 문서 ID 및 메타데이터를 등록한다.

    metadata를 생략하면 기존 테스트 방식과 호환되는 일반 벡터 검색으로 동작한다.
    """
    import numpy as np

    if encode is None and vectors is None and not doc_ids:
        _clear_item_index()
        return

    vectors = np.asarray(vectors, dtype=np.float32)

    if vectors.ndim != 2:
        raise ValueError("vectors는 2차원 배열이어야 합니다.")

    if len(vectors) != len(doc_ids):
        raise ValueError("vectors와 doc_ids 개수가 다릅니다.")

    if len(set(doc_ids)) != len(doc_ids):
        raise ValueError("doc_ids에 중복이 있습니다.")

    if not np.isfinite(vectors).all():
        raise ValueError("벡터에 NaN 또는 Inf가 있습니다.")

    if metadata is not None:
        if len(metadata) != len(doc_ids):
            raise ValueError("metadata와 doc_ids 개수가 다릅니다.")

        if not all(isinstance(m, dict) for m in metadata):
            raise ValueError("metadata는 딕셔너리 목록이어야 합니다.")

    _INDEX.update(
        encode=encode,
        vectors=vectors,
        doc_ids=list(doc_ids),
        metadata=list(metadata) if metadata is not None else None,
    )


# ============================================================
# 2. 성급 데이터 정규화
# ============================================================

def _rarity_tokens(value):
    """성급 데이터를 집합으로 정규화한다.

    예:
        '5성'       -> {'5성'}
        '4성/5성'   -> {'4성', '5성'}
        '3성/4성'   -> {'3성', '4성'}
        '4~5성'     -> {'4성', '5성'}
    """
    if value is None:
        return set()

    values = value if isinstance(value, (list, tuple, set)) else [value]
    tokens = set()

    for item in values:
        text = str(item).strip()

        range_match = re.fullmatch(
            r"([1-5])\s*[~∼-]\s*([1-5])\s*성?",
            text,
        )

        if range_match:
            start, end = map(int, range_match.groups())

            tokens.update(
                f"{n}성"
                for n in range(min(start, end), max(start, end) + 1)
            )
            continue

        for token in text.replace(",", "/").split("/"):
            token = token.strip()

            if token.isdigit():
                token += "성"

            if token:
                tokens.add(token)

    return tokens


# ============================================================
# 3. 임베딩 및 메타데이터 로드
# ============================================================

def load_item_index(folder):
    """저장된 무기·성유물 임베딩과 원본 문서 메타데이터를 불러온다."""
    import numpy as np

    _clear_item_index()

    try:
        folder = Path(folder)

        vector_path = folder / "doc__granite-r2__weapon-artifact.npy"
        doc_path = folder / "doc__granite-r2__weapon-artifact.jsonl"
        documents_path = folder.parent / "documents_ko.jsonl"

        if not all(
            path.exists()
            for path in (vector_path, doc_path, documents_path)
        ):
            return False

        vectors = np.load(vector_path, allow_pickle=False)

        doc_ids = []

        with open(doc_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    doc_ids.append(json.loads(line)["doc_id"])

        if vectors.ndim != 2 or len(vectors) != len(doc_ids):
            return False

        if not np.isfinite(vectors).all():
            return False

        # 원본 documents_ko.jsonl에서 메타데이터 수집
        metadata_by_id = {}

        with open(documents_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue

                doc = json.loads(line)

                if doc.get("kind") not in ("weapon", "artifact"):
                    continue

                doc_id = doc.get("doc_id")
                metadata = doc.get("metadata")

                if not doc_id or not isinstance(metadata, dict):
                    return False

                if doc_id in metadata_by_id:
                    return False

                metadata_by_id[doc_id] = metadata

        # 임베딩과 원본 문서 ID 일치 확인
        if set(doc_ids) != set(metadata_by_id):
            return False

        # 임베딩 JSONL 순서에 맞춰 메타데이터 정렬
        metadata = [
            metadata_by_id[doc_id]
            for doc_id in doc_ids
        ]

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

        set_item_index(
            encode,
            vectors,
            doc_ids,
            metadata,
        )

        return True

    except Exception:
        _clear_item_index()
        return False


# ============================================================
# 4. 인덱스 정보
# ============================================================

def item_index_size():
    """현재 등록된 검색 문서 수를 반환한다."""
    return len(_INDEX["doc_ids"])


def item_metadata_size():
    """현재 등록된 메타데이터 수를 반환한다."""
    metadata = _INDEX["metadata"]

    return len(metadata) if metadata is not None else 0


# ============================================================
# 5. 아이템 벡터 검색 및 필터링
# ============================================================

def item_vector_search(
    question,
    k=5,
    kind=None,
    weapon_type=None,
    main_stat=None,
    rarity=None,
    return_info=False,
):
    """
    조건에 맞는 무기·성유물 후보를 필터링한 뒤 벡터 유사도로 검색한다.

    기본 검색:
        1. 5성 우선
        2. 4성 다음
        3. 4~5성 결과가 부족하면 3성으로 보충

    동일 성급에서는 벡터 유사도가 높은 순서로 반환한다.

    rarity를 명시하면 해당 성급만 검색하고 3성 자동 확장은 하지 않는다.

    return_info=True:
        {
            "doc_ids": [...],
            "fallback_to_3star": True/False
        }
    """
    import numpy as np

    def empty_result():
        if return_info:
            return {
                "doc_ids": [],
                "fallback_to_3star": False,
            }

        return []

    try:
        encode = _INDEX["encode"]
        vectors = _INDEX["vectors"]
        doc_ids = _INDEX["doc_ids"]
        metadata = _INDEX["metadata"]

        if encode is None or vectors is None or not doc_ids:
            return empty_result()

        if not isinstance(question, str) or not question.strip():
            return empty_result()

        k = int(k)

        if k <= 0 or vectors.ndim != 2 or len(vectors) != len(doc_ids):
            return empty_result()

        if kind not in (None, "weapon", "artifact"):
            return empty_result()

        # ----------------------------------------------------
        # 메타데이터가 없는 기존 테스트 방식 호환
        # ----------------------------------------------------

        if metadata is None:
            if any(
                value is not None
                for value in (kind, weapon_type, main_stat, rarity)
            ):
                return empty_result()

            candidate_indices = list(range(len(doc_ids)))
            primary_groups = {}
            fallback_indices = []
            legacy_mode = True

        else:
            if len(metadata) != len(doc_ids):
                return empty_result()

            legacy_mode = False
            primary_groups = {}
            fallback_indices = []

            # ------------------------------------------------
            # 기본 검색: 5성 → 4성
            # 3성은 부족한 결과를 채울 때만 사용
            # ------------------------------------------------

            if rarity is None:
                primary_rarities = {"5성", "4성"}
                fallback_rarities = {"3성"}

            else:
                # 성급을 명시하면 해당 성급만 검색
                primary_rarities = _rarity_tokens(rarity)
                fallback_rarities = set()

                if not primary_rarities:
                    return empty_result()

            for i, meta in enumerate(metadata):
                if not isinstance(meta, dict):
                    continue

                # 아이템 종류 필터
                if kind and meta.get("kind") != kind:
                    continue

                # 무기 종류 필터
                if weapon_type and meta.get("weapon") != weapon_type:
                    continue

                # 주옵션 필터
                # 주옵션 필터 (문자열 하나 또는 목록: '치명타' -> ['치명타 확률', '치명타 피해'])
                if main_stat and meta.get("main_stat") not in (
                    {main_stat} if isinstance(main_stat, str) else set(main_stat)
                ):
                    continue

                item_rarities = _rarity_tokens(meta.get("rarity"))

                matched_primary = item_rarities & primary_rarities

                if matched_primary:
                    # 여러 성급이 존재하면 허용된 성급 중 가장 높은 등급 사용
                    tier = max(
                        int(value[0])
                        for value in matched_primary
                    )

                    primary_groups.setdefault(tier, []).append(i)

                elif fallback_rarities and item_rarities & fallback_rarities:
                    fallback_indices.append(i)

            candidate_indices = [
                i
                for tier in sorted(primary_groups, reverse=True)
                for i in primary_groups[tier]
            ] + fallback_indices

            if not candidate_indices:
                return empty_result()

        # ----------------------------------------------------
        # 질문 임베딩
        # ----------------------------------------------------

        query_vector = np.asarray(
            encode([question]),
            dtype=np.float32,
        )

        if query_vector.ndim == 1:
            query_vector = query_vector.reshape(1, -1)

        if (
            query_vector.ndim != 2
            or query_vector.shape[0] != 1
            or query_vector.shape[1] != vectors.shape[1]
            or not np.isfinite(query_vector).all()
        ):
            return empty_result()

        # 후보 문서만 코사인 유사도 계산
        scores = np.dot(
            vectors[candidate_indices],
            query_vector[0],
        )

        score_by_index = {
            index: float(score)
            for index, score in zip(candidate_indices, scores)
        }

        # ----------------------------------------------------
        # 기존 메타데이터 없는 검색: 유사도순
        # ----------------------------------------------------

        if legacy_mode:
            ranked_indices = sorted(
                candidate_indices,
                key=lambda i: score_by_index[i],
                reverse=True,
            )

            results = ranked_indices[:k]
            fallback_used = False

        # ----------------------------------------------------
        # 성급 우선순위 검색
        # ----------------------------------------------------

        else:
            ranked_primary = []

            for tier in sorted(primary_groups, reverse=True):
                group = primary_groups[tier]

                group.sort(
                    key=lambda i: score_by_index[i],
                    reverse=True,
                )

                ranked_primary.extend(group)

            # 우선 5성·4성 결과를 반환
            selected = ranked_primary[:k]

            # 결과가 부족하면 3성으로 나머지 개수 보충
            fallback_used = False

            if rarity is None and len(selected) < k and fallback_indices:
                fallback_indices.sort(
                    key=lambda i: score_by_index[i],
                    reverse=True,
                )

                remaining = k - len(selected)
                fallback_results = fallback_indices[:remaining]

                selected.extend(fallback_results)

                fallback_used = bool(fallback_results)

            results = selected

        # ----------------------------------------------------
        # doc_id 반환 및 중복 제거
        # ----------------------------------------------------

        result_ids = []
        seen = set()

        for i in results:
            doc_id = doc_ids[i]

            if doc_id in seen:
                continue

            seen.add(doc_id)
            result_ids.append(doc_id)

            if len(result_ids) >= k:
                break

        if return_info:
            return {
                "doc_ids": result_ids,
                "fallback_to_3star": fallback_used,
            }

        return result_ids

    except Exception:
        return empty_result()
