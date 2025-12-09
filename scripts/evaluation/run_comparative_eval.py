import json
import os
import sys
import numpy as np
from dotenv import load_dotenv

# Add PROJECT ROOT to path (one level up from scripts/evaluation, then two levels up from scripts)
# Actually, the script is in scripts/evaluation.
# __file__ = scripts/evaluation/run_comparative_eval.py
# dirname = scripts/evaluation
# ../.. = project root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from src.agents.resource_agent import ResourceAgent
from src.agents.eval_agent import EvaluationAgent

load_dotenv()

GROUND_TRUTH_PATH = os.path.join("data", "evaluation", "graded_ground_truth.json")

def run_comparative_eval():
    if not os.path.exists(GROUND_TRUTH_PATH):
        print(f"Error: Ground truth not found at {GROUND_TRUTH_PATH}")
        print("Please run 'python scripts/evaluation/generate_synthetic_data.py' first.")
        return

    print("Loading graded ground truth...")
    with open(GROUND_TRUTH_PATH, 'r', encoding='utf-8') as f:
        test_cases = json.load(f)

    agent = ResourceAgent()
    evaluator = EvaluationAgent()
    
    baseline_metrics = {"recall@5": [], "ndcg@5": []}
    advanced_metrics = {"recall@5": [], "ndcg@5": []}
    
    print(f"Running evaluation on {len(test_cases)} test cases...")
    print("-" * 60)
    
    for i, case in enumerate(test_cases):
        query = case["query"]
        relevant_map = case["relevant_resources"] # {id: score}
        
        print(f"Test {i+1}: '{query}'")
        
        # --- 1. Baseline (No Expansion) ---
        # We temporarily disable expansion by mocking the method or just calling find_resources 
        # but find_resources has expansion hardcoded. 
        # Let's hack it: we'll manually search Qdrant with just the original query here.
        # This mimics the "Old" behavior.
        
        try:
            # Manual single vector search (Baseline)
            query_vector = list(agent.model.embed(query))[0]
            baseline_results = agent.qdrant_client.query_points(
                collection_name="educational_resources",
                query=query_vector,
                limit=5,
                with_payload=True
            ).points
            baseline_ids = [str(p.id) for p in baseline_results]
        except Exception as e:
            print(f"Baseline failed: {e}")
            baseline_ids = []

        b_scores = evaluator.evaluate_resources(baseline_ids, relevant_map, k=5)
        baseline_metrics["recall@5"].append(b_scores["recall@5"])
        baseline_metrics["ndcg@5"].append(b_scores["ndcg@5"])
        
        # --- 2. Advanced (With Expansion) ---
        # This uses the new ResourceAgent logic we just wrote
        advanced_res_objs = agent.find_resources(query, limit=5)
        advanced_ids = [res.id for res in advanced_res_objs]
        
        a_scores = evaluator.evaluate_resources(advanced_ids, relevant_map, k=5)
        advanced_metrics["recall@5"].append(a_scores["recall@5"])
        advanced_metrics["ndcg@5"].append(a_scores["ndcg@5"])
        
        print(f"  Baseline -> NDCG: {b_scores['ndcg@5']:.4f}")
        print(f"  Advanced -> NDCG: {a_scores['ndcg@5']:.4f}")
        if a_scores['ndcg@5'] > b_scores['ndcg@5']:
            print("  ✅ Improved!")
        elif a_scores['ndcg@5'] < b_scores['ndcg@5']:
            print("  🔻 Regressed")
        else:
            print("  ➖ Same")
            
    print("-" * 60)
    print("FINAL RESULTS")
    print("-" * 60)
    
    b_mean_recall = np.mean(baseline_metrics["recall@5"])
    b_mean_ndcg = np.mean(baseline_metrics["ndcg@5"])
    
    a_mean_recall = np.mean(advanced_metrics["recall@5"])
    a_mean_ndcg = np.mean(advanced_metrics["ndcg@5"])
    
    print(f"Metric      | Baseline | Advanced | Change")
    print(f"------------|----------|----------|-------")
    print(f"Recall@5    | {b_mean_recall:.4f}   | {a_mean_recall:.4f}   | {(a_mean_recall - b_mean_recall):+.4f}")
    print(f"NDCG@5      | {b_mean_ndcg:.4f}   | {a_mean_ndcg:.4f}   | {(a_mean_ndcg - b_mean_ndcg):+.4f}")

if __name__ == "__main__":
    run_comparative_eval()
