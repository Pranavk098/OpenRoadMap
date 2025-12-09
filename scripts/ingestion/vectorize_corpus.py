import sys
import os

# Add src to path to allow imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src')))

import json
from sentence_transformers import SentenceTransformer
from qdrant_client.models import Distance, VectorParams, PointStruct
from dotenv import load_dotenv
from dependencies import get_qdrant_client, COLLECTION_NAME

load_dotenv()

# Configuration
INPUT_FILE = os.path.join("data", "processed", "unified_corpus.json")
MODEL_NAME = "all-MiniLM-L6-v2"

def vectorize_corpus():
    if not os.path.exists(INPUT_FILE):
        print(f"Error: Unified corpus not found at {INPUT_FILE}")
        return

    print(f"Loading corpus from {INPUT_FILE}...")
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        corpus = json.load(f)
        
    print(f"Loading model {MODEL_NAME}...")
    # Use FastEmbed for consistency with backend
    from fastembed import TextEmbedding
    # Use BAAI/bge-small-en-v1.5 which is supported and high quality (384 dim)
    model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
    
    print(f"Connecting to Qdrant...")
    client = get_qdrant_client()
    
    # Recreate collection
    client.recreate_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=384, distance=Distance.COSINE),
    )
    
    print("Generating embeddings and indexing...")
    batch_size = 100
    total = len(corpus)
    
    for i in range(0, total, batch_size):
        batch = corpus[i:i+batch_size]
        
        # Prepare text for embedding (Title + Description)
        # Prepare text for embedding (Title + Description)
        texts = [f"{item['title']}: {item['description']}" for item in batch]
        # FastEmbed returns a generator, convert to list
        embeddings = list(model.embed(texts))
        
        points = []
        for j, item in enumerate(batch):
            points.append(PointStruct(
                id=item['id'],
                vector=embeddings[j].tolist(),
                payload={
                    "title": item['title'],
                    "description": item['description'],
                    "url": item['url'],
                    "source": item['source'],
                    "content_type": item['content_type'],
                    "quality_score": item['quality_score']
                }
            ))
            
        client.upsert(
            collection_name=COLLECTION_NAME,
            points=points
        )
        print(f"Processed {min(i+batch_size, total)}/{total} records")

    print("Vectorization and indexing complete.")

if __name__ == "__main__":
    vectorize_corpus()
