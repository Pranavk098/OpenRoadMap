import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.reranker import mmr_rerank


def test_mmr_reduces_redundancy_vs_pure_relevance_ranking():
    """
    Constructed example: candidate A is the most relevant, candidate B is a
    near-duplicate of A (also highly relevant), candidate C is diverse
    (orthogonal to the query, low relevance).

    Pure relevance ranking (sorted by similarity to the query) would pick
    [A, B] for the top 2 - two near-identical documents.

    MMR with a real diversity weight should prefer C over the redundant B
    for the second slot, because B adds almost nothing once A is selected.
    """
    query = np.array([1.0, 0.0, 0.0])
    vectors = np.array([
        [0.99, 0.14, 0.0],   # A: close to query -> most relevant
        [0.985, 0.17, 0.0],  # B: near-duplicate of A -> also highly relevant, redundant
        [0.3, -0.9, 0.0],    # C: far from A -> lower relevance, but diverse
    ])
    ids = ["A", "B", "C"]

    # Sanity check: pure relevance order really would be [A, B, C].
    relevance = vectors @ query / np.linalg.norm(vectors, axis=1)
    pure_relevance_order = [ids[i] for i in np.argsort(-relevance)]
    assert pure_relevance_order == ["A", "B", "C"]

    # lambda=1.0 -> pure relevance, should reproduce the same top-2 as above.
    result_pure = mmr_rerank(query, vectors, ids, k=2, lambda_param=1.0)
    assert result_pure == ["A", "B"]

    # lambda=0.5 -> balances relevance and diversity. B is redundant with A
    # (already selected), so C should be preferred for the second slot.
    result_mmr = mmr_rerank(query, vectors, ids, k=2, lambda_param=0.5)
    assert result_mmr == ["A", "C"]


def test_mmr_rerank_respects_k():
    query = np.array([1.0, 0.0])
    vectors = np.array([[1.0, 0.0], [0.9, 0.1], [0.0, 1.0], [0.5, 0.5]])
    ids = ["A", "B", "C", "D"]

    result = mmr_rerank(query, vectors, ids, k=2)
    assert len(result) == 2
    assert set(result).issubset(set(ids))


def test_mmr_rerank_k_larger_than_candidates_returns_all():
    query = np.array([1.0, 0.0])
    vectors = np.array([[1.0, 0.0], [0.0, 1.0]])
    ids = ["A", "B"]

    result = mmr_rerank(query, vectors, ids, k=10)
    assert len(result) == 2
    assert set(result) == {"A", "B"}


def test_mmr_rerank_empty_candidates():
    query = np.array([1.0, 0.0])
    vectors = np.zeros((0, 2))
    ids = []

    assert mmr_rerank(query, vectors, ids, k=5) == []
