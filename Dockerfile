# Oracle Always Free (ARM) serving image — Arch B.
# Bakes the three fastembed ONNX weights into the image at BUILD time so
# cold starts never pay the Hugging Face download (~27s observed) and the
# box needs no HF network access at runtime.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FASTEMBED_CACHE_PATH=/app/.fastembed_cache

WORKDIR /app

# onnxruntime needs no system libs beyond what slim ships for CPU inference.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code only — data/, frontend/, tests/ stay out (see .dockerignore).
COPY src/ ./src/

# Bake retrieval weights: dense + sparse + reranker (names must match
# src/agents/resource_agent.py). Fails the build if a model can't download,
# so a bad weight rev never ships silently.
RUN python -c "from fastembed import TextEmbedding; TextEmbedding('BAAI/bge-small-en-v1.5')" \
 && python -c "from fastembed import SparseTextEmbedding; SparseTextEmbedding('Qdrant/bm42-all-minilm-l6-v2-attentions')" \
 && python -c "from fastembed.rerank.cross_encoder import TextCrossEncoder; TextCrossEncoder('Xenova/ms-marco-MiniLM-L-6-v2')"

EXPOSE 8000

# Single worker: each worker reloads all three models (~500-650MB RSS total),
# so --workers 1 is the memory-safe setting even on 12GB (leaves headroom
# for Qdrant sidecar + page cache). Async I/O gives real concurrency.
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
