import json
import os
import sys

import numpy as np
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.getcwd())

from src.metrics import ndcg_at_k
from src.reranker import mmr_rerank

load_dotenv()

# Configuration
#
# Two separate ground-truth sets are evaluated against (see
# generate_synthetic_ground_truth.py):
#   GROUND_TRUTH_FILE           - "known-item search": query = the corpus
#                                  item's own title. Easy - any reasonable
#                                  dense retriever should ace an
#                                  (near-)exact string match.
#   GROUND_TRUTH_FILE_REALISTIC - "learner-phrased": query = a heuristically
#                                  generated natural-language search phrase
#                                  ("how to learn react hooks"), not the
#                                  catalog title. Harder, more representative
#                                  of real usage.
GROUND_TRUTH_FILE = os.path.join("data", "evaluation", "retrieval_ground_truth.json")
GROUND_TRUTH_FILE_REALISTIC = os.path.join("data", "evaluation", "retrieval_ground_truth_realistic.json")
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
TOP_K = 5
MMR_CANDIDATE_POOL = 20  # candidates fetched before MMR re-ranks down to TOP_K
MMR_LAMBDA = 0.5  # relevance/diversity tradeoff; see src/reranker.py
EMBEDDING_MODEL_NAME = "BAAI/bge-small-en-v1.5"


def _load_ground_truth(path: str):
    if not os.path.exists(path):
        raise FileNotFoundError(f"Ground truth file not found at {path}")
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def evaluate_retrieval(variant: str = "baseline", ground_truth_file: str = GROUND_TRUTH_FILE) -> dict:
    """
    Runs the retrieval evaluation harness against a running Qdrant instance.

    variant:
        "baseline" - dense-only ResourceAgent ranking, top TOP_K. This is a
                     real, existing technique (the current serving path),
                     not "MultiFactor"/"CrossEncoder" - those never existed
                     in this codebase.
        "mmr"      - fetches a larger candidate pool via ResourceAgent, then
                     applies MMR diversity re-ranking (src/reranker.py) down
                     to TOP_K. Also real - implemented in this track.

    ground_truth_file: which ground-truth set to evaluate against (see
        GROUND_TRUTH_FILE vs GROUND_TRUTH_FILE_REALISTIC above).

    Raises if Qdrant is not reachable, rather than silently falling through
    to ResourceAgent's web-search fallback - a DuckDuckGo fallback result
    would never match the synthetic corpus IDs in the ground truth, which
    would produce real-looking recall/ndcg numbers that are actually
    meaningless (they'd just measure "the web fallback doesn't know our
    corpus IDs", not retrieval quality).
    """
    ground_truth = _load_ground_truth(ground_truth_file)

    from src.agents.resource_agent import ResourceAgent
    resource_agent = ResourceAgent()

    try:
        resource_agent.qdrant_client.get_collections()
    except Exception as e:
        raise RuntimeError(f"Qdrant not reachable at {QDRANT_URL}: {e}")

    embedder = None
    if variant == "mmr":
        from fastembed import TextEmbedding
        embedder = TextEmbedding(model_name=EMBEDDING_MODEL_NAME)

    total_recall = 0.0
    total_ndcg = 0.0
    count = 0

    print(f"Evaluating {len(ground_truth)} queries [variant={variant}]...")

    for item in ground_truth:
        query = item['query']
        relevant_ids = set(item['relevant_resource_ids'])

        retrieved_ids = []
        try:
            if variant == "mmr":
                pool = resource_agent.find_resources(query, limit=MMR_CANDIDATE_POOL)
                if pool:
                    texts = [f"{r.title} {r.description}" for r in pool]
                    doc_vectors = np.array(list(embedder.embed(texts)))
                    query_vector = np.array(list(embedder.embed([query]))[0])
                    ids = [r.id for r in pool]
                    retrieved_ids = [
                        rid for rid in mmr_rerank(query_vector, doc_vectors, ids, k=TOP_K, lambda_param=MMR_LAMBDA)
                        if rid
                    ]
            else:
                resources = resource_agent.find_resources(query, limit=TOP_K)
                retrieved_ids = [res.id for res in resources if res.id]
        except Exception as e:
            print(f"Search failed for '{query}' [{variant}]: {e}")
            retrieved_ids = []

        # Recall@K = (Relevant Retrieved) / (Total Relevant)
        relevant_retrieved = sum(1 for rid in retrieved_ids if rid in relevant_ids)
        recall = relevant_retrieved / len(relevant_ids) if relevant_ids else 0.0

        # NDCG@K: binary relevance in retrieved order
        relevance_list = [1 if rid in relevant_ids else 0 for rid in retrieved_ids]
        ndcg = ndcg_at_k(relevance_list, TOP_K)

        total_recall += recall
        total_ndcg += ndcg
        count += 1

    if count == 0:
        return {"queries_evaluated": 0, f"avg_recall@{TOP_K}": 0.0, f"avg_ndcg@{TOP_K}": 0.0}

    return {
        "queries_evaluated": count,
        f"avg_recall@{TOP_K}": total_recall / count,
        f"avg_ndcg@{TOP_K}": total_ndcg / count,
    }


def main():
    for gt_label, gt_file in (("known_item_search", GROUND_TRUTH_FILE), ("realistic_learner_phrased", GROUND_TRUTH_FILE_REALISTIC)):
        if not os.path.exists(gt_file):
            print(f"Ground truth set '{gt_label}' not found at {gt_file}, skipping.")
            continue
        for variant in ("baseline", "mmr"):
            try:
                results = evaluate_retrieval(variant, ground_truth_file=gt_file)
            except Exception as e:
                print(f"[{gt_label}] Variant '{variant}' unavailable: {e}")
                continue

            print("-" * 30)
            print(f"Evaluation Results (Top-{TOP_K}, ground_truth={gt_label}, variant={variant})")
            print("-" * 30)
            print(f"Queries Evaluated: {results['queries_evaluated']}")
            print(f"Average Recall@{TOP_K}: {results[f'avg_recall@{TOP_K}']:.4f}")
            print(f"Average NDCG@{TOP_K}:   {results[f'avg_ndcg@{TOP_K}']:.4f}")
            print("-" * 30)


if __name__ == "__main__":
    main()
