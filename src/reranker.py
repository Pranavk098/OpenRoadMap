"""
Maximal Marginal Relevance (MMR) diversity re-ranking.

Pure numpy implementation operating on already-computed embedding vectors -
no live services (Qdrant, OpenAI) required, so it is directly unit
testable with synthetic vectors. Standard formula:

    MMR = argmax_{d in R \\ S} [ lambda * sim(d, query) - (1 - lambda) * max_{s in S} sim(d, s) ]

Selected greedily: repeatedly pick the highest-MMR remaining candidate,
add it to the selected set S, until k items are selected (or candidates
run out).
"""
import numpy as np


def _cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    denom = (np.linalg.norm(a) * np.linalg.norm(b)) + 1e-10
    return float(np.dot(a, b) / denom)


def mmr_rerank(
    query_vector: np.ndarray,
    candidate_vectors: np.ndarray,
    candidate_ids: list,
    k: int,
    lambda_param: float = 0.5,
) -> list:
    """Re-rank candidates by Maximal Marginal Relevance.

    Args:
        query_vector: (d,) embedding of the query.
        candidate_vectors: (n, d) embeddings of the candidate documents,
            same order as candidate_ids.
        candidate_ids: identifiers for the n candidates.
        k: number of items to select (clamped to n if fewer candidates exist).
        lambda_param: relevance vs. diversity tradeoff in [0, 1].
            1.0 = pure relevance ranking (redundancy ignored).
            0.0 = pure diversity (query relevance ignored).

    Returns:
        candidate_ids re-ordered by MMR selection, length min(k, n).
    """
    query_vector = np.asarray(query_vector, dtype=float)
    candidate_vectors = np.asarray(candidate_vectors, dtype=float)
    n = len(candidate_ids)
    k = min(k, n)

    if n == 0 or k == 0:
        return []

    relevance = [_cosine_sim(query_vector, candidate_vectors[i]) for i in range(n)]

    selected = []
    remaining = list(range(n))

    while remaining and len(selected) < k:
        best_idx = None
        best_score = -float("inf")
        for idx in remaining:
            if not selected:
                redundancy = 0.0
            else:
                redundancy = max(_cosine_sim(candidate_vectors[idx], candidate_vectors[s]) for s in selected)
            score = lambda_param * relevance[idx] - (1 - lambda_param) * redundancy
            if score > best_score:
                best_score = score
                best_idx = idx
        selected.append(best_idx)
        remaining.remove(best_idx)

    return [candidate_ids[i] for i in selected]
