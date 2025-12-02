from ..models import RoadmapResponse
import warnings

# Suppress warnings for cleaner output
warnings.filterwarnings("ignore")

class EvaluationAgent:
    def __init__(self):
        # Lazy load rouge_scorer only when needed or initialize as None
        self._rouge_scorer = None

    @property
    def rouge_scorer(self):
        if self._rouge_scorer is None:
            from rouge_score import rouge_scorer
            self._rouge_scorer = rouge_scorer.RougeScorer(['rougeL'], use_stemmer=True)
        return self._rouge_scorer

    def evaluate_roadmap_structure(self, generated_roadmap: RoadmapResponse, ground_truth_topics: list[str]) -> dict:
        """
        Evaluates the roadmap structure using BERTScore and ROUGE-L.
        Compares generated node titles against ground truth topics.
        """
        generated_topics = [node.title for node in generated_roadmap.nodes]
        
        # 1. ROUGE-L (Longest Common Subsequence)
        # Treat the list of topics as a single sequence/sentence
        gen_seq = " ".join(generated_topics)
        ref_seq = " ".join(ground_truth_topics)
        rouge_scores = self.rouge_scorer.score(ref_seq, gen_seq)
        rouge_l = rouge_scores['rougeL'].fmeasure

        # 2. BERTScore (Semantic Similarity)
        # We compare the list of topics. If lengths differ, we might need to align them or just compare as strings.
        # For simplicity, we compare the full sequence string.
        try:
            from bert_score import score as bert_score
            P, R, F1 = bert_score([gen_seq], [ref_seq], lang="en", verbose=False)
            bert_f1 = F1.mean().item()
        except Exception as e:
            print(f"BERTScore calculation failed: {e}")
            bert_f1 = 0.0

        return {
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
        # Create binary relevance array for top-k
        relevance_scores = [1 if res in relevant_resources else 0 for res in top_k]
        
        # Pad with zeros if less than k items retrieved
        if len(relevance_scores) < k:
            relevance_scores += [0] * (k - len(relevance_scores))
            
        # Ideal relevance (all 1s for the number of relevant items found, or min(k, total_relevant))
        ideal_relevance = [1] * min(k, total_relevant) + [0] * (k - min(k, total_relevant))
        
        # Calculate NDCG
        # ndcg_score expects 2D arrays (samples x items)
        try:
            from sklearn.metrics import ndcg_score
            ndcg_k = ndcg_score([ideal_relevance], [relevance_scores], k=k)
        except Exception as e:
            print(f"NDCG calculation failed: {e}")
            ndcg_k = 0.0

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
