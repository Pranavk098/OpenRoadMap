import asyncio
import urllib.parse

import httpx
import structlog
from ddgs import DDGS

from ..dependencies import COLLECTION_NAME, get_async_qdrant_client
from ..models import Resource

logger = structlog.get_logger(__name__)

# Hybrid retrieval: a dense (semantic) model + a sparse (lexical) model,
# fused with Qdrant's native RRF, then reranked with a cross-encoder.
# All three are ONNX-runtime models via fastembed - no torch, CPU-friendly.
#
# bge-small-en-v1.5 (384d) - the larger bge-base-en-v1.5 (768d) gave better
# retrieval quality but OOM'd Render's free tier (512MB) once loaded twice
# under 2 workers; see DECISIONS.md. Still a CPU-only ONNX model, no CUDA.
DENSE_MODEL_NAME = "BAAI/bge-small-en-v1.5"
# Sparse lexical signal: catches exact named-entity/keyword matches
# ("PyTorch", "Kubernetes", "CS50") that a dense-only embedding can miss.
SPARSE_MODEL_NAME = "Qdrant/bm42-all-minilm-l6-v2-attentions"
# Cross-encoder reranker, also via fastembed (torch-free). Replaces the old
# uncalibrated score_threshold=0.4 cutoff with an actual relevance judgment
# over the fused candidate pool.
RERANKER_MODEL_NAME = "Xenova/ms-marco-MiniLM-L-6-v2"

DENSE_VECTOR_NAME = "dense"
SPARSE_VECTOR_NAME = "sparse"

# How many fused hybrid candidates to pull per node before reranking down
# to the caller's requested `limit` (typically 3-5). Lowered from 50: the
# cross-encoder rerank pass runs per-node on this many candidates, and at
# 50 it was a measurable chunk of resources_ms even before any web
# fallback (confirmed live via roadmap.timings) - with a 278-item corpus,
# scoring 50 candidates per query for a 3-slot result is well past
# diminishing returns; RRF's top ~20 fused candidates are already the
# corpus's best guesses for that query.
CANDIDATE_POOL_SIZE = 20

# ms-marco cross-encoders are trained so a raw (unnormalized) logit score
# above 0 indicates the query/document pair is plausibly relevant, and
# below 0 indicates it probably isn't - there's no fixed "0.4"-style
# probability cutoff to calibrate here, so 0.0 (the model's own decision
# boundary) would be the "no calibration" choice. Loosened to -0.5 (still
# requires the cross-encoder to judge a candidate as plausibly on-topic,
# just not strictly past its exact zero boundary): the 278-item corpus is
# course/doc-level (broad resources, not lesson-granular), so a genuinely
# relevant broad resource for a narrow node sometimes scores just under
# zero rather than comfortably above it. At 0.0 that pushed nodes to web
# fallback - the single biggest latency cost - even when a decent corpus
# match already existed. Not loosened further than this: still a real
# relevance judgment, not "return whatever's least bad."
WEAK_SCORE_THRESHOLD = -0.5

# Caps concurrent DDG calls across a single roadmap's node batch. Firing one
# request per weak node simultaneously (tried first) reliably triggers DDG's
# own rate limiting once more than a couple of nodes need it, which then
# starves every node's web search, not just the burst's. Raised 3->4->5
# alongside the shorter DDG_CALL_TIMEOUT_SECONDS/lower breaker threshold
# below: when DDG is unhealthy, more concurrency means the first (losing)
# wave finishes - and trips the breaker for everyone after it - faster.
WEB_SEARCH_MAX_CONCURRENCY = 5

# Hard ceiling on the whole web-fallback stage (all short nodes, every
# wave), separate from and larger than any single call's timeout below -
# bounds the worst case (many short nodes, degraded DDG) to a known tax
# instead of it scaling with how many nodes need fallback. Sized to fit
# one DDG wave at DDG_CALL_TIMEOUT_SECONDS plus a Wikipedia-only wave or
# two for whatever the circuit breaker has already given up on.
WEB_FALLBACK_STAGE_DEADLINE_SECONDS = 4.0

# Bounds DDG+Wikipedia together for one node. Lowered from 6.0 now that
# WEB_FALLBACK_STAGE_DEADLINE_SECONDS bounds the whole batch anyway - this
# just needs to fit one DDG_CALL_TIMEOUT_SECONDS attempt plus a Wikipedia
# call afterward.
WEB_SEARCH_TIMEOUT_SECONDS = 4.0
# DDG gets its own, shorter timeout, separate from WEB_SEARCH_TIMEOUT_SECONDS
# (which bounds DDG+Wikipedia together). Without this, a DDG call that just
# hangs (observed live: worse than a fast "no results" failure) burns the
# *entire* outer budget - the outer asyncio.wait_for then cancels the whole
# search before Wikipedia ever runs, AND before the circuit breaker's
# failure counter can even be incremented (the cancellation happens before
# that line executes), so the breaker never trips either. A dedicated,
# shorter DDG timeout fails fast, feeds the breaker, and leaves headroom
# for Wikipedia within the outer budget. Set to 2.5s, just above a healthy
# isolated ddgs call's observed ~2.4s (a lower value like 2.0s was timing
# out even healthy calls, never giving DDG a chance to actually succeed) -
# the circuit breaker, not this per-call timeout, is what bounds the cost
# of DDG being unhealthy.
DDG_CALL_TIMEOUT_SECONDS = 2.5
WIKIPEDIA_TIMEOUT_SECONDS = 1.5
ALLOWED_URL_SCHEMES = {"http", "https"}
DESCRIPTION_MAX_LENGTH = 200

# DDG rate-limits under bursty concurrent load (observed live: a roadmap
# with several nodes needing web fallback triggers a run of consecutive
# "No results found" failures from ddgs, each still costing real wall-clock
# time before failing). Once a batch sees this many consecutive DDG
# failures, remaining nodes in the same batch skip straight to Wikipedia
# instead of also paying for a DDG call that's overwhelmingly likely to
# fail the same way - a real, observed-live resilience fix, not a
# speculative one.
DDG_CIRCUIT_BREAKER_THRESHOLD = 2


class _DdgCircuitBreaker:
    """Shared per-batch (per find_resources_batch call) failure counter -
    see DDG_CIRCUIT_BREAKER_THRESHOLD."""

    def __init__(self, threshold: int = DDG_CIRCUIT_BREAKER_THRESHOLD):
        self._threshold = threshold
        self._consecutive_failures = 0
        self.tripped = False

    def record(self, succeeded: bool) -> None:
        if succeeded:
            self._consecutive_failures = 0
            return
        self._consecutive_failures += 1
        if self._consecutive_failures >= self._threshold:
            self.tripped = True


def _safe_url(url: str) -> str | None:
    """Only allow http/https URLs. Drops javascript:, data:, and anything
    else that shouldn't end up clickable in a client."""
    if not url:
        return None
    try:
        parsed = urllib.parse.urlparse(url)
    except ValueError:
        return None
    if parsed.scheme.lower() not in ALLOWED_URL_SCHEMES or not parsed.netloc:
        return None
    return url


def _truncate(text: str, length: int = DESCRIPTION_MAX_LENGTH) -> str:
    text = text or ""
    if len(text) <= length:
        return text
    return text[:length] + "..."


_VIDEO_HOSTS = {"youtube.com", "www.youtube.com", "youtu.be", "m.youtube.com"}


def _resource_type_for_url(url: str) -> str:
    """Web fallback results are otherwise all lumped under "Web Resource" -
    tag video-hosting URLs distinctly so the UI can render/label them as
    videos instead of generic links."""
    try:
        host = urllib.parse.urlparse(url).netloc.lower()
    except ValueError:
        return "Web Resource"
    return "Video" if host in _VIDEO_HOSTS else "Web Resource"


def _reformulate_query(query: str) -> str:
    """Cheapest reformulation available without an extra LLM call: drop the
    ancestor-path prefix roadmap_engine prepends (e.g.
    "React Development > Fundamentals > Hooks & Effects: useState tutorial"
    becomes "Hooks & Effects: useState tutorial"), so a retry searches on
    the node's own terms instead of context that may be diluting the match.
    """
    if " > " in query:
        return query.rsplit(" > ", 1)[-1]
    return query


class ResourceAgent:
    # Set once at FastAPI startup (see src/main.py lifespan) so models are
    # loaded a single time for the whole process instead of lazily per
    # request. Each falls back to lazy-loading itself (e.g. for standalone
    # scripts that construct a ResourceAgent outside the app's lifespan).
    _shared_dense_model = None
    _shared_sparse_model = None
    _shared_reranker = None

    def __init__(
        self,
        dense_model=None,
        sparse_model=None,
        reranker=None,
        qdrant_client=None,
        ddgs_client=None,
    ):
        self._dense_model = dense_model
        self._sparse_model = sparse_model
        self._reranker = reranker
        self._qdrant_client = qdrant_client
        self._ddgs = ddgs_client

    @property
    def dense_model(self):
        model = self._dense_model or ResourceAgent._shared_dense_model
        if model is None:
            from fastembed import TextEmbedding

            model = TextEmbedding(DENSE_MODEL_NAME)
            ResourceAgent._shared_dense_model = model
        return model

    @property
    def sparse_model(self):
        model = self._sparse_model or ResourceAgent._shared_sparse_model
        if model is None:
            from fastembed import SparseTextEmbedding

            model = SparseTextEmbedding(SPARSE_MODEL_NAME)
            ResourceAgent._shared_sparse_model = model
        return model

    @property
    def reranker(self):
        model = self._reranker or ResourceAgent._shared_reranker
        if model is None:
            from fastembed.rerank.cross_encoder import TextCrossEncoder

            model = TextCrossEncoder(RERANKER_MODEL_NAME)
            ResourceAgent._shared_reranker = model
        return model

    @property
    def qdrant_client(self):
        if self._qdrant_client is None:
            self._qdrant_client = get_async_qdrant_client()
        return self._qdrant_client

    @property
    def ddgs(self):
        if self._ddgs is None:
            self._ddgs = DDGS()
        return self._ddgs

    async def find_resources_batch(self, queries: list[str], limit: int = 3) -> list[list[Resource]]:
        """
        Hybrid batch pipeline. The core invariant - and the fix for a real
        bug found in production, where topically-unrelated local-corpus
        items (e.g. an ML course served for a "Mathematics for Engineers"
        node) were shown as if relevant - is that EVERY candidate, from
        EVERY source, must clear the reranker's relevance bar before it's
        shown. Nothing is ever shown just because it's the "least bad" of
        an unfiltered top-N; a slot with nothing genuinely relevant gets
        the honest search-link fallback instead.

          1. Embed all queries as both dense and sparse vectors - dense and
             sparse passes run concurrently (`asyncio.gather`), not
             sequentially.
          2. One Qdrant round trip: per query, prefetch top-N dense and
             top-N sparse candidates and fuse them with RRF (no relevance
             floor at this stage - RRF is rank-based, not a similarity
             score, so a small/narrow corpus will happily return its least-
             irrelevant items for any query with no way to tell they're bad
             yet), then rerank + filter by WEAK_SCORE_THRESHOLD - the exact
             same filter used everywhere below, so a node whose corpus
             matches are genuinely good is already done here. Reranking
             across nodes runs concurrently (one `to_thread` per node), not
             as a sequential Python loop blocking the event loop.
          3. Only nodes still short after that get a real web search - ONE
             concurrency-capped round (not the old two sequential "retry
             only if still short" rounds - collapsing to one round is a
             real latency win, see DECISIONS.md's ~13-15s figure). Critically,
             the web search always uses the reformulated (ancestor-prefix
             stripped) query, never the raw retrieval query: the retrieval
             query is deliberately a long "Goal > Ancestor > Node: details"
             breadcrumb string for embedding quality, but handed to a web
             search engine as literal query text that same string returns
             nothing (confirmed live) - it reads as a run-on sentence with
             literal ">" characters, not a search query. The bare node query
             is what a human would actually type.
          4. The merged pool (corpus + web) gets one final rerank/filter
             pass per node, judged against that same reformulated query.
          5. Any slot still empty after that gets the honest "search
             Google for X" link - never a mis-labeled irrelevant result.
        """
        if not queries:
            return []

        n = len(queries)
        dense_vectors, sparse_vectors = await self._embed(queries)
        candidates_by_node = await self._hybrid_search_batch(dense_vectors, sparse_vectors)

        merged_by_node = list(candidates_by_node)
        good_by_node = await self._rerank_and_filter_many(queries, merged_by_node)

        short_indices = [i for i in range(n) if len(good_by_node[i]) < limit]
        if short_indices:
            # Hard deadline on the whole web-fallback stage, independent of
            # the per-call/per-batch timeouts inside it: those bound one
            # DDG call, not the stage as a whole, so a roadmap with many
            # short nodes could still stack up several waves' worth of
            # waiting. This caps the worst case so a bad DDG day costs a
            # bounded, known tax instead of an open-ended one - whatever
            # hasn't resolved by the deadline gets the honest fallback link
            # instead of continuing to wait.
            try:
                await asyncio.wait_for(
                    self._resolve_web_fallback(short_indices, queries, limit, merged_by_node, good_by_node),
                    timeout=WEB_FALLBACK_STAGE_DEADLINE_SECONDS,
                )
            except asyncio.TimeoutError:
                logger.warning(
                    "resource_agent.web_fallback_stage_deadline_exceeded",
                    node_count=len(short_indices),
                )

        results: list[list[Resource]] = []
        for i in range(n):
            items = good_by_node[i][:limit]
            if len(items) < limit:
                items = items + [self._google_link(queries[i])]
            results.append(items[:limit])
        return results

    async def _resolve_web_fallback(
        self,
        short_indices: list[int],
        queries: list[str],
        limit: int,
        merged_by_node: list[list[dict]],
        good_by_node: list[list[Resource]],
    ) -> None:
        """Mutates merged_by_node/good_by_node in place - split out of
        find_resources_batch so it can be wrapped in a single
        WEB_FALLBACK_STAGE_DEADLINE_SECONDS deadline (see call site)."""
        web_queries = [_reformulate_query(queries[i]) for i in short_indices]
        web_pools = await self._web_search_many(web_queries, limit)

        for i, web in zip(short_indices, web_pools):
            merged_by_node[i] = merged_by_node[i] + web
            logger.info(
                "resource_agent.web_fallback_used",
                query=queries[i],
                good_count_before_web=len(good_by_node[i]),
            )

        reranked = await self._rerank_and_filter_many(
            web_queries, [merged_by_node[i] for i in short_indices]
        )
        for i, good in zip(short_indices, reranked):
            good_by_node[i] = good

    async def _rerank_and_filter_many(
        self, queries: list[str], candidates_list: list[list[dict]]
    ) -> list[list[Resource]]:
        """Runs _rerank_and_filter for every node concurrently (one
        to_thread per node) instead of a sequential Python loop - the
        cross-encoder inference is CPU-bound, so this overlaps nodes on the
        thread pool rather than blocking the event loop node-by-node."""
        return list(
            await asyncio.gather(
                *[
                    asyncio.to_thread(self._rerank_and_filter, q, c)
                    for q, c in zip(queries, candidates_list)
                ]
            )
        )

    async def _web_search_many(self, queries: list[str], limit: int) -> list[list[dict]]:
        """Runs _web_search_candidates for multiple queries with concurrency
        capped at WEB_SEARCH_MAX_CONCURRENCY - see find_resources_batch's
        docstring for why an uncapped burst reliably triggers DDG's rate
        limiting on any roadmap with more than a couple of weak nodes. All
        queries in one call share one _DdgCircuitBreaker, so once DDG
        starts failing consistently within this batch, later queries in the
        same batch stop paying for a DDG call likely to fail the same way."""
        semaphore = asyncio.Semaphore(WEB_SEARCH_MAX_CONCURRENCY)
        breaker = _DdgCircuitBreaker()

        async def _bounded(query: str) -> list[dict]:
            async with semaphore:
                return await self._web_search_candidates(query, limit, breaker)

        outcomes = await asyncio.gather(*[_bounded(q) for q in queries], return_exceptions=True)
        results = []
        for query, outcome in zip(queries, outcomes):
            if isinstance(outcome, BaseException):
                logger.warning("resource_agent.web_search_failed", query=query, error=str(outcome))
                outcome = []
            results.append(outcome)
        return results

    def _rerank_and_filter(self, query: str, candidates: list[dict]) -> list[Resource]:
        """Reranks candidates and drops anything below WEAK_SCORE_THRESHOLD
        - the single point where "is this actually relevant" is decided,
        used for both the primary pass and the retry pass so there's no
        second, looser path a bad result could sneak through."""
        ranked = self._rerank(query, candidates)
        good = [resource for score, resource in ranked if score >= WEAK_SCORE_THRESHOLD]
        seen_urls: set[str] = set()
        deduped = []
        for resource in good:
            if resource.url in seen_urls:
                continue
            seen_urls.add(resource.url)
            deduped.append(resource)
        return deduped

    async def _embed(self, queries: list[str]):
        async def _dense():
            try:
                return await asyncio.to_thread(lambda: list(self.dense_model.query_embed(queries)))
            except Exception as e:
                logger.warning("resource_agent.dense_embed_failed", error=str(e))
                return [None] * len(queries)

        async def _sparse():
            try:
                return await asyncio.to_thread(lambda: list(self.sparse_model.query_embed(queries)))
            except Exception as e:
                logger.warning("resource_agent.sparse_embed_failed", error=str(e))
                return [None] * len(queries)

        # Dense and sparse are independent ONNX inference passes - run
        # concurrently instead of paying their cost twice, sequentially.
        dense, sparse = await asyncio.gather(_dense(), _sparse())
        return dense, sparse

    async def _hybrid_search_batch(self, dense_vectors, sparse_vectors) -> list[list[dict]]:
        """Returns, per query index, a list of {"resource": Resource, "text": str}
        candidate dicts (text is what gets reranked against)."""
        n = len(dense_vectors)
        out: list[list[dict]] = [[] for _ in range(n)]
        valid_indices = [
            i for i in range(n) if dense_vectors[i] is not None and sparse_vectors[i] is not None
        ]
        if not valid_indices:
            return out

        try:
            from qdrant_client.http.models import (
                Fusion,
                FusionQuery,
                Prefetch,
                QueryRequest,
                SparseVector,
            )

            requests = []
            for i in valid_indices:
                sv = sparse_vectors[i]
                requests.append(
                    QueryRequest(
                        prefetch=[
                            Prefetch(
                                query=dense_vectors[i].tolist(),
                                using=DENSE_VECTOR_NAME,
                                limit=CANDIDATE_POOL_SIZE,
                            ),
                            Prefetch(
                                query=SparseVector(indices=sv.indices.tolist(), values=sv.values.tolist()),
                                using=SPARSE_VECTOR_NAME,
                                limit=CANDIDATE_POOL_SIZE,
                            ),
                        ],
                        query=FusionQuery(fusion=Fusion.RRF),
                        limit=CANDIDATE_POOL_SIZE,
                        with_payload=True,
                    )
                )
            responses = await self.qdrant_client.query_batch_points(
                collection_name=COLLECTION_NAME, requests=requests
            )
        except Exception as e:
            logger.warning("resource_agent.hybrid_search_failed", error=str(e))
            return out

        for pos, i in enumerate(valid_indices):
            for point in responses[pos].points:
                payload = point.payload or {}
                url = _safe_url(payload.get("url", ""))
                if not url:
                    continue
                resource = Resource(
                    id=str(point.id),
                    title=payload.get("title", "Unknown"),
                    url=url,
                    description=_truncate(payload.get("description", "")),
                    type=payload.get("content_type", "resource"),
                )
                text = f"{payload.get('title', '')}: {payload.get('description', '')}"
                out[i].append({"resource": resource, "text": text})

        return out

    def _rerank(self, query: str, candidates: list[dict]) -> list[tuple[float, Resource]]:
        if not candidates:
            return []
        texts = [c["text"] for c in candidates]
        try:
            scores = list(self.reranker.rerank(query, texts))
        except Exception as e:
            logger.warning("resource_agent.rerank_failed", error=str(e))
            # Fall back to the existing fused (RRF) order rather than failing
            # the request outright.
            scores = list(range(len(candidates), 0, -1))
        paired = list(zip(scores, [c["resource"] for c in candidates]))
        paired.sort(key=lambda pair: pair[0], reverse=True)
        return paired

    async def _web_search_candidates(
        self, query: str, needed: int, breaker: "_DdgCircuitBreaker | None" = None
    ) -> list[dict]:
        """Real web search results as candidate dicts ({"resource", "text"})
        for the joint rerank pool - NOT pre-filtered or pre-selected here.
        Whether any of these are good enough to show is decided once, later,
        by _rerank_and_filter. Time-boxed so one slow search can't stall the
        whole batch; returns an empty list (never a synthetic placeholder
        "resource") on timeout or failure - the caller decides what an empty
        pool means."""
        if needed <= 0:
            return []
        try:
            return await asyncio.wait_for(
                self._web_search_candidates_inner(query, needed, breaker), timeout=WEB_SEARCH_TIMEOUT_SECONDS
            )
        except asyncio.TimeoutError:
            logger.warning("resource_agent.web_search_timeout", query=query)
            return []
        except Exception as e:
            logger.warning("resource_agent.web_search_failed", query=query, error=str(e))
            return []

    async def _web_search_candidates_inner(
        self, query: str, needed: int, breaker: "_DdgCircuitBreaker | None" = None
    ) -> list[dict]:
        candidates: list[dict] = []

        # DuckDuckGo (via the `ddgs` package - the maintained successor to
        # the deprecated, aggressively-rate-limited `duckduckgo-search`). A
        # general tutorial/course query and a YouTube-restricted query run
        # concurrently so surfacing a video result doesn't cost extra
        # latency - both share the same timeout budget as a single call. If
        # the batch's circuit breaker has already tripped (several
        # consecutive DDG failures for other nodes in this same batch),
        # skip straight to Wikipedia - see DDG_CIRCUIT_BREAKER_THRESHOLD.
        if breaker is not None and breaker.tripped:
            logger.info("resource_agent.ddg_skipped_circuit_open", query=query)
        else:
            general_results, youtube_results = [], []
            try:
                general_task = asyncio.to_thread(
                    self.ddgs.text, f"{query} tutorial course", max_results=max(needed, 3)
                )
                youtube_task = asyncio.to_thread(self.ddgs.text, f"{query} site:youtube.com", max_results=2)
                general_results, youtube_results = await asyncio.wait_for(
                    asyncio.gather(general_task, youtube_task, return_exceptions=True),
                    timeout=DDG_CALL_TIMEOUT_SECONDS,
                )
                if isinstance(general_results, Exception):
                    logger.warning("resource_agent.ddg_general_failed", query=query, error=str(general_results))
                    general_results = []
                if isinstance(youtube_results, Exception):
                    logger.warning("resource_agent.ddg_youtube_failed", query=query, error=str(youtube_results))
                    youtube_results = []
            except asyncio.TimeoutError:
                # A hung DDG call - not "no results", genuinely no response
                # within DDG_CALL_TIMEOUT_SECONDS. Fails fast rather than
                # burning the full WEB_SEARCH_TIMEOUT_SECONDS budget.
                logger.warning("resource_agent.ddg_timeout", query=query)
            except Exception as e:
                logger.warning("resource_agent.ddg_failed", query=query, error=str(e))
            finally:
                # Always report to the breaker, including on timeout - this
                # is the fix for the breaker never tripping under a hanging
                # DDG (see DDG_CALL_TIMEOUT_SECONDS's docstring).
                if breaker is not None:
                    breaker.record(succeeded=bool(general_results or youtube_results))

            seen_urls: set[str] = set()
            for res in [*(youtube_results or []), *(general_results or [])]:
                url = _safe_url(res.get("href", ""))
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                title = res.get("title", "")
                body = res.get("body", "")
                candidates.append(
                    {
                        "resource": Resource(
                            title=title,
                            url=url,
                            description=_truncate(body),
                            type=_resource_type_for_url(url),
                        ),
                        "text": f"{title}: {body}",
                    }
                )

        # Wikipedia summary API: free, no API key, best-effort. Also just a
        # candidate - reranked and filtered like everything else, not given
        # a free pass just for being a real source.
        wiki_resource = await self._wikipedia_fallback(query)
        if wiki_resource:
            candidates.append({"resource": wiki_resource, "text": f"{wiki_resource.title}: {wiki_resource.description}"})

        return candidates

    async def _wikipedia_fallback(self, query: str) -> Resource | None:
        title = urllib.parse.quote(query.strip().replace(" ", "_"))
        url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{title}"
        try:
            async with httpx.AsyncClient(timeout=WIKIPEDIA_TIMEOUT_SECONDS) as client:
                resp = await client.get(url)
            if resp.status_code != 200:
                return None
            data = resp.json()
            page_url = _safe_url(data.get("content_urls", {}).get("desktop", {}).get("page", ""))
            if not page_url:
                return None
            return Resource(
                title=data.get("title", query),
                url=page_url,
                description=_truncate(data.get("extract", "")),
                type="Wikipedia",
            )
        except Exception as e:
            # Best-effort: swallow failures, this is just one fallback of several.
            logger.info("resource_agent.wikipedia_failed", query=query, error=str(e))
            return None

    def _google_link(self, query: str) -> Resource:
        encoded_query = urllib.parse.quote(query)
        return Resource(
            title=f"Search Google for '{query}'",
            url=f"https://www.google.com/search?q={encoded_query}",
            description="No direct resources found. Click to search on Google.",
            type="Search Link",
        )

    async def find_resources_async(self, query: str, limit: int = 3) -> list[Resource]:
        batch = await self.find_resources_batch([query], limit=limit)
        return batch[0] if batch else []

    def find_resources(self, query: str, limit: int = 3) -> list[Resource]:
        """Synchronous convenience method kept for backward compatibility -
        scripts/evaluation/evaluate_retrieval.py (owned by another
        workstream) calls this exact signature. Internally delegates to the
        async batch path with a single-item batch."""
        return asyncio.run(self.find_resources_async(query, limit=limit))
