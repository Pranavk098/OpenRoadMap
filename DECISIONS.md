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

### Track B — Eval Integrity

- **NDCG fix**: extracted `dcg_at_k`/`ndcg_at_k` into new `src/metrics.py` (pure, framework-free). Both `eval_agent.py::evaluate_resources` and `evaluate_retrieval.py` import from it; deleted the buggy `sklearn.metrics.ndcg_score` call (fed a synthetic "all 1s then 0s" array as `y_true` — not a real relevance judgment) and the duplicate hand-rolled copy.
- **Ground truth pollution**: cleaned `retrieval_ground_truth.json` **50 → 29 entries** (removed 21 `"Unknown Title"`). Root-caused in `ingest_coursera.py`/`ingest_edx.py`: added `resolve_title(row)` — tries known column variants, returns `None` on missing/NaN/empty; unmapped/duplicate rows are now **skipped with a logged warning**, never defaulted to a sentinel string. `generate_synthetic_ground_truth.py` also defensively filters degenerate/duplicate queries.
- **Generation metric**: added `bipartite_topic_alignment` (greedy nearest-unclaimed-match over `fastembed` cosine similarity, threshold `0.6`, documented) as the **primary** generation metric (coverage/precision) in `eval_agent.py`. ROUGE-L/BERTScore kept but relabeled `secondary/reference` with a one-line reason (order/length-sensitive metric applied to a set-coverage problem).
- **Real reranker**: `src/reranker.py` implements MMR (pure numpy), unit-tested to demonstrably prefer a diverse candidate over a near-duplicate. Wired into `evaluate_retrieval.py` as `variant="mmr"` vs `dense_baseline`. Retired the fictional "MultiFactor/CrossEncoder" labels — neither existed in code.
- **Honesty guard**: `evaluate_retrieval.py` now checks Qdrant connectivity up front and raises clearly instead of silently falling through to DDG web search (which would produce real-looking but meaningless recall numbers against a synthetic corpus).
- **`run_evaluation.py`**: writes `{generated_at, commit_sha, retrieval, generation, notes}` to `data/evaluation/results.json` + `frontend/public/eval-results.json`. **Actually executed** here: retrieval is `null` (Qdrant unreachable, confirmed live) and generation is `null` (no `OPENAI_API_KEY`, confirmed live) — genuine failures recorded verbatim, not fabricated numbers.
- **Dashboard**: `Evaluation.jsx` fetches `/eval-results.json`, shows `generated_at`/commit SHA, real numbers when present, and an honest "not yet run in this environment" empty state on 404. Zero hardcoded metric literals remain.
- **Realistic ground truth (addendum)**: title-as-query was near-trivial known-item search, inflating/deflating Recall unrepresentatively. Added a **second, separate** file `retrieval_ground_truth_realistic.json` — learner-phrased templates (`"how to learn X"`, `"beginner guide to X"`, etc.) over a marketing-noise-stripped title. Actually generated: **29 base items → 58 variants**, spot-checked, no raw-title echo. An LLM-phrased variant generator is also written but gated off by default and **unexecuted** (no API key). Both ground-truth sets now report separately (`known_item_search` vs `realistic_learner_phrased`) so the easy-vs-realistic gap is a visible finding, not hidden in one blended number.
- **Reranker/label honesty**: as of this track's snapshot, did not claim a "hybrid (RRF-fused)" variant since that didn't exist in the code this worktree saw — only labeled techniques real at the time (`dense_baseline`, `mmr_reranked`). Track A's hybrid+cross-encoder work (merged after this) supersedes this for the serving path. **Orchestrator follow-up needed**: re-run `run_evaluation.py` post-merge once Qdrant is available so `results.json` reflects the final hybrid pipeline as a third real variant, rather than backfilling it now.
- **Tests**: 27/27 passing (`test_metrics.py`, `test_reranker.py`, `test_ingestion_mapping.py`, `test_synthetic_ground_truth.py`) — NDCG hand-verified, MMR redundancy-reduction demonstrated (not asserted by construction), ingestion skip-on-missing-column covered, learner-query templating covered.
- **Verified once, live**: installed `rouge_score`/`bert_score` temporarily to smoke-test `evaluate_roadmap_structure` end-to-end — real numbers (`coverage=0.6, precision=1.0, rouge_l=0.571, bert_score=0.911`), not repeated routinely (bert_score pulls a ~1.4GB torch checkpoint).
- **Dependencies needed in `requirements.txt`** (not edited by this track): `fastembed` (verified installable/functional); `rouge_score`/`bert_score` were already missing — pre-existing gap, not introduced here.

---

### Track A — Backend Core

**Security**
- `slowapi` rate limiting (`RATE_LIMIT` env var, default `5/minute`) on `POST /generate-roadmap` and `GET /v1/roadmap/stream`, keyed by client IP.
- `goal` (POST body + SSE query param) capped at 200 chars, control characters rejected, via a shared validator.
- CORS: `ALLOWED_ORIGINS` env var (default `http://localhost:5173`), `allow_credentials` dropped entirely (no sessions exist to need it) — fixes the spec-invalid `["*"]` + credentials combo.
- `CorrelationIdMiddleware` + a generic exception handler: raw exception text logged server-side only, clients get `{"error": "...", "correlation_id": "..."}`. SSE `error` events follow the same contract.
- `resource_agent.py` validates every resource URL server-side (`http`/`https` only) — not relying on frontend JSX alone.

**Latency / async rewrite**
- `roadmap_engine.py` fully async; `AsyncOpenAI`/`AsyncQdrantClient` replace sync clients. `POST /generate-roadmap` and the new SSE endpoint share one pipeline (`stream_roadmap_events`) — no duplicated logic.
- Retrieval batched: one embedding pass for all node queries, one Qdrant round trip for the whole roadmap, web fallbacks via `asyncio.gather` each bounded by `asyncio.wait_for(timeout=2.5)`.
- Dropped the 3 hardcoded few-shots (~1,200+ wasted input tokens/call) for a strict structured-outputs JSON schema. Model configurable via `ROADMAP_MODEL` (default `gpt-4o-mini`).
- New `GET /v1/roadmap/stream?goal=...` SSE endpoint (exact contract below); `POST /generate-roadmap` stays byte-for-byte backward compatible.
- New `src/cache.py`: in-process LRU by default, Redis if `REDIS_URL` is set (permanently degrades to LRU on first Redis failure — never fails a request over a cache problem). Key = `sha256(normalized goal)`, TTL 30 days, checked before any LLM call. `scripts/prewarm_cache.py` added as a standalone, non-blocking prewarm job.
- New `src/dag_validator.py`: caps at 10 nodes, drops dangling/self prerequisite refs, breaks cycles. Does **not** fabricate nodes to hit a 4-node minimum — logs a warning instead (truthfulness over a count target).
- Fixed the always-appended `"..."` ellipsis bug (only appends when actually truncating).
- Swapped `duckduckgo-search` → `ddgs`; added Wikipedia REST summary as a second free fallback before the last-resort Google search link.
- `structlog` throughout, correlation-id-bound; per-stage timers (`llm_ms`, `resources_ms`, `total_ms`, `cache_hit`) as structured events.
- `vectorize_corpus.py`: `recreate_collection()` → build-new → upsert → atomic alias swap → delete old (no more index-destroying reindex).
- `requirements.txt` pinned; `torch`/`sentence-transformers`/`transformers`/`huggingface-hub` removed; `fastembed` added. Confirmed a clean venv install pulls no CUDA wheels.
- `docker-compose.yml`: optional `redis` service added.

**Retrieval architecture modernization** (the dense-only/MiniLM/cosine-threshold critique)
- **Hybrid dense+sparse**: dense `fastembed.TextEmbedding("BAAI/bge-base-en-v1.5")` (768d, chosen over bge-small/MiniLM for retrieval quality, still ONNX/CPU/no-torch — bge-small is a documented same-shape fallback if bge-base proves too heavy on a real free-tier CPU deploy); sparse `fastembed.SparseTextEmbedding("Qdrant/bm42-all-minilm-l6-v2-attentions")` for the named-entity/abbreviation case ("PyTorch", "Kubernetes", "CS50") dense-only misses. Uses fastembed's asymmetric `query_embed`/`passage_embed` correctly (not plain `embed`).
- **Qdrant hybrid query**: two named vectors per point; `Prefetch` dense top-50 + `Prefetch` sparse top-50 fused via `Fusion.RRF`, still one `query_batch_points` round trip for the whole roadmap.
- **Reranking replaces `score_threshold=0.4`**: fused top-50 reranked via `fastembed.rerank.cross_encoder.TextCrossEncoder("Xenova/ms-marco-MiniLM-L-6-v2")` (ONNX, torch-free); top 3-5 kept by reranker score. A defensive RRF-order fallback exists in code if the cross-encoder fails to load, but isn't the primary path.
- **Real retrieval queries**: added `search_query` (maxLength 80) to the planner's structured-output schema — zero extra LLM calls — replacing the human-facing `description` as the embedded text (falls back to `"{title}: {description}"` only for pre-migration cached roadmaps).
- **DAG-aware queries**: after validation, prepends one representative ancestor chain to each node's query (`"React Development > Fundamentals > Hooks & Effects: {search_query}"`) — cheap string concat, no extra calls.
- **Bounded one-retry agentic step** (resolves the "these aren't real agents" critique via behavior, not a rename): if a node's reranked results are too few or all score below the cross-encoder's own zero-logit relevance boundary, `ResourceAgent` reformulates once (drops the ancestor-path prefix, widens web search, reranks the merged set jointly) — hard-capped at one retry per node, logged.
- `vectorize_corpus.py` writes both named vectors via `passage_embed`, matching `query_embed` at retrieval time — full ingestion path is torch-free.
- **Not verified live**: no network access to Hugging Face Hub in this sandbox to actually download/run bge-base, bm42, or ms-marco end-to-end, or a live Qdrant hybrid query. All fastembed/qdrant-client APIs confirmed importable/constructible against pinned versions and covered by mocked tests — no real embedding or ranking was ever produced here. **User must smoke-test this against real Qdrant + HF downloads before shipping.**

**SSE event contract** (`GET /v1/roadmap/stream?goal=...`, `text/event-stream`; each event is `event: <name>\ndata: <json>\n\n`)
1. `structure` (once, before retrieval): `{"nodes": [{"id","title","description","prerequisites":[...]}, ...]}`
2. `resources` (once per node, order not guaranteed to match `structure`, correlate via `id`): `{"id", "resources": [{"id","title","url","description","type"}, ...]}`
3. `done` (terminal): `{"cache_hit": true|false}`
4. `error` (terminal, instead of `done`): `{"error": "generic message", "correlation_id": "uuid4"}`

A cache hit emits the identical event sequence, just faster.

**Verification**: fresh-venv install resolves clean (no torch/sentence-transformers/transformers); `from src.main import app` imports cleanly; **51 pytest tests pass**, all clients mocked (`tests/{conftest,test_dag_validator,test_cache,test_resource_agent,test_main,test_roadmap_engine}.py`, root `pytest.ini`).
**Not verified**: any live OpenAI/Qdrant/Redis/fastembed-model call.
**Flagged for the hygiene pass**: a bare `pytest` from repo root will still try to collect the pre-existing `tests/test_api.py`, `test_ddg.py`, `test_wide_scope.py` (real subprocess/network scripts, not unit tests) and hang/fail — pre-existing condition, needs addressing when tests/ is cleaned up. Also `scripts/ingestion/search_test.py`/`qdrant_verify.py` are pre-existing scratch debug scripts hardcoded to `localhost:6333`; `search_test.py` still imports `sentence_transformers`, now removed from `requirements.txt`, so it's currently broken. Not fixed here (out of scope, not on the deploy path, not collected by `pytest` since `pytest.ini` scopes to `testpaths = tests`) — candidate for the hygiene pass.

---

### Deploy prep (orchestrator, post-merge)

- **Security incident, caught before it shipped**: the user pasted a live `OPENAI_API_KEY` and a live Qdrant Cloud API key directly into `.env.example` — a file tracked by git and meant to ship in the public repo. Caught via `git diff` before committing; confirmed via `git log -- .env.example` it was never actually committed (safe, but was one `git add .`/`git commit -am` away from a public leak). Moved the real values into `.env` (gitignored, confirmed via `.gitignore`), reverted `.env.example` to placeholders. **User should still rotate both keys** as a precaution — they were pasted into a chat session regardless of what got committed.
- **`QDRANT_API_KEY` wiring**: neither `QdrantClient`/`AsyncQdrantClient` constructor (`src/dependencies.py`) nor `scripts/ingestion/vectorize_corpus.py`'s standalone client took an API key — worked fine against a local no-auth Qdrant but would silently fail to authenticate against Qdrant Cloud. Added `QDRANT_API_KEY` env var (empty/unset → `None`, correct for local Docker Qdrant), threaded through both. Verified: loads from `.env`, client constructs, and the full test suite (78 tests: 66 core + 12 resource-agent) still passes.
- **Deploy config added**: `Procfile` (`uvicorn src.main:app --workers 2`, generic Railway/Heroku-style buildpack target) and `render.yaml` (Render blueprint, free-tier web service, `/health` healthcheck, all secrets marked `sync: false` so Render prompts for them in its dashboard rather than reading committed values).
- **Not done here**: pushing anything to the remote, or merging to `main` on origin — only local git state changed. Pushing affects a shared/public repo and needs an explicit go-ahead separate from "do the local prep."
- **Pushed to origin, with user go-ahead**: `main` (`db4cf8d..a61d5ce`) and `feature/gtm-overhaul`. Blocked once on a stale cached GitHub credential (`gh` CLI had two logged-in accounts, wrong one active) — fixed via `gh auth switch`, not by touching passwords/tokens directly.
- **First-ever live run against real services**, now that the user supplied real `OPENAI_API_KEY` + Qdrant Cloud credentials — upgrades several "not verified live" caveats above:
  - `RoadmapAgent.generate_structure`: real gpt-4o-mini call, structured-outputs schema validated against the live API (not just shape-checked), `search_query` field populated correctly per node.
  - `fastembed` model downloads: `BAAI/bge-base-en-v1.5` (dense), `Qdrant/bm42-all-minilm-l6-v2-attentions` (sparse), and the `ms-marco` cross-encoder reranker all downloaded and ran for real, first time ever exercised outside mocks.
  - Qdrant hybrid query: confirmed graceful handling of a nonexistent collection (404 → falls through to web fallback, no crash) before ingestion, then real hybrid dense+sparse+RRF retrieval after.
  - **Seeded the live Qdrant Cloud collection**: ran `ingest_manual.py` → `process_corpus.py` → `vectorize_corpus.py` against production `QDRANT_URL` — 15 items from `data/manual/curated_resources.json`, alias-swap indexing confirmed (`educational_resources` → `educational_resources_1787558025`), `count=15` verified post-ingest.
  - **Agentic retry loop confirmed working on real data, not just mocks**: for "Python basics for a beginner," all 9 nodes retrieved 15 real hybrid candidates each, the reranker correctly judged most too generic for the specific sub-topic (small 15-item general corpus vs. narrow queries), the one-retry reformulation fired and merged in live web results — and for one node ("Working with Collections") a real manual-corpus item (Real Python) won the joint rerank over the web results. This is the exact "inspects its own results and acts" behavior the retry was built for, observed live.
  - End-to-end latency: 27.4s cold (first-ever fastembed model download included), 12.5s warm (models cached) for a 9-node roadmap — consistent with the audit's async/parallel-retrieval target range.
- **First real deploy attempt surfaced the bge-base tradeoff Track A had flagged as unverified.** Render free tier (512MB) OOM'd loading `bge-base-en-v1.5` (768d) — with `--workers 2` it loads twice, making it worse. Switched to the documented fallback: `BAAI/bge-small-en-v1.5` (384d) in both `resource_agent.py` and `vectorize_corpus.py`, and dropped to `--workers 1` in `Procfile`/`render.yaml` (memory, not CPU, is the binding constraint here — async I/O already gives real concurrency within one worker). Re-vectorized the live Qdrant collection to match via the alias-swap path (confirmed: old 768d collection deleted, new 384d collection live under the same alias, zero downtime).
- **Two real bugs found by actually running the eval harness live for the first time — exactly what this kind of testing is for:**
  1. `scripts/evaluation/evaluate_retrieval.py` called `ResourceAgent.find_resources()` (the sync convenience wrapper) once per query in a loop. That wrapper does its own `asyncio.run()` per call; reusing the same `ResourceAgent`'s async Qdrant/HTTP clients across many separate event loops broke the connection pool partway through the first live run (`Event loop is closed`, some queries silently fell back to web search instead of real hybrid retrieval — which would have quietly corrupted the recall/NDCG numbers). Fixed: `evaluate_retrieval()` is now `async`, calls `find_resources_async` directly, and `run_evaluation.py` runs the entire retrieval + generation eval under one `asyncio.run()` so there's exactly one event loop and one shared `ResourceAgent` for the whole run (also saves reloading the fastembed models 4x).
  2. `run_evaluation.py`'s generation eval globbed `data/manual/*.json` expecting every file to be a `{"skill": ..., "roadmap": [...]}` document, but `curated_resources.json` (the resource corpus, ingested earlier in this same session) lives in that directory too and is a flat list — `ground_truth.get("skill")` on a list raised an uncaught `AttributeError` that crashed the whole script, discarding the real retrieval results already computed earlier in the same run. Fixed: skip non-dict ground-truth files with a note instead of crashing; also wrapped both eval phases in top-level try/except so a failure in one phase can no longer erase results from the other — `results.json` now always gets written.
  - Both bugs were latent since Track A/B were built in parallel worktrees off the same base commit — Track A changed `generate_structure`/`find_resources` to async after Track B had already written code against the original sync signatures. Disjoint-file parallelism didn't catch it because nothing failed at import time; it only surfaced under a real, live, multi-query run. Fixed post-merge, re-verified with the full test suite (78/78 still pass) before re-running live.
- **User reported the deployed app's resource suggestions as generic/weak ("Search Google for X" links, an unrelated Wikipedia article) and slow (~14s).** Root-caused live: `WEB_SEARCH_TIMEOUT_SECONDS = 2.5` wrapped up to 3 sequential real network calls in `_web_fallback_inner` (primary DDG search, a broadened DDG retry if empty, then Wikipedia) — a single raw `ddgs` call alone measured ~2.2s, so the whole chain blew the 2.5s budget almost every time and fell straight to the weak last-resort fallbacks. Fixed: raised to `6.0s` (bounded per-node, not additive across nodes since fallbacks already run via `asyncio.gather`), and while in there, added a YouTube-restricted query running *concurrently* (not sequentially) with the general search so video results actually surface — any web-fallback URL from a YouTube host is now tagged `type="Video"` instead of generic `"Web Resource"`. Verified live: "Machine Learning Algorithms" now returns a real YouTube playlist + two real Coursera courses in 2.87s, vs. Wikipedia/Google-link fallback before.

---

### Orchestrator — merge + dependency reconciliation

All three tracks merged cleanly with zero file conflicts (disjoint ownership held). Post-merge reconciliation:

- Added `numpy` to `requirements.txt` (serving) — `src/metrics.py` (imported eagerly by `eval_agent.py`, imported eagerly by `roadmap_engine.py` at module load) uses it directly; it's a real runtime dependency of the live app, not just eval tooling, even though it arrived via Track B's file.
- Confirmed `src/reranker.py` (Track B's MMR) is **not** imported anywhere in the serving path — only by `scripts/evaluation/evaluate_retrieval.py`. Track A's live reranking uses fastembed's own `TextCrossEncoder` directly, unrelated to Track B's MMR. No conflict, no shared dependency needed.
- Split dependencies properly: new `requirements-dev.txt` (`-r requirements.txt` plus `pytest`/`pytest-asyncio`, `rouge-score`/`bert-score`, `pandas`/`beautifulsoup4`/`feedparser`/`google-api-python-client`/`requests` for ingestion scripts). **Verified in isolation**: `pip install -r requirements.txt` alone resolves with zero torch/transformers/CUDA packages — the L7 fix holds for what actually ships in the API container. `bert-score` (dev-only) does transitively pull torch, but that's fine since it never reaches the serving image.
- **Full integration test**: fresh venv, `pip install -r requirements.txt -r requirements-dev.txt`, ran all 78 tests from both tracks together (`tests/` minus the three pre-existing live-network scripts) — **78/78 pass**, no cross-track import or fixture collisions. `from src.main import app` imports cleanly end-to-end.
- Frontend (Track C) independently verified: `npm run build` + `npm run lint` clean, code-splitting confirmed via build output (separate `reactflow`/`recharts`/`Roadmap`/`Evaluation` chunks).

---

### Track D — Hygiene / CI (orchestrator, sequential after merge)

- **CI**: `.github/workflows/ci.yml` — backend job runs `ruff check` + `pytest` (mocked, dummy `OPENAI_API_KEY`, no live services needed); frontend job runs `npm run lint` + `npm run build`. Both jobs verified locally before committing the workflow, not just written and hoped for.
- **`ruff.toml`**: scoped to `E9` (syntax errors), `F` (pyflakes — unused imports/vars, undefined names), `I` (import sorting) — deliberately not the full pyupgrade/blind-except/etc. rule set, which would flag hundreds of pre-existing working lines with no real bug behind them. Ran `ruff --fix` (mechanical import-sorting/unused-import fixes across 16 files) and manually removed one genuinely-dead variable (`institution` in `ingest_edx.py`, pre-existing, unrelated to any track's changes) that the new gate surfaced.
- **`pytest.ini`**: added `testpaths = tests` — Track A had flagged that a bare `pytest` from repo root would try to collect the pre-existing live-network manual scripts and hang; scoping discovery to `tests/` fixes it directly instead of renaming files to dodge collection.
- **Test cleanup**: deleted `tests/test_wide_scope.py` (imported `backend.app.main:app`, a path that never existed in this repo — dead, never passed) and `tests/test_ddg.py` (imported `duckduckgo_search` directly, which Track A removed in favor of `ddgs` — now flatly broken). Moved the three remaining manual/live scripts (`test_api.py`, `repro_issue.py`, `verify_resources.py` — real subprocess/network calls, no assertions, not actual pytest tests) to `scripts/manual_smoke/` with a one-line header noting they need live Qdrant/OpenAI and aren't part of CI. `tests/` is now exclusively the mocked automated suite (78 tests, Tracks A+B combined).
- **Dead file removal**: `frontend/src/layout/Sidebar.jsx` (confirmed via grep — `App.jsx` only imports `Navbar`; the one remaining "Sidebar" string in the codebase is an unrelated JSX comment in `Roadmap.jsx` labeling the resource panel). Root `package.json`/`package-lock.json` (stray accidental-`npm install`-at-repo-root artifacts — no scripts, dependency list unrelated to the actual `frontend/` app, two lockfiles was a standing footgun).
- **`LICENSE`** (MIT, matching the claim the README already made) and **`.env.example`** (enumerated by grepping every `os.getenv`/`os.environ.get` call across `src/` rather than guessing — `OPENAI_API_KEY`, `QDRANT_URL`, `QDRANT_COLLECTION`, `ALLOWED_ORIGINS`, `RATE_LIMIT`, `ROADMAP_MODEL`, `REDIS_URL`).
- **`README.md`** rewritten: accurate architecture diagram (hybrid retrieval, reranking, one honest agentic retry — matches what's actually in `src/`, not what was there before), explicit "why these aren't called agents / why this isn't 2023's retrieval stack" section addressing the naming-honesty critique directly, real setup steps reflecting the two-file requirements split and optional Redis, a `Known gaps` section (favicon/OG image still placeholders, eval numbers are environment-dependent — flagging rather than hiding), removed the placeholder-screenshot `<img>` that 404s and the LICENSE-doesn't-exist mismatch.

### Requirements split, finalized

- `requirements.txt` — serving/runtime only. **Verified in an isolated fresh venv**: zero torch/transformers/CUDA packages resolve.
- `requirements-dev.txt` — `-r requirements.txt` plus test/eval/ingestion-only deps (`pytest`, `pytest-asyncio`, `rouge-score`, `bert-score`, `pandas`, `beautifulsoup4`, `feedparser`, `google-api-python-client`, `requests`). `bert-score` does pull `torch` transitively, but only into this dev file, never the serving image.

### Deliberately skipped

- **`mypy`**: the audit's CI suggestion (§8, phase 4) included it. The codebase has no type annotations anywhere; running mypy as-is would either need a permissive config that catches nothing meaningful, or an out-of-scope annotation-writing pass across the whole codebase to be worth anything. Skipped rather than adding a CI step that's decorative. `ruff`'s `F` rules (undefined names, unused imports/vars) catch the cheap subset of what mypy would catch here.
- **Secret scanning** (audit S6): not added. Worth doing (e.g. a `gitleaks` CI step) but lower priority than everything else in this pass — flagging as a real gap, not silently dropping it.
- **Renaming the `RoadmapAgent`/`ResourceAgent`/`EvaluationAgent` classes**: the user's own framing offered two equally-valid fixes for the "these aren't real agents" critique — rename to honest names, or make one genuinely agentic. Went with the latter (Track A's bounded retrieval retry) since it's a real capability, not just different words for the same fixed pipeline; the README's "honest naming notes" section explains this choice explicitly rather than leaving it unstated.

### Final state

- **78/78 backend unit tests pass** (fresh venv, mocked clients, no live services) — confirmed again after the ruff `--fix` pass and `testpaths` change.
- **Frontend build + lint clean**, confirmed again after `Sidebar.jsx`/root-`package.json` deletion.
- `from src.main import app` imports cleanly end-to-end with the fully merged tree.
- **What was never executed against live services in this sandbox, and needs a real smoke test before shipping**: any real OpenAI call (structured-outputs schema was validated for shape, not run against the live API), any real Qdrant hybrid query (RRF fusion, the three fastembed model downloads — bge-base-en-v1.5, bm42 sparse, ms-marco reranker — were confirmed importable/constructible, never run against real weights), any real Redis connection, and the live evaluation run (`results.json`'s retrieval/generation fields are currently `null` with honest notes, not fabricated numbers).

---
