import math
import sys
import os

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.metrics import dcg_at_k, ndcg_at_k, cosine_similarity_matrix, bipartite_topic_alignment


def test_dcg_at_k_hand_computed():
    # relevance = [1, 0, 1] at k=3
    # DCG = 1/log2(2) + 0/log2(3) + 1/log2(4) = 1 + 0 + 0.5 = 1.5
    relevance = [1, 0, 1]
    expected = 1 / math.log2(2) + 0 / math.log2(3) + 1 / math.log2(4)
    assert dcg_at_k(relevance, 3) == pytest.approx(expected)
    assert expected == pytest.approx(1.5)


def test_ndcg_at_k_hand_computed():
    # relevance = [1, 0, 1] at k=3.
    # DCG = 1.5 (see test_dcg_at_k_hand_computed).
    # Ideal ordering = [1, 1, 0] -> DCG = 1/log2(2) + 1/log2(3) + 0/log2(4)
    #                              = 1 + 0.6309297535714574 = 1.6309297535714574
    # NDCG = 1.5 / 1.6309297535714574 = 0.9197207891481876
    relevance = [1, 0, 1]
    result = ndcg_at_k(relevance, 3)
    assert result == pytest.approx(0.9197207891481876)


def test_ndcg_at_k_perfect_ranking_is_one():
    # Already-ideal ordering should score a perfect 1.0.
    relevance = [1, 1, 0, 0]
    assert ndcg_at_k(relevance, 4) == pytest.approx(1.0)


def test_ndcg_at_k_all_zero_relevance_is_zero():
    # No relevant items at all -> ideal DCG is 0 -> defined as 0, not NaN/inf.
    relevance = [0, 0, 0]
    assert ndcg_at_k(relevance, 3) == 0.0


def test_cosine_similarity_matrix_identical_vectors():
    a = np.array([[1.0, 0.0], [0.0, 1.0]])
    sims = cosine_similarity_matrix(a, a)
    assert sims[0, 0] == pytest.approx(1.0)
    assert sims[1, 1] == pytest.approx(1.0)
    assert sims[0, 1] == pytest.approx(0.0)


def test_bipartite_topic_alignment_perfect_match():
    # Every generated topic embedding exactly matches a gold topic embedding
    # -> full coverage and full precision.
    gen = np.array([[1.0, 0.0], [0.0, 1.0]])
    gold = np.array([[0.0, 1.0], [1.0, 0.0]])
    result = bipartite_topic_alignment(gen, gold, threshold=0.6)
    assert result["coverage"] == pytest.approx(1.0)
    assert result["precision"] == pytest.approx(1.0)
    assert len(result["matches"]) == 2


def test_bipartite_topic_alignment_partial_coverage_and_precision():
    # 3 gold topics, only 2 have a matching generated topic; 1 extra
    # generated topic matches nothing (junk/padding).
    # gold[0] and gold[1] each have a near-identical generated counterpart;
    # gold[2] has no match; gen[2] is orthogonal to everything (junk).
    gen = np.array([
        [1.0, 0.0, 0.0],   # matches gold[0]
        [0.0, 1.0, 0.0],   # matches gold[1]
        [0.0, 0.0, -1.0],  # matches nothing (anti-correlated with gold[2])
    ])
    gold = np.array([
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
        [0.0, 0.0, 1.0],
    ])
    result = bipartite_topic_alignment(gen, gold, threshold=0.6)
    # 2 of 3 gold topics matched.
    assert result["coverage"] == pytest.approx(2 / 3)
    # 2 of 3 generated topics matched.
    assert result["precision"] == pytest.approx(2 / 3)


def test_bipartite_topic_alignment_empty_inputs():
    empty = np.zeros((0, 0))
    non_empty = np.array([[1.0, 0.0]])
    assert bipartite_topic_alignment(empty, non_empty) == {"coverage": 0.0, "precision": 0.0, "matches": []}
    assert bipartite_topic_alignment(non_empty, empty) == {"coverage": 0.0, "precision": 0.0, "matches": []}


def test_bipartite_topic_alignment_threshold_excludes_weak_matches():
    # Similarity of 0.5 is below the default 0.6 threshold -> no match.
    gen = np.array([[1.0, 1.0]])   # normalized: [0.707, 0.707]
    gold = np.array([[1.0, 0.0]])  # cosine sim with gen[0] = 0.707... actually check below
    result = bipartite_topic_alignment(gen, gold, threshold=0.99)
    assert result["coverage"] == 0.0
    assert result["precision"] == 0.0
