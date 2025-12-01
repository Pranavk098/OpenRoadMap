import json
import os
import random

# Configuration
INPUT_CORPUS = os.path.join("data", "processed", "unified_corpus.json")
OUTPUT_FILE = os.path.join("data", "evaluation", "retrieval_ground_truth.json")
SAMPLE_SIZE = 50

def generate_ground_truth():
    if not os.path.exists(INPUT_CORPUS):
        print(f"Error: Corpus file not found at {INPUT_CORPUS}")
        print("Please run the ingestion and processing scripts first.")
        return

    print(f"Loading corpus from {INPUT_CORPUS}...")
    with open(INPUT_CORPUS, 'r', encoding='utf-8') as f:
        corpus = json.load(f)

    if len(corpus) < SAMPLE_SIZE:
        print(f"Warning: Corpus has fewer items ({len(corpus)}) than sample size ({SAMPLE_SIZE}). Using all items.")
        sample = corpus
    else:
        sample = random.sample(corpus, SAMPLE_SIZE)

    ground_truth = []
    
    print("Generating synthetic queries...")
    for item in sample:
        # Strategy: Use the title as the query (Known-Item Search)
        query = item['title']
        
        # Create the ground truth entry
        entry = {
            "query": query,
            "relevant_resource_ids": [item['id']],
            "difficulty": "easy", # Exact title match is considered easy
            "source_item": {
                "title": item['title'],
                "source": item['source']
            }
        }
        ground_truth.append(entry)

    # Ensure output directory exists
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

    print(f"Saving {len(ground_truth)} ground truth items to {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(ground_truth, f, indent=2)

    print("Ground truth generation complete.")

if __name__ == "__main__":
    generate_ground_truth()
