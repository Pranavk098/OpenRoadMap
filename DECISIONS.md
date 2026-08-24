# OpenRoadMap — GTM Overhaul: Decision Log

Terse log of what changed, why, and tradeoffs. One entry per decision, newest at bottom of each section.

## Environment constraints (read this first)

- No `.env` / `OPENAI_API_KEY` in this workspace → live gpt-4o/mini calls were **not** executed here. All LLM-path code is unit-tested with mocked OpenAI responses, not run against the real API. User must smoke-test with a real key before shipping.
- Docker available, no Qdrant/Redis running by default → retrieval-path integration tests use mocked Qdrant client. `docker-compose up` still required for real retrieval.
- Network access confirmed (pypi/npm reachable) → dependency installs for verification are possible.

## Orchestration plan

Work split into 4 isolated git worktrees, merged sequentially into `feature/gtm-overhaul`, to avoid file-conflict churn between parallel agents:

| Track | Scope | Files |
|---|---|---|
| A — Backend core | Latency, security, caching, streaming | `src/`, `requirements.txt`, `docker-compose.yml` |
| B — Eval integrity | Ground truth, metrics, reranker, dashboard data | `src/agents/eval_agent.py`, `scripts/evaluation/`, `scripts/ingestion/ingest_*`, `data/evaluation/`, `frontend/src/pages/Evaluation.jsx` |
| C — Frontend product | Routing, SEO, perf, error handling | `frontend/src/pages/Roadmap.jsx`, `Landing.jsx`, `App.jsx`, `index.html`, `api/client.js`, `vite.config.js` |
| D — Hygiene/CI | Runs after A+B+C merge (needs final state) | CI, tests, LICENSE, `.env.example`, README, root package.json cleanup |

Rationale: A/B/C touch disjoint file sets (backend engine vs. eval scripts vs. frontend UI), so they're safe to parallelize. D depends on the merged result (accurate README/CI needs final file layout), so it runs last, sequentially.

## Interruption + scope expansion (mid-run)

All three tracks hit the session usage cap mid-task and stopped (uncommitted, in their own worktree branches — nothing lost). Resumed each from where it left off.

At the same point, user supplied a RAG-architecture critique: the retrieval stack (dense-only MiniLM, raw cosine, fixed 0.4 threshold, description-as-query, DAG thrown away after planning, "Agent" classes with no actual agency) is the most dated part of the project. Folded into the in-flight tracks rather than spun up as new parallel tracks, since the changes land in files A and B already own:

- **Track A** (owns `resource_agent.py`, `roadmap_agent.py`, `roadmap_engine.py`, `vectorize_corpus.py`) absorbs: stronger dense embedding, hybrid dense+sparse retrieval via Qdrant native fusion, a `search_query` schema field (replaces description-as-query), DAG-ancestor-path query contextualization, reranking wired into the serving path (replacing the hardcoded 0.4 threshold), and a bounded agentic retry/reformulate loop in `ResourceAgent` — which resolves the "agent" naming honesty issue by making it *actually* agentic instead of just renaming classes.
- **Track B** (owns eval scripts/metrics) absorbs: replacing title-as-query ground truth (near-trivial known-item search) with learner-phrased queries, and evaluating retrieval through the new hybrid+rerank stages instead of the old fictional "MultiFactor/CrossEncoder" labels.
- **Track C** (frontend) — no RAG-related scope change; just finishing its original verification.

---
