import json
import os
import math
import sys
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.getcwd())

load_dotenv()

# Configuration
GROUND_TRUTH_FILE = os.path.join("data", "evaluation", "retrieval_ground_truth.json")
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
TOP_K = 5

def dcg_at_k(r, k):
    r = r[:k]
    if r:
        return sum([rel / math.log2(idx + 2) for idx, rel in enumerate(r)])
    return 0.0

def ndcg_at_k(r, k):
    dcg_max = dcg_at_k(sorted(r, reverse=True), k)
    if not dcg_max:
        return 0.0
    return dcg_at_k(r, k) / dcg_max

def evaluate_retrieval():
    if not os.path.exists(GROUND_TRUTH_FILE):
        print(f"Error: Ground truth file not found at {GROUND_TRUTH_FILE}")
        return

    print(f"Loading ground truth from {GROUND_TRUTH_FILE}...")
    with open(GROUND_TRUTH_FILE, 'r', encoding='utf-8') as f:
        ground_truth = json.load(f)

    # Initialize ResourceAgent
    try:
        from src.agents.resource_agent import ResourceAgent
        resource_agent = ResourceAgent()
    except ImportError as e:
        print(f"Error importing ResourceAgent: {e}")
        return

    total_recall = 0.0
    total_ndcg = 0.0
    count = 0

    print(f"Evaluating {len(ground_truth)} queries...")
    
    for item in ground_truth:
        query = item['query']
        relevant_ids = set(item['relevant_resource_ids'])
        
        retrieved_ids = []
        try:
            # find_resources returns Resource objects
            resources = resource_agent.find_resources(query, limit=TOP_K)
            # Extract IDs from resources
            retrieved_ids = [res.id for res in resources if res.id]
        except Exception as e:
            print(f"Search failed for '{query}': {e}")
            retrieved_ids = []
        
        # Calculate Recall@K
        # Recall = (Relevant Retrieved) / (Total Relevant)
        relevant_retrieved = sum(1 for rid in retrieved_ids if rid in relevant_ids)
        recall = relevant_retrieved / len(relevant_ids) if relevant_ids else 0.0
        
        # Calculate NDCG@K
        # Relevance list: 1 if ID is relevant, 0 otherwise
        relevance_list = [1 if rid in relevant_ids else 0 for rid in retrieved_ids]
        ndcg = ndcg_at_k(relevance_list, TOP_K)
        
        total_recall += recall
        total_ndcg += ndcg
        count += 1

    if count == 0:
        print("No queries evaluated.")
        return

    avg_recall = total_recall / count
    avg_ndcg = total_ndcg / count

    print("-" * 30)
    print(f"Evaluation Results (Top-{TOP_K})")
    print("-" * 30)
    print(f"Queries Evaluated: {count}")
    print(f"Average Recall@{TOP_K}: {avg_recall:.4f}")
    print(f"Average NDCG@{TOP_K}:   {avg_ndcg:.4f}")
    print("-" * 30)

if __name__ == "__main__":
    evaluate_retrieval()
