"""
Shared, framework-free evaluation metrics.

These functions operate only on plain Python lists / numpy arrays - no
sklearn, no pydantic, no agent/framework classes - so they can be unit
tested in isolation and imported by both the EvaluationAgent
(src/agents/eval_agent.py) and the offline evaluation scripts
(scripts/evaluation/*.py) without pulling framework dependencies into
either side.
"""
import math

import numpy as np


def dcg_at_k(relevance: list, k: int) -> float:
    """Discounted Cumulative Gain at k.

    relevance: binary (or graded) relevance scores, IN RETRIEVED ORDER.
    Standard formula: sum(rel_i / log2(i + 2)) for i in [0, k).
    """
    relevance = relevance[:k]
    if not relevance:
        return 0.0
    return sum(rel / math.log2(idx + 2) for idx, rel in enumerate(relevance))


def ndcg_at_k(relevance: list, k: int) -> float:
    """Normalized DCG at k.

    Normalizes DCG@k by the DCG of the ideal ordering (relevance sorted
    descending).

    This replaces the previous `sklearn.metrics.ndcg_score` usage in
    eval_agent.py, which fed it a synthetic "all 1s then 0s" array as
    y_true instead of a real relevance judgment - ndcg_score expects
    y_true to be graded relevance labels and y_score to be predicted
    scores, so that call was computing a number with no defined meaning.
    """
    ideal_dcg = dcg_at_k(sorted(relevance, reverse=True), k)
    if not ideal_dcg:
        return 0.0
    return dcg_at_k(relevance, k) / ideal_dcg


# Cosine similarity threshold above which a (generated topic, gold topic)
# pair counts as a match in bipartite_topic_alignment. 0.6 on sentence-level
# embeddings (e.g. fastembed's bge-small-en-v1.5) sits comfortably above
# noise/unrelated-topic similarity while still catching paraphrases and
# vocabulary shifts ("REST APIs" <-> "Web APIs and HTTP"). It is a
# conservative, documented default - not tuned against this project's own
# ground truth - and is exposed as a constant so it can be revisited.
TOPIC_MATCH_THRESHOLD = 0.6


def cosine_similarity_matrix(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Pairwise cosine similarity between rows of a (n x d) and b (m x d)."""
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    a_norm = a / (np.linalg.norm(a, axis=1, keepdims=True) + 1e-10)
    b_norm = b / (np.linalg.norm(b, axis=1, keepdims=True) + 1e-10)
    return a_norm @ b_norm.T


def bipartite_topic_alignment(
    generated_embeddings: np.ndarray,
    gold_embeddings: np.ndarray,
    threshold: float = TOPIC_MATCH_THRESHOLD,
) -> dict:
    """Greedy bipartite matching between generated topics and gold topics.

    This is the PRIMARY "did we cover the right topics" signal, replacing
    ROUGE-L. The actual comparison is between two *unordered sets* of
    topics of different sizes (~6 generated node titles vs ~20 gold
    topics) - a set-coverage question, not a sequence-alignment question,
    which is why a sequence metric like ROUGE-L produces a misleadingly
    low score here.

    Matching strategy is greedy nearest-unclaimed-match over the full
    similarity matrix (highest similarity pairs claimed first), not an
    optimal (Hungarian) assignment - deliberately, to avoid adding scipy
    as a dependency for what is a small matching problem (~5-20 items per
    side). This is not globally optimal but is simple, fast, and a
    reasonable approximation at this scale.

    Args:
        generated_embeddings: (n_gen, d) embeddings of generated topics.
        gold_embeddings: (n_gold, d) embeddings of gold/ground-truth topics.
        threshold: minimum cosine similarity for a pair to count as a match.

    Returns:
        dict with:
            coverage: fraction of gold topics matched to some generated
                topic above `threshold` (did we hit everything needed?).
            precision: fraction of generated topics matched to some gold
                topic above `threshold` (did we avoid padding with junk?).
            matches: list of (generated_idx, gold_idx, similarity) tuples
                for each matched pair.
    """
    n_gen = len(generated_embeddings)
    n_gold = len(gold_embeddings)

    if n_gen == 0 or n_gold == 0:
        return {"coverage": 0.0, "precision": 0.0, "matches": []}

    sims = cosine_similarity_matrix(np.asarray(generated_embeddings), np.asarray(gold_embeddings))

    candidates = []
    for gi in range(n_gen):
        for gj in range(n_gold):
            if sims[gi, gj] >= threshold:
                candidates.append((sims[gi, gj], gi, gj))
    candidates.sort(reverse=True, key=lambda x: x[0])

    matched_gen = set()
    matched_gold = set()
    matches = []
    for sim, gi, gj in candidates:
        if gi in matched_gen or gj in matched_gold:
            continue
        matched_gen.add(gi)
        matched_gold.add(gj)
        matches.append((gi, gj, float(sim)))

    coverage = len(matched_gold) / n_gold
    precision = len(matched_gen) / n_gen

    return {"coverage": coverage, "precision": precision, "matches": matches}
