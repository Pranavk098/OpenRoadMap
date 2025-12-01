from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer

client = QdrantClient(host="localhost", port=6333)
model = SentenceTransformer("all-MiniLM-L6-v2")

COLLECTION = "educational_resources"

q = [
    "learn machine learning from scratch",
    "introduction to data visualization",
    "deep learning for healthcare",
    "how to build a REST API with Python",
    "basics of probability and statistics"
]
# Encode all queries
vectors = model.encode(q, convert_to_numpy=True).tolist()

print(f"Searching in collection: {COLLECTION}")

for i, query_text in enumerate(q):
    print(f"\nQuery: '{query_text}'")
    try:
        # Try using query_points method
        response = client.query_points(
            collection_name=COLLECTION,
            query=vectors[i],
            limit=5,
            with_payload=True
        )
        hits = response.points
        
        for h in hits:
            print(f"  - Score: {h.score:.4f}, Title: {h.payload.get('title')}")
            
    except AttributeError:
        print("client.query_points failed.")
    except Exception as e:
        print(f"An error occurred: {e}")
