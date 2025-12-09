import json
import os
import random
import sys
from dotenv import load_dotenv
from openai import OpenAI

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src')))
from dependencies import get_openai_client

load_dotenv()

CORPUS_PATH = os.path.join("data", "processed", "unified_corpus.json")
OUTPUT_PATH = os.path.join("data", "evaluation", "graded_ground_truth.json")
NUM_SAMPLES = 20  # Generate 20 samples for testing (can increase later)

def generate_synthetic_data():
    if not os.path.exists(CORPUS_PATH):
        print(f"Error: Corpus not found at {CORPUS_PATH}")
        return

    print("Loading corpus...")
    with open(CORPUS_PATH, 'r', encoding='utf-8') as f:
        corpus = json.load(f)

    # Filter for high quality items (e.g., Coursera/EdX)
    candidates = [item for item in corpus if item.get('source') in ['Coursera', 'edX']]
    if len(candidates) < NUM_SAMPLES:
        candidates = corpus
    
    samples = random.sample(candidates, min(len(candidates), NUM_SAMPLES))
    
    client = get_openai_client()
    synthetic_data = []

    print(f"Generating synthetic queries for {len(samples)} items...")
    
    for i, item in enumerate(samples):
        print(f"Processing {i+1}/{len(samples)}: {item['title']}")
        
        prompt = f"""
        I have a learning resource with the following details:
        Title: {item['title']}
        Description: {item['description'][:300]}...
        
        Generate 3 distinct search queries that a user might type to find this resource.
        Assign a relevance score (1-3) to each query based on how specific it is to this resource.
        
        3 = Perfect Match (The query is looking for exactly this topic or title)
        2 = Relevant (The query is looking for this general subject)
        1 = Broad/Tangential (The query is related but very broad)
        
        Format the output as a JSON object with keys "queries" which is a list of objects {{"query": "...", "score": ...}}.
        Do not include markdown formatting.
        """
        
        try:
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                response_format={"type": "json_object"}
            )
            
            content = response.choices[0].message.content
            data = json.loads(content)
            
            for q in data.get("queries", []):
                synthetic_data.append({
                    "query": q["query"],
                    "relevant_resources": {item['id']: q["score"]},
                    "difficulty": "easy" if q["score"] == 3 else "medium" if q["score"] == 2 else "hard",
                    "source_item": {
                        "title": item['title'],
                        "source": item.get('source', 'Unknown')
                    }
                })
                
        except Exception as e:
            print(f"Failed to generate for item {item['id']}: {e}")

    print(f"Saving {len(synthetic_data)} synthetic test cases to {OUTPUT_PATH}...")
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(synthetic_data, f, indent=2)
    print("Done!")

if __name__ == "__main__":
    generate_synthetic_data()
