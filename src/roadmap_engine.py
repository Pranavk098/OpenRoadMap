import time

import structlog

from .agents.eval_agent import EvaluationAgent
from .agents.resource_agent import ResourceAgent
from .agents.roadmap_agent import RoadmapAgent
from .cache import cache, cache_key
from .dag_validator import validate_dag
from .models import RoadmapNode, RoadmapResponse

logger = structlog.get_logger(__name__)

# Initialize agents
roadmap_agent = RoadmapAgent()
resource_agent = ResourceAgent()
eval_agent = EvaluationAgent()

RESOURCE_LIMIT_PER_NODE = 3


def _ancestor_titles(node_id: str, nodes_by_id: dict, _seen: set | None = None) -> list[str]:
    """Walks one representative prerequisite chain back to a root node,
    returning ancestor titles in root-first order (not including node_id's
    own title). The DAG may have multiple prerequisites per node; we follow
    the first one deterministically since this is just contextual framing
    for a search query, not a structural guarantee.

    `_seen` guards against cycles even though dag_validator.validate_dag
    should already have broken them - belt and suspenders.
    """
    seen = _seen if _seen is not None else set()
    node = nodes_by_id.get(node_id)
    if node is None or node_id in seen:
        return []
    seen.add(node_id)
    prereqs = node.get("prerequisites") or []
    if not prereqs:
        return []
    parent_id = prereqs[0]
    parent = nodes_by_id.get(parent_id)
    if parent is None:
        return []
    return _ancestor_titles(parent_id, nodes_by_id, seen) + [parent["title"]]


def _build_retrieval_query(goal: str, node: dict, nodes_by_id: dict) -> str:
    """Builds the text that actually gets embedded for resource retrieval.

    Uses the LLM-authored `search_query` (a purpose-built, keyword-focused
    search string) instead of the human-facing description, and prepends
    the node's ancestor path so e.g. "Hooks & Effects" is retrieved as
    "React Development > Fundamentals > Hooks & Effects: ..." rather than
    in isolation - the same node title can mean very different things
    depending on what roadmap it's under.
    """
    base_query = node.get("search_query") or f"{node['title']}: {node['description']}"
    ancestors = _ancestor_titles(node["id"], nodes_by_id)
    path = [goal] + ancestors + [node["title"]]
    return f"{' > '.join(path)}: {base_query}"


def _node_summary(node: RoadmapNode) -> dict:
    return {
        "id": node.id,
        "title": node.title,
        "description": node.description,
        "prerequisites": node.prerequisites,
        "node_type": node.node_type,
        "est_hours": node.est_hours,
        "outcomes": node.outcomes,
    }


def _diversify_resources(resources_by_node: list) -> list:
    """Enforce per-roadmap quality rules the retriever cannot see locally:

    - Global URL dedup: the same link never appears under two nodes (second
      occurrence is dropped, keeping the higher-ranked node's copy).
    - At most one Search-Link fallback per roadmap: extra ones become an
      honest practice prompt instead of a fake resource.
    - Type variety per node is preserved by ordering (retriever already ranks
      Video/Course/Docs above Search Link), so this only trims, never
      reorders within a node.
    """
    seen_urls: set = set()
    search_link_used = False
    diversified = []
    for resources in resources_by_node:
        kept = []
        for r in resources:
            url = getattr(r, "url", "") or ""
            rtype = (getattr(r, "type", "") or "").lower()
            if url and url in seen_urls:
                continue
            if "search" in rtype:
                if search_link_used:
                    continue
                search_link_used = True
            if url:
                seen_urls.add(url)
            kept.append(r)
        diversified.append(kept)
    return diversified


async def _get_cached_roadmap(goal: str, level: str = "beginner") -> RoadmapResponse | None:
    try:
        raw = await cache.get(cache_key(goal, level))
    except Exception as e:
        logger.warning("cache.read_failed", error=str(e))
        return None
    if raw is None:
        return None
    try:
        return RoadmapResponse.model_validate_json(raw)
    except Exception as e:
        logger.warning("cache.deserialize_failed", error=str(e))
        return None


async def _set_cached_roadmap(goal: str, roadmap: RoadmapResponse, level: str = "beginner") -> None:
    try:
        await cache.set(cache_key(goal, level), roadmap.model_dump_json())
    except Exception as e:
        # Never let a cache failure affect the response the caller already has.
        logger.warning("cache.write_failed", error=str(e))


async def stream_roadmap_events(goal: str, level: str = "beginner", _result_sink: dict | None = None):
    """
    Async generator driving the whole roadmap pipeline and yielding
    (event_name, payload_dict) tuples in the exact order/shape documented
    as the SSE contract in DECISIONS.md:

      1. ("structure", {"nodes": [...]})   - as soon as the DAG is generated & validated
      2. ("resources", {"id": ..., "resources": [...]})  - once per node, as resources resolve
      3. ("done", {"cache_hit": bool})

    `_result_sink` is an internal-only hook: if a dict is passed, the final
    assembled RoadmapResponse is stashed at `_result_sink["roadmap"]` so
    generate_roadmap() (the non-streaming POST /generate-roadmap path) can
    reuse this exact pipeline instead of duplicating it.
    """
    import asyncio as _asyncio

    total_start = time.perf_counter()
    level = (level or "beginner").strip().lower()
    if level not in ("beginner", "intermediate", "advanced"):
        level = "beginner"

    cached = await _get_cached_roadmap(goal, level)
    if cached is not None:
        if _result_sink is not None:
            _result_sink["roadmap"] = cached
        logger.info(
            "roadmap.timings",
            total_ms=round((time.perf_counter() - total_start) * 1000, 1),
            cache_hit=True,
        )
        yield ("structure", {"nodes": [_node_summary(n) for n in cached.nodes]})
        for node in cached.nodes:
            yield ("resources", {"id": node.id, "resources": [r.model_dump() for r in node.resources]})
        yield ("done", {"cache_hit": True})
        return

    llm_start = time.perf_counter()
    nodes_data = await roadmap_agent.generate_structure(goal, level=level)
    llm_ms = (time.perf_counter() - llm_start) * 1000

    nodes_data = validate_dag(nodes_data)

    yield (
        "structure",
        {
            "nodes": [
                {
                    "id": n["id"],
                    "title": n["title"],
                    "description": n["description"],
                    "prerequisites": n.get("prerequisites", []),
                    "node_type": n.get("node_type"),
                    "est_hours": n.get("est_hours"),
                    "outcomes": n.get("outcomes", []),
                }
                for n in nodes_data
            ]
        },
    )

    nodes_by_id = {n["id"]: n for n in nodes_data}
    queries = [_build_retrieval_query(goal, n, nodes_by_id) for n in nodes_data]
    resources_start = time.perf_counter()
    resources_by_node = (
        await resource_agent.find_resources_batch(queries, limit=RESOURCE_LIMIT_PER_NODE) if queries else []
    )
    resources_ms = (time.perf_counter() - resources_start) * 1000
    resources_by_node = _diversify_resources(resources_by_node)

    roadmap_nodes = []
    for i, n in enumerate(nodes_data):
        resources = resources_by_node[i] if i < len(resources_by_node) else []
        node = RoadmapNode(
            id=n["id"],
            title=n["title"],
            description=n["description"],
            prerequisites=n.get("prerequisites", []),
            resources=resources,
            node_type=n.get("node_type"),
            est_hours=n.get("est_hours"),
            outcomes=n.get("outcomes", []),
        )
        roadmap_nodes.append(node)
        yield ("resources", {"id": node.id, "resources": [r.model_dump() for r in resources]})

    roadmap = RoadmapResponse(goal=goal, nodes=roadmap_nodes)

    try:
        # Eval stays off the streaming hot path: run in a worker thread so a
        # slow model load never delays done/total_ms for the user.
        eval_result = await _asyncio.to_thread(eval_agent.evaluate, roadmap)
        logger.info("eval_agent.result", **eval_result)
    except Exception as e:
        logger.warning("eval_agent.failed", error=str(e))

    await _set_cached_roadmap(goal, roadmap, level)

    total_ms = (time.perf_counter() - total_start) * 1000
    logger.info(
        "roadmap.timings",
        llm_ms=round(llm_ms, 1),
        resources_ms=round(resources_ms, 1),
        total_ms=round(total_ms, 1),
        cache_hit=False,
    )

    if _result_sink is not None:
        _result_sink["roadmap"] = roadmap

    yield ("done", {"cache_hit": False})


async def generate_roadmap(goal: str, level: str = "beginner") -> RoadmapResponse:
    """
    Backward-compatible entry point for POST /generate-roadmap: runs the
    same async pipeline as the SSE stream and collects the final assembled
    RoadmapResponse instead of streaming it.
    """
    sink: dict = {}
    async for _event, _payload in stream_roadmap_events(goal, level=level, _result_sink=sink):
        pass
    return sink["roadmap"]
