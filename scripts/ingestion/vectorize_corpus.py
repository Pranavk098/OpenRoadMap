import json
import os
import time

from dotenv import load_dotenv
from fastembed import SparseTextEmbedding, TextEmbedding
from qdrant_client import QdrantClient
from qdrant_client.models import (
    CreateAlias,
    CreateAliasOperation,
    DeleteAlias,
    DeleteAliasOperation,
    Distance,
    PointStruct,
    SparseVector,
    SparseVectorParams,
    VectorParams,
)

load_dotenv()

# Configuration
INPUT_FILE = os.path.join("data", "processed", "unified_corpus.json")
COLLECTION_ALIAS = os.getenv("QDRANT_COLLECTION", "educational_resources")
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY") or None

# Same models as src/agents/resource_agent.py so query-time and index-time
# vectors live in the same embedding spaces (dense semantic + sparse lexical).
DENSE_MODEL_NAME = "BAAI/bge-base-en-v1.5"
DENSE_VECTOR_SIZE = 768
SPARSE_MODEL_NAME = "Qdrant/bm42-all-minilm-l6-v2-attentions"

DENSE_VECTOR_NAME = "dense"
SPARSE_VECTOR_NAME = "sparse"


def _current_alias_target(client: QdrantClient, alias_name: str) -> str | None:
    """Returns the collection name the alias currently points to, or None
    if the alias doesn't exist yet (e.g. first-ever ingest)."""
    aliases = client.get_aliases().aliases
    for a in aliases:
        if a.alias_name == alias_name:
            return a.collection_name
    return None


def vectorize_corpus():
    if not os.path.exists(INPUT_FILE):
        print(f"Error: Unified corpus not found at {INPUT_FILE}")
        return

    print(f"Loading corpus from {INPUT_FILE}...")
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        corpus = json.load(f)

    print(f"Loading dense model {DENSE_MODEL_NAME}...")
    dense_model = TextEmbedding(DENSE_MODEL_NAME)
    print(f"Loading sparse model {SPARSE_MODEL_NAME}...")
    sparse_model = SparseTextEmbedding(SPARSE_MODEL_NAME)

    print(f"Connecting to Qdrant at {QDRANT_URL}...")
    client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

    # Ingest into a fresh, timestamped collection rather than
    # recreate_collection()'ing the live one - recreate_collection destroys
    # the index in place (no incremental reindex, readers see an empty
    # collection mid-ingest) and is deprecated in current qdrant-client.
    # Instead: build the new collection fully, then atomically flip the
    # alias the app reads from, then drop the old collection.
    new_collection_name = f"{COLLECTION_ALIAS}_{int(time.time())}"
    print(f"Creating new collection '{new_collection_name}'...")
    client.create_collection(
        collection_name=new_collection_name,
        vectors_config={DENSE_VECTOR_NAME: VectorParams(size=DENSE_VECTOR_SIZE, distance=Distance.COSINE)},
        sparse_vectors_config={SPARSE_VECTOR_NAME: SparseVectorParams()},
    )

    print("Generating embeddings and indexing...")
    batch_size = 100
    total = len(corpus)

    for i in range(0, total, batch_size):
        batch = corpus[i : i + batch_size]

        # Prepare text for embedding (Title + Description). Uses
        # passage_embed (not query_embed) since these are indexed documents,
        # not search queries - matters for asymmetric models like bge.
        texts = [f"{item['title']}: {item['description']}" for item in batch]
        dense_embeddings = list(dense_model.passage_embed(texts))
        sparse_embeddings = list(sparse_model.passage_embed(texts))

        points = []
        for j, item in enumerate(batch):
            sparse_vec = sparse_embeddings[j]
            points.append(
                PointStruct(
                    id=item["id"],
                    vector={
                        DENSE_VECTOR_NAME: dense_embeddings[j].tolist(),
                        SPARSE_VECTOR_NAME: SparseVector(
                            indices=sparse_vec.indices.tolist(),
                            values=sparse_vec.values.tolist(),
                        ),
                    },
                    payload={
                        "title": item["title"],
                        "description": item["description"],
                        "url": item["url"],
                        "source": item["source"],
                        "content_type": item["content_type"],
                        "quality_score": item["quality_score"],
                    },
                )
            )

        client.upsert(collection_name=new_collection_name, points=points)
        print(f"Processed {min(i + batch_size, total)}/{total} records")

    old_collection_name = _current_alias_target(client, COLLECTION_ALIAS)

    print(f"Swapping alias '{COLLECTION_ALIAS}' -> '{new_collection_name}'...")
    operations = []
    if old_collection_name is not None:
        operations.append(DeleteAliasOperation(delete_alias=DeleteAlias(alias_name=COLLECTION_ALIAS)))
    operations.append(
        CreateAliasOperation(
            create_alias=CreateAlias(collection_name=new_collection_name, alias_name=COLLECTION_ALIAS)
        )
    )
    client.update_collection_aliases(change_aliases_operations=operations)

    if old_collection_name and old_collection_name != new_collection_name:
        print(f"Deleting old collection '{old_collection_name}'...")
        client.delete_collection(collection_name=old_collection_name)

    print("Vectorization and indexing complete.")


if __name__ == "__main__":
    vectorize_corpus()
