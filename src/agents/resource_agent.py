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
# BAAI/bge-base-en-v1.5 (768d) was picked over the smaller bge-small/MiniLM
# (384d) for meaningfully better semantic retrieval quality; it's still a
# CPU-only ONNX model with no CUDA dependency. If it turns out too slow/heavy
# for a free-tier CPU deploy in practice, bge-small-en-v1.5 is a drop-in
# same-shape fallback (see DECISIONS.md).
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
# to the caller's requested `limit` (typically 3-5).
CANDIDATE_POOL_SIZE = 50

# ms-marco cross-encoders are trained so a raw (unnormalized) logit score
# above 0 indicates the query/document pair is plausibly relevant, and
# below 0 indicates it probably isn't - there's no fixed "0.4"-style
# probability cutoff to calibrate here, so 0.0 (the model's own decision
# boundary) is used rather than a tuned magic number.
WEAK_SCORE_THRESHOLD = 0.0

WEB_SEARCH_TIMEOUT_SECONDS = 2.5
WIKIPEDIA_TIMEOUT_SECONDS = 1.5
ALLOWED_URL_SCHEMES = {"http", "https"}
DESCRIPTION_MAX_LENGTH = 200


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
        Hybrid batch pipeline:
          1. Embed all queries as both dense and sparse vectors in one pass.
          2. One Qdrant round trip: per query, prefetch top-N dense and
             top-N sparse candidates and fuse them with RRF.
          3. Rerank each node's fused candidates with a cross-encoder and
             keep the top `limit`.
          4. Agentic step: if a node's top results are weak or there simply
             weren't enough candidates, reformulate the query once (drop
             the ancestor-path context) and retry against a merged
             candidate set (existing + a widened web search). Bounded to
             exactly one retry per node.
          5. Any node still short of `limit` falls back to plain web search
             (each fallback individually time-boxed so one slow search
             can't stall the whole batch).
        """
        if not queries:
            return []

        n = len(queries)
        dense_vectors, sparse_vectors = await self._embed(queries)
        candidates_by_node = await self._hybrid_search_batch(dense_vectors, sparse_vectors)

        results: list[list[Resource]] = [[] for _ in range(n)]
        retry_needed: list[int] = []

        for i in range(n):
            ranked = self._rerank(queries[i], candidates_by_node[i])
            if len(ranked) >= limit and all(score >= WEAK_SCORE_THRESHOLD for score, _ in ranked[:limit]):
                results[i] = [resource for _score, resource in ranked[:limit]]
            else:
                retry_needed.append(i)

        if retry_needed:
            retry_outcomes = await asyncio.gather(
                *[self._retry_node(queries[i], candidates_by_node[i], limit) for i in retry_needed],
                return_exceptions=True,
            )
            for idx, outcome in zip(retry_needed, retry_outcomes):
                if isinstance(outcome, BaseException):
                    logger.warning("resource_agent.retry_failed", query=queries[idx], error=str(outcome))
                    outcome = []
                results[idx] = outcome

        # Final safety net: anything still short (e.g. web retry itself came
        # up empty) gets one more plain web-search pass.
        short_indices = [i for i in range(n) if len(results[i]) < limit]
        if short_indices:
            fallback_results = await asyncio.gather(
                *[self._web_fallback(queries[i], limit - len(results[i])) for i in short_indices],
                return_exceptions=True,
            )
            for idx, fb in zip(short_indices, fallback_results):
                if isinstance(fb, BaseException):
                    logger.warning("resource_agent.web_fallback_error", query=queries[idx], error=str(fb))
                    fb = []
                results[idx].extend(fb)

        return [r[:limit] for r in results]

    async def _retry_node(self, query: str, original_candidates: list[dict], limit: int) -> list[Resource]:
        """The one-bounded-retry 'agentic' step: reformulate the query
        (drop ancestor-path context) and widen the candidate pool with a
        fresh web search, then rerank the merged pool jointly. Never
        recurses - this is called at most once per node."""
        reformulated = _reformulate_query(query)
        logger.warning(
            "resource_agent.weak_or_short_results_retry",
            original_query=query,
            reformulated_query=reformulated,
            candidate_count=len(original_candidates),
        )

        extra_resources = await self._web_fallback(reformulated, max(limit, 3))
        merged = list(original_candidates) + [
            {"resource": r, "text": f"{r.title}: {r.description}"} for r in extra_resources
        ]
        ranked = self._rerank(reformulated, merged)
        return [resource for _score, resource in ranked[:limit]]

    async def _embed(self, queries: list[str]):
        try:
            dense = await asyncio.to_thread(lambda: list(self.dense_model.query_embed(queries)))
        except Exception as e:
            logger.warning("resource_agent.dense_embed_failed", error=str(e))
            dense = [None] * len(queries)
        try:
            sparse = await asyncio.to_thread(lambda: list(self.sparse_model.query_embed(queries)))
        except Exception as e:
            logger.warning("resource_agent.sparse_embed_failed", error=str(e))
            sparse = [None] * len(queries)
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

    async def _web_fallback(self, query: str, needed: int) -> list[Resource]:
        if needed <= 0:
            return []
        try:
            return await asyncio.wait_for(
                self._web_fallback_inner(query, needed), timeout=WEB_SEARCH_TIMEOUT_SECONDS
            )
        except asyncio.TimeoutError:
            logger.warning("resource_agent.web_fallback_timeout", query=query)
            return [self._google_link(query)]
        except Exception as e:
            logger.warning("resource_agent.web_fallback_failed", query=query, error=str(e))
            return [self._google_link(query)]

    async def _web_fallback_inner(self, query: str, needed: int) -> list[Resource]:
        resources: list[Resource] = []

        # 1. DuckDuckGo (via the `ddgs` package - the maintained successor
        # to the deprecated, aggressively-rate-limited `duckduckgo-search`).
        try:
            web_results = await asyncio.to_thread(self.ddgs.text, f"{query} tutorial course", max_results=needed)
            if not web_results:
                web_results = await asyncio.to_thread(self.ddgs.text, query, max_results=needed)
            for res in web_results or []:
                url = _safe_url(res.get("href", ""))
                if not url:
                    continue
                resources.append(
                    Resource(
                        title=res.get("title", ""),
                        url=url,
                        description=_truncate(res.get("body", "")),
                        type="Web Resource",
                    )
                )
        except Exception as e:
            logger.warning("resource_agent.ddg_failed", query=query, error=str(e))

        # 2. Wikipedia summary API: free, no API key, best-effort.
        if len(resources) < needed:
            wiki_resource = await self._wikipedia_fallback(query)
            if wiki_resource:
                resources.append(wiki_resource)

        # 3. Last resort: a Google search link.
        if not resources:
            resources.append(self._google_link(query))

        return resources[:needed]

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
