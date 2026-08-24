import warnings

import numpy as np

from ..metrics import TOPIC_MATCH_THRESHOLD, bipartite_topic_alignment, ndcg_at_k
from ..models import RoadmapResponse

# Suppress warnings for cleaner output
warnings.filterwarnings("ignore")

class EvaluationAgent:
    def __init__(self):
        # Lazy load rouge_scorer / embedding model only when needed
        self._rouge_scorer = None
        self._embedding_model = None

    @property
    def rouge_scorer(self):
        if self._rouge_scorer is None:
            from rouge_score import rouge_scorer
            self._rouge_scorer = rouge_scorer.RougeScorer(['rougeL'], use_stemmer=True)
        return self._rouge_scorer

    @property
    def embedding_model(self):
        # fastembed - same embedding backend used for MMR reranking (see
        # src/reranker.py), so we don't reintroduce torch/sentence-transformers
        # into the eval path.
        if self._embedding_model is None:
            from fastembed import TextEmbedding
            self._embedding_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
        return self._embedding_model

    def evaluate_roadmap_structure(self, generated_roadmap: RoadmapResponse, ground_truth_topics: list[str]) -> dict:
        """
        Evaluates the roadmap structure.

        PRIMARY metric: bipartite topic alignment (coverage / precision).
        Generated node titles and ground-truth topics are embedded and
        greedily matched as two sets by cosine similarity (see
        src/metrics.bipartite_topic_alignment). This is the headline
        "did we cover the right topics" signal.

        SECONDARY / reference metrics: ROUGE-L and BERTScore are still
        computed for continuity, but are NOT the primary signal. Both are
        sequence metrics (order- and length-sensitive), applied here to what
        is actually a set-coverage comparison (~6 generated titles vs ~20
        gold topics) - that mismatch is why ROUGE-L in particular reads as a
        misleadingly low number that reflects the metric choice, not
        generation quality.
        """
        generated_topics = [node.title for node in generated_roadmap.nodes]

        # --- PRIMARY: bipartite topic alignment ---
        gen_embeddings = (
            np.array(list(self.embedding_model.embed(generated_topics)))
            if generated_topics else np.zeros((0, 0))
        )
        gold_embeddings = (
            np.array(list(self.embedding_model.embed(ground_truth_topics)))
            if ground_truth_topics else np.zeros((0, 0))
        )
        alignment = bipartite_topic_alignment(gen_embeddings, gold_embeddings, threshold=TOPIC_MATCH_THRESHOLD)

        # --- SECONDARY/reference: ROUGE-L (Longest Common Subsequence) ---
        gen_seq = " ".join(generated_topics)
        ref_seq = " ".join(ground_truth_topics)
        rouge_scores = self.rouge_scorer.score(ref_seq, gen_seq)
        rouge_l = rouge_scores['rougeL'].fmeasure

        # --- SECONDARY/reference: BERTScore (Semantic Similarity) ---
        try:
            from bert_score import score as bert_score
            P, R, F1 = bert_score([gen_seq], [ref_seq], lang="en", verbose=False)
            bert_f1 = F1.mean().item()
        except Exception as e:
            print(f"BERTScore calculation failed: {e}")
            bert_f1 = 0.0

        return {
            "coverage": alignment["coverage"],
            "precision": alignment["precision"],
            "primary_metric": "bipartite_topic_alignment",
            "secondary_metrics_note": (
                "rouge_l and bert_score are secondary/reference metrics only. "
                "Both are order/length-sensitive sequence metrics applied to what "
                "is really a set-coverage comparison; coverage/precision above are primary."
            ),
            "rouge_l": rouge_l,
            "bert_score": bert_f1,
            "generated_topics": generated_topics,
            "ground_truth_topics": ground_truth_topics
        }

    def evaluate_resources(self, retrieved_resources: list[str], relevant_resources: list[str], k: int = 5) -> dict:
        """
        Evaluates resource retrieval using Recall@k and NDCG@k.
        retrieved_resources: List of URLs/IDs retrieved by the system (ranked).
        relevant_resources: Set/List of relevant URLs/IDs (ground truth).
        """
        # Truncate to top-k
        top_k = retrieved_resources[:k]

        # 1. Recall@k
        # Count how many relevant items are in the top-k
        hits = sum(1 for res in top_k if res in relevant_resources)
        total_relevant = len(relevant_resources)
        recall_k = hits / total_relevant if total_relevant > 0 else 0.0

        # 2. NDCG@k
        # Binary relevance array for top-k, in retrieved order, padded to k.
        relevance_scores = [1 if res in relevant_resources else 0 for res in top_k]
        if len(relevance_scores) < k:
            relevance_scores += [0] * (k - len(relevance_scores))

        ndcg_k = ndcg_at_k(relevance_scores, k)

        return {
            f"recall@{k}": recall_k,
            f"ndcg@{k}": ndcg_k
        }

    def evaluate(self, roadmap: RoadmapResponse) -> dict:
        """
        Legacy simple evaluation (kept for backward compatibility).
        """
        node_count = len(roadmap.nodes)
        resource_count = sum(len(node.resources) for node in roadmap.nodes)

        score = 1.0
        feedback = "Roadmap looks good."

        if node_count < 3:
            score -= 0.2
            feedback = "Roadmap is a bit short."

        if resource_count == 0:
            score -= 0.5
            feedback = "No resources found for any topic."

        return {
            "score": score,
            "feedback": feedback,
            "metrics": {
                "node_count": node_count,
                "resource_count": resource_count
            }
        }
