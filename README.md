# OpenRoadMap

AI-generated learning roadmaps for *any* skill — not just software roles. Give it a goal ("Machine Learning," "Sourdough Bread Baking," "Screenwriting") and it returns a dependency-ordered curriculum with real, retrieved learning resources attached to each step.

roadmap.sh gives you hand-curated paths for software roles. OpenRoadMap generates a path plus retrieved resources for any skill — the tradeoff is breadth and freshness for hand-curation. The `data/manual/` set (astrophysics, screenwriting, urban gardening, sourdough, alongside the usual dev topics) is the actual differentiator, and the [evaluation dashboard](#evaluation) exists so that claim is checkable rather than asserted.

## How it works

```
goal
  │
  ▼
Planner (gpt-4o-mini, schema-constrained)
  → emits nodes: {id, title, description, prerequisites, search_query}
  │
  ▼
DAG validation (cycles broken, dangling refs dropped, node cap enforced)
  │
  ▼
Retriever, per node, in parallel — not a loop over one node at a time:
  1. ancestor-path-aware query  ("Goal > Parent > Node: search_query")
  2. hybrid search — dense (fastembed bge-base) + sparse (fastembed bm42),
     fused with Qdrant's native RRF — top 50 candidates
  3. cross-encoder rerank → top 3-5
  4. weak/short results? → one bounded retry: reformulate + widen web
     fallback (ddgs → Wikipedia → last-resort search link), rerank jointly
  │
  ▼
stream to client (SSE: structure → resources per node → done)
  │
  ▼
cache the finished roadmap (30d TTL, keyed on normalized goal)
```

Two honest naming notes, since this gets asked in interviews:

- **"Planner" and "Retriever," not "agents."** The previous version called these `RoadmapAgent`/`ResourceAgent`/`EvaluationAgent` — three classes with methods called in a fixed sequence, no actual agency. The retriever now genuinely is one: it inspects its own result quality and reformulates on a weak match (bounded to one retry, logged) rather than returning junk. The planner and evaluator are still exactly what they sound like — a schema-constrained LLM call and a metrics computation — described as such rather than inflated.
- **The retrieval stack is 2026-shaped, not 2023-shaped.** Dense-only bi-encoder + raw cosine + a hardcoded similarity threshold was the reference architecture a few years ago. This one is hybrid dense+sparse retrieval, RRF-fused, reranked — see [`DECISIONS.md`](DECISIONS.md) for the specific models and why.

## Tech stack

**Backend** — FastAPI (async throughout), Qdrant (hybrid vector search), `fastembed` (ONNX embeddings + reranking — deliberately no `torch`/`sentence-transformers` in the serving container, see below), OpenAI (`gpt-4o-mini` by default, schema-constrained structured outputs), `structlog`, `slowapi` (rate limiting), Redis-optional caching.

**Frontend** — React 19, Vite 7, Tailwind, React Flow (roadmap graph), Recharts (evaluation dashboard), React Router (URL-addressable `/roadmap/:slug` routes).

## Getting started

### Prerequisites
Node 18+, Python 3.11+, Docker, an OpenAI API key.

### 1. Clone and configure
```bash
git clone https://github.com/Pranavk098/OpenRoadMap.git
cd OpenRoadMap
cp .env.example .env   # fill in OPENAI_API_KEY at minimum
```

### 2. Start Qdrant (and optionally Redis)
```bash
docker-compose up -d
```

### 3. Backend
```bash
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt          # serving deps only — no torch
pip install -r requirements-dev.txt      # + testing / eval / ingestion tooling
uvicorn src.main:app --reload
```
- `POST /generate-roadmap` — full roadmap in one response (backward-compatible shape).
- `GET /v1/roadmap/stream?goal=...` — SSE: `structure` event as soon as the DAG is ready, then one `resources` event per node as retrieval finishes, then `done`. See `DECISIONS.md` for the exact payload contract.
- `GET /health` — reports whether the retrieval models actually finished loading, not just that the process is up.

### 4. Ingest a corpus (optional but recommended)
```bash
python scripts/ingestion/process_corpus.py
python scripts/ingestion/vectorize_corpus.py   # zero-downtime alias swap, not a destructive reindex
```

### 5. Frontend
```bash
cd frontend
npm install
npm run dev   # http://localhost:5173
```

## Testing

```bash
pytest                 # mocked unit tests only — no live OpenAI/Qdrant/Redis needed
cd frontend && npm run lint && npm run build
```

Live, network-hitting smoke scripts (real Qdrant + real OpenAI required) live in `scripts/manual_smoke/` and are intentionally excluded from `pytest`/CI.

## Evaluation

`scripts/evaluation/run_evaluation.py` writes real, timestamped results (retrieval Recall@k/NDCG@k on both a known-item and a realistic learner-phrased query set; generation quality via bipartite topic-coverage alignment) to `data/evaluation/results.json`, which the `/evaluation` page fetches and renders directly — no hardcoded numbers. If it hasn't been run against live services in a given environment, the dashboard says so explicitly rather than showing a plausible-looking placeholder.

## Configuration

See [`.env.example`](.env.example) for every environment variable the app reads (rate limits, CORS origins, model choice, optional Redis). Full rationale for every architectural decision — including what was verified live vs. what's code-complete but untested in a given environment — is in [`DECISIONS.md`](DECISIONS.md).

## Known gaps

- No real favicon or social-preview (OG) image yet — placeholders are wired up in `index.html`/`frontend/public/`, waiting on real brand assets.
- The retrieval/generation numbers in `data/evaluation/results.json` reflect whatever environment last ran the eval script — check the `generated_at` timestamp before citing them.

## Contributing

1. Fork the project
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes
4. Push to the branch and open a Pull Request

## License

MIT — see [LICENSE](LICENSE).

---
*Built by Pranav Koduru*
