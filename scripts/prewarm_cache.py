"""Standalone cache prewarm script.

Runs the real generation pipeline (LLM call + resource retrieval) for a
configurable list of topics and writes each result into the roadmap cache
(Redis if REDIS_URL is set, otherwise the in-process LRU - which is only
useful for prewarming if this script's process is the same one serving
requests, so in practice this is meant to be run with REDIS_URL set).

Deliberately NOT run automatically at server startup: this repo has no
OpenAI key or Qdrant instance in some environments, and blocking server
startup on network calls to a third-party API is bad practice regardless.
Instead, a deploy job can invoke this separately, e.g.:

    OPENAI_API_KEY=... QDRANT_URL=... REDIS_URL=... \\
        python scripts/prewarm_cache.py "Learn Python" "Learn Guitar"

With no topics given, a small default list of common goals is used.
"""

import asyncio
import os
import sys

sys.path.append(os.getcwd())

DEFAULT_TOPICS = [
    "Learn Python Programming",
    "Learn Web Development",
    "Learn Machine Learning",
    "Learn Data Science",
    "Learn Guitar",
]


async def prewarm(topics: list[str]) -> None:
    from src.roadmap_engine import generate_roadmap

    for topic in topics:
        print(f"Prewarming: {topic}")
        try:
            roadmap = await generate_roadmap(topic)
            print(f"  -> {len(roadmap.nodes)} nodes cached for '{topic}'")
        except Exception as e:
            print(f"  -> FAILED for '{topic}': {e}")


def main() -> None:
    topics = sys.argv[1:] or DEFAULT_TOPICS
    if not os.getenv("REDIS_URL"):
        print(
            "Warning: REDIS_URL is not set. Results will only populate this "
            "process's in-memory cache, which won't be visible to your "
            "running server. Set REDIS_URL to prewarm the shared cache."
        )
    asyncio.run(prewarm(topics))


if __name__ == "__main__":
    main()
