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

### Track C — Frontend Product

- **C1 (infinite recursion on cycles):** `getLevel` in `Roadmap.jsx` now tracks a `visiting` Set; re-entering a node already in `visiting` returns level `0` instead of recursing. Verified with a standalone script replicating the algorithm against a 2-node and 3-node prerequisite cycle — terminates, produces sane levels, no stack overflow.
- **C2 (dangling prerequisite edges):** edge creation now checks `nodeMap.has(prereqId) && nodeMap.has(node.id)` before pushing an edge, so a `prerequisites` entry referencing a nonexistent node id is silently dropped instead of handed to ReactFlow.
- **C3 (URL-addressable roadmaps, no fake fallback):** added `/roadmap/:slug` route. `Landing.jsx` slugifies the topic, stashes the roadmap response in `sessionStorage` under `roadmap:${slug}`, and navigates there (router `state` kept only as a fast path, not the source of truth). `Roadmap.jsx` on mount tries `location.state` → `sessionStorage` → regenerates via the API using a de-slugified topic guess; a failed regeneration shows a real error state (retry + go home), never mock data. Deleted `mockRoadmapData` entirely — it was a silent-failure fallback, not a real demo. Old bare `/roadmap` route now redirects to `/` instead of ever serving fake data. Removed the now-meaningless "Roadmap Demo" nav item in `Navbar.jsx`.
- **L9 (full re-layout on every progress tick):** split the layout `useEffect` (nodes/edges from `roadmapData` only, no `progressMap` in deps) from progress rendering, which is now merged into a `displayNodes` `useMemo` keyed on `[nodes, progressMap]`. Dragging the progress slider no longer re-runs the level-assignment DFS or rebuilds the graph.
- **Error handling:** added `ErrorBoundary` (new `components/ErrorBoundary.jsx`) wrapping routed content in `App.jsx`. Replaced both `alert()` calls in `Landing.jsx` with inline error UI + retry button, distinguishing network-down vs. timeout/cold-backend vs. server-error via a new `RoadmapApiError`/`describeApiError` in `api/client.js` (added a 30s `AbortController` timeout to `generateRoadmap` so a hung request can be classified as "waking up the server" rather than hanging forever). Same treatment applied to the API-retry path in `Roadmap.jsx`.
- **SEO:** `index.html` — real `<title>`, meta description, OG tags, Twitter card tags. `document.title` set per-route via `useEffect` in `Landing.jsx` and `Roadmap.jsx` (not done in `Evaluation.jsx` — owned by Track B).
- **Code splitting:** `Evaluation` and `Roadmap` routes are now `React.lazy` + `Suspense` in `App.jsx` so the landing bundle doesn't ship ReactFlow or Recharts. `vite.config.js` adds `manualChunks` splitting `reactflow` and `recharts` into their own chunks. Confirmed via `npm run build`: separate chunks, landing page loads neither.
- **New:** "Copy link" button on the Roadmap header (clipboard + "Copied!" confirmation); aggregate roadmap-completion progress bar in the header (average of all nodes' progress); new `NotFound.jsx` page for unmatched routes.
- **Verified:** `npm run build` and `npm run lint` both pass clean. Live-driven in-browser: no-backend failure shows inline error + retry (no `alert()`); `/roadmap/machine-learning` with no cached state correctly attempts regeneration and shows a real error state on failure; bare `/roadmap` redirects to `/`; `NotFound` renders for a bogus path.
- **Asset gaps — need real files from the user:**
  - Favicon: `index.html` now references `/favicon.svg` but no such file exists in `frontend/public/` (only the default `vite.svg`).
  - OG image: `index.html`'s `og:image`/`twitter:image` point at `/og-image.png`, a placeholder path — no real social-preview image exists yet.

---
