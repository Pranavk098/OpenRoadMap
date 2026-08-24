import os
from qdrant_client import QdrantClient, AsyncQdrantClient
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()

# Qdrant Setup
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
COLLECTION_NAME = os.getenv("QDRANT_COLLECTION", "educational_resources")


def get_qdrant_client() -> QdrantClient:
    """Sync client, kept for scripts/tools that aren't async."""
    return QdrantClient(url=QDRANT_URL)


def get_async_qdrant_client() -> AsyncQdrantClient:
    return AsyncQdrantClient(url=QDRANT_URL)


# OpenAI Setup
def get_openai_client() -> AsyncOpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable is not set")
    return AsyncOpenAI(api_key=api_key)
