import pytest

from src.agents.resource_agent import (
    ResourceAgent,
    _DdgCircuitBreaker,
    _reformulate_query,
    _truncate,
    corpus_gap_report,
)
from src.models import Resource


class _ArrayLike(list):
    """Stand-in for the numpy arrays fastembed normally returns - just
    needs .tolist() so resource_agent's `vec.tolist()` calls work."""

    def tolist(self):
        return list(self)


class FakeSparseEmbedding:
    def __init__(self, indices, values):
        self.indices = _ArrayLike(indices)
        self.values = _ArrayLike(values)


class FakeDenseModel:
    def query_embed(self, queries):
        return [_ArrayLike([0.1, 0.2, 0.3]) for _ in queries]


class FakeSparseModel:
    def query_embed(self, queries):
        return [FakeSparseEmbedding([0, 1, 2], [0.5, 0.3, 0.2]) for _ in queries]


class FakeReranker:
    """Scores documents by a caller-supplied function; records every call
    so tests can assert how many rerank passes happened and with what
    query text (e.g. to check the ancestor-prefix reformulation)."""

    def __init__(self, score_fn):
        self.score_fn = score_fn
        self.calls: list[tuple[str, list[str]]] = []

    def rerank(self, query, documents):
        documents = list(documents)
        self.calls.append((query, documents))
        return [self.score_fn(len(self.calls), query, d) for d in documents]


class FakePoint:
    def __init__(self, id, payload):
        self.id = id
        self.payload = payload


class FakeQueryResponse:
    def __init__(self, points):
        self.points = points


class FakeQdrantClient:
    def __init__(self, responses_by_call=None, single_response=None):
        # Either provide one fixed response list (reused for every call) or
        # a queue of responses (one list of FakeQueryResponse per call).
        self._responses_by_call = responses_by_call
        self._single_response = single_response
        self.calls: list[list] = []

    async def query_batch_points(self, collection_name, requests):
        self.calls.append(requests)
        if self._single_response is not None:
            return self._single_response
        return self._responses_by_call.pop(0)


class FakeDDGS:
    def __init__(self, results=None):
        self.results = results if results is not None else []
        self.call_count = 0

    def text(self, query, max_results=3):
        self.call_count += 1
        return list(self.results)[:max_results]


def _point(id_, title, url="https://example.com/x", description="A description"):
    return FakePoint(id_, {"title": title, "url": url, "description": description, "content_type": "resource"})


@pytest.fixture(autouse=True)
def _no_real_network(monkeypatch):
    """Safety net: any test that doesn't explicitly mock the Wikipedia
    fallback's httpx call gets a fake client that fails fast instead of
    silently making a real network call. _wikipedia_fallback treats this
    as just another best-effort failure (it already catches everything),
    so tests not specifically about Wikipedia are unaffected."""

    class _NetworkDisabledAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url):
            raise RuntimeError("real network access is disabled in tests")

    monkeypatch.setattr("src.agents.resource_agent.httpx.AsyncClient", _NetworkDisabledAsyncClient)


def _agent(dense=None, sparse=None, reranker=None, qdrant=None, ddgs=None):
    return ResourceAgent(
        dense_model=dense or FakeDenseModel(),
        sparse_model=sparse or FakeSparseModel(),
        reranker=reranker,
        qdrant_client=qdrant,
        ddgs_client=ddgs or FakeDDGS(),
    )


# --- truncation bug fix -----------------------------------------------------


def test_truncate_short_text_unchanged_no_ellipsis():
    assert _truncate("short text") == "short text"


def test_truncate_long_text_gets_ellipsis():
    long_text = "x" * 250
    result = _truncate(long_text)
    assert result == "x" * 200 + "..."
    assert len(result) == 203


def test_truncate_exact_length_boundary_no_ellipsis():
    exact = "x" * 200
    assert _truncate(exact) == exact


# --- reformulation helper ----------------------------------------------------


def test_reformulate_strips_ancestor_prefix():
    q = "React Development > Fundamentals > Hooks & Effects: useState useEffect tutorial"
    assert _reformulate_query(q) == "Hooks & Effects: useState useEffect tutorial"


def test_reformulate_leaves_query_without_ancestor_prefix_unchanged():
    q = "useState useEffect tutorial"
    assert _reformulate_query(q) == q


# --- hybrid search + rerank happy path --------------------------------------


async def test_hybrid_candidates_reranked_and_top_limit_returned():
    response = FakeQueryResponse(
        [
            _point("1", "Weakest match", url="https://example.com/weakest"),
            _point("2", "Best match", url="https://example.com/best"),
            _point("3", "Middle match", url="https://example.com/middle"),
        ]
    )
    qdrant = FakeQdrantClient(single_response=[response])

    # Reranker deliberately reorders: point "2" scores highest.
    def score_fn(_call_no, _query, text):
        return {"Weakest match": 0.1, "Best match": 5.0, "Middle match": 2.0}[text.split(":")[0]]

    reranker = FakeReranker(score_fn)
    ddgs = FakeDDGS()
    agent = _agent(reranker=reranker, qdrant=qdrant, ddgs=ddgs)

    results = await agent.find_resources_batch(["query for node"], limit=2)

    assert len(results) == 1
    titles = [r.title for r in results[0]]
    assert titles == ["Best match", "Middle match"]
    # Corpus alone already cleared the bar for `limit` slots - web search
    # is gated behind actual need (see find_resources_batch docstring for
    # why an unconditional burst reliably triggers DDG rate limiting), so
    # it's never called here.
    assert ddgs.call_count == 0


async def test_url_scheme_validation_drops_unsafe_urls():
    response = FakeQueryResponse(
        [
            _point("1", "Safe result", url="https://example.com/ok"),
            _point("2", "Unsafe result", url="javascript:alert(1)"),
        ]
    )
    qdrant = FakeQdrantClient(single_response=[response])
    reranker = FakeReranker(lambda _c, _q, _d: 5.0)
    agent = _agent(reranker=reranker, qdrant=qdrant, ddgs=FakeDDGS([]))

    results = await agent.find_resources_batch(["query"], limit=2)

    urls = [r.url for r in results[0]]
    assert "javascript:alert(1)" not in urls
    assert all(u.startswith("http") for u in urls)


# --- agentic retry: weak scores ----------------------------------------------


async def test_weak_scores_trigger_single_bounded_retry_with_reformulated_query():
    original_query = "React Development > Fundamentals > Hooks & Effects: useState tutorial"
    response = FakeQueryResponse([_point("1", "Barely related"), _point("2", "Also weak")])
    qdrant = FakeQdrantClient(single_response=[response])

    def score_fn(call_no, _query, _text):
        # First rerank pass (the original query): everything is weak.
        # Second pass (post-retry, merged candidates): strong.
        return -1.0 if call_no == 1 else 3.0

    reranker = FakeReranker(score_fn)
    ddgs = FakeDDGS([{"title": "Web result", "href": "https://example.com/web", "body": "desc"}])
    agent = _agent(reranker=reranker, qdrant=qdrant, ddgs=ddgs)

    results = await agent.find_resources_batch([original_query], limit=2)

    assert len(results[0]) == 2
    # Web fallback was actually invoked as part of the retry's widening step.
    assert ddgs.call_count >= 1
    # The retry reranked with the ancestor-prefix stripped off.
    assert any(call_query == "Hooks & Effects: useState tutorial" for call_query, _docs in reranker.calls)
    # Exactly two rerank passes happened (one original + one bounded retry) - not more.
    assert len(reranker.calls) == 2


async def test_short_candidate_count_triggers_retry_even_with_strong_scores():
    # Only one candidate for a limit of 3 - should still trigger the retry
    # path (not just the weak-score path) to try to fill out the results.
    response = FakeQueryResponse([_point("1", "Only candidate")])
    qdrant = FakeQdrantClient(single_response=[response])
    reranker = FakeReranker(lambda _c, _q, _d: 5.0)  # strong score, but too few
    ddgs = FakeDDGS(
        [
            {"title": "Extra 1", "href": "https://example.com/1", "body": "d"},
            {"title": "Extra 2", "href": "https://example.com/2", "body": "d"},
        ]
    )
    agent = _agent(reranker=reranker, qdrant=qdrant, ddgs=ddgs)

    results = await agent.find_resources_batch(["some query"], limit=3)

    assert ddgs.call_count >= 1
    assert len(results[0]) <= 3
    assert len(results[0]) >= 2  # original candidate + at least one web result


# --- web fallback tiering: DDG -> Wikipedia -> Google last resort -----------


async def test_wikipedia_used_when_ddg_returns_nothing(monkeypatch):
    qdrant = FakeQdrantClient(single_response=[FakeQueryResponse([])])
    reranker = FakeReranker(lambda _c, _q, _d: 1.0)
    ddgs = FakeDDGS([])  # DDG comes up empty
    agent = _agent(reranker=reranker, qdrant=qdrant, ddgs=ddgs)

    class FakeResponse:
        status_code = 200

        def json(self):
            return {
                "title": "Python (programming language)",
                "extract": "Python is a programming language.",
                "content_urls": {"desktop": {"page": "https://en.wikipedia.org/wiki/Python"}},
            }

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url):
            return FakeResponse()

    monkeypatch.setattr("src.agents.resource_agent.httpx.AsyncClient", FakeAsyncClient)

    results = await agent.find_resources_batch(["Python"], limit=1)

    assert len(results[0]) >= 1
    types = [r.type for r in results[0]]
    assert "Wikipedia" in types


async def test_google_search_link_is_last_resort_when_everything_fails(monkeypatch):
    qdrant = FakeQdrantClient(single_response=[FakeQueryResponse([])])
    reranker = FakeReranker(lambda _c, _q, _d: 1.0)
    ddgs = FakeDDGS([])
    agent = _agent(reranker=reranker, qdrant=qdrant, ddgs=ddgs)

    class FailingAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url):
            raise ConnectionError("no network")

    monkeypatch.setattr("src.agents.resource_agent.httpx.AsyncClient", FailingAsyncClient)

    results = await agent.find_resources_batch(["Obscure Topic"], limit=1)

    assert len(results[0]) == 1
    assert results[0][0].type == "Search Link"
    assert "google.com/search" in results[0][0].url


# --- DDG circuit breaker (added after a live run showed DDG rate-limiting
# under concurrent load, each failed call still costing real latency) -------


def test_circuit_breaker_trips_after_threshold_consecutive_failures():
    breaker = _DdgCircuitBreaker(threshold=3)
    breaker.record(succeeded=False)
    breaker.record(succeeded=False)
    assert not breaker.tripped
    breaker.record(succeeded=False)
    assert breaker.tripped


def test_circuit_breaker_resets_consecutive_count_on_success():
    breaker = _DdgCircuitBreaker(threshold=3)
    breaker.record(succeeded=False)
    breaker.record(succeeded=False)
    breaker.record(succeeded=True)
    breaker.record(succeeded=False)
    breaker.record(succeeded=False)
    assert not breaker.tripped


async def test_tripped_circuit_breaker_skips_ddg_and_uses_wikipedia(monkeypatch):
    ddgs = FakeDDGS([{"title": "Should not be reached", "href": "https://example.com/x", "body": "d"}])
    agent = _agent(ddgs=ddgs)
    breaker = _DdgCircuitBreaker(threshold=1)
    breaker.record(succeeded=False)  # trips immediately with threshold=1

    class FakeResponse:
        status_code = 200

        def json(self):
            return {
                "title": "T",
                "extract": "E",
                "content_urls": {"desktop": {"page": "https://en.wikipedia.org/wiki/T"}},
            }

    class FakeAsyncClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url):
            return FakeResponse()

    monkeypatch.setattr("src.agents.resource_agent.httpx.AsyncClient", FakeAsyncClient)

    candidates = await agent._web_search_candidates_inner("some query", 3, breaker)

    assert ddgs.call_count == 0
    assert any(c["resource"].type == "Wikipedia" for c in candidates)


# --- backward-compatible sync wrapper ---------------------------------------


def test_sync_find_resources_delegates_to_async_batch(monkeypatch):
    captured = {}

    async def fake_batch(self, queries, limit=3):
        captured["queries"] = queries
        captured["limit"] = limit
        return [[Resource(title="T", url="https://example.com", description="d")]]

    monkeypatch.setattr(ResourceAgent, "find_resources_batch", fake_batch)

    agent = _agent()
    result = agent.find_resources("Real Python", limit=5)

    assert captured["queries"] == ["Real Python"]
    assert captured["limit"] == 5
    assert len(result) == 1
    assert result[0].title == "T"


# --- source-trust rerank boost ------------------------------------------------


def _cand(title, url, rtype):
    return {
        "resource": Resource(title=title, url=url, description="d", type=rtype),
        "text": f"{title}: d",
    }


def test_trust_boost_lifts_borderline_trusted_over_threshold():
    # Official docs scoring -0.6 clears the -0.5 bar via its +0.3 boost;
    # a generic web result at the same raw score does not.
    agent = _agent(reranker=FakeReranker(lambda _c, _q, _d: -0.6))
    trusted = agent._rerank_and_filter("q", [_cand("Docs", "https://docs.example.com/x", "Official Documentation")])
    generic = agent._rerank_and_filter("q", [_cand("Blog", "https://blog.example.com/x", "Web Resource")])
    assert len(trusted) == 1
    assert generic == []


def test_trust_boost_does_not_override_clear_relevance_gap():
    def score_fn(_c, _q, text):
        return 4.0 if text.startswith("Strong") else -4.0

    agent = _agent(reranker=FakeReranker(score_fn))
    out = agent._rerank_and_filter(
        "q",
        [
            _cand("Strong generic", "https://a.example.com/1", "Web Resource"),
            _cand("Weak docs", "https://docs.example.com/2", "Official Documentation"),
        ],
    )
    assert [r.title for r in out] == ["Strong generic"]


def test_trust_boost_never_reorders_within_node():
    # Boost applies at the filter step only; relative order stays reranker order.
    def score_fn(_c, _q, text):
        return {"B-web": 3.0, "A-docs": 2.0}[text.split(":")[0]]

    agent = _agent(reranker=FakeReranker(score_fn))
    out = agent._rerank_and_filter(
        "q",
        [_cand("A-docs", "https://docs.example.com/a", "Course"), _cand("B-web", "https://b.example.com/b", "Web Resource")],
    )
    assert [r.title for r in out] == ["B-web", "A-docs"]


# --- corpus-gap report ----------------------------------------------------------


def test_corpus_gap_report_flags_only_short_nodes():
    queries = ["q1", "q2", "q3"]
    good = [
        [Resource(title="A", url="https://a.example.com", description="d")],
        [
            Resource(title="B", url="https://b.example.com", description="d"),
            Resource(title="C", url="https://c.example.com", description="d"),
            Resource(title="D", url="https://d.example.com", description="d"),
        ],
        [],
    ]
    gaps = corpus_gap_report(queries, good, limit=3)
    assert [(g["query"], g["good_count"]) for g in gaps] == [("q1", 1), ("q3", 0)]


def test_corpus_gap_report_empty_when_filled():
    queries = ["q1"]
    good = [[Resource(title="A", url="https://a.example.com", description="d")]]
    assert corpus_gap_report(queries, good, limit=1) == []
