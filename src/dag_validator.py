"""Server-side validation of the roadmap DAG returned by the LLM.

Belt-and-suspenders: a separate workstream hardens the frontend renderer
against a malformed graph, but the source of truth (this API) should never
hand out a broken DAG in the first place.
"""

import structlog

logger = structlog.get_logger(__name__)

MIN_NODES = 4
MAX_NODES = 10


def validate_dag(nodes: list[dict]) -> list[dict]:
    """Validate and repair a list of roadmap node dicts.

    - Truncates to MAX_NODES if the LLM returned too many.
    - Drops prerequisite references to node ids that don't exist (or to
      the node's own id).
    - Breaks any prerequisite cycles by dropping the cycle-closing edge.
    - Logs a warning (via structlog, correlation id picked up from
      contextvars bound by the request middleware) for every repair made.

    Does not fabricate nodes: if fewer than MIN_NODES are given, they are
    returned as-is (a warning is logged) since inventing content would
    violate the truthfulness/no-fabrication principle of this system.
    """
    if not nodes:
        return []

    working = list(nodes)

    if len(working) > MAX_NODES:
        logger.warning(
            "dag_validator.truncated",
            original_count=len(working),
            max_nodes=MAX_NODES,
        )
        working = working[:MAX_NODES]

    if len(working) < MIN_NODES:
        logger.warning(
            "dag_validator.undersized",
            count=len(working),
            min_nodes=MIN_NODES,
        )

    valid_ids = {n["id"] for n in working if "id" in n}

    cleaned = []
    for n in working:
        node_id = n.get("id")
        raw_prereqs = n.get("prerequisites") or []
        prereqs = [p for p in raw_prereqs if p in valid_ids and p != node_id]
        dropped = [p for p in raw_prereqs if p not in prereqs]
        if dropped:
            logger.warning(
                "dag_validator.dangling_prereq_dropped",
                node_id=node_id,
                dropped=dropped,
            )
        cleaned.append({**n, "prerequisites": prereqs})

    # Break cycles: DFS over the "depends on" graph (node -> prerequisite),
    # dropping the edge that closes a cycle (a back-edge to a node
    # currently on the recursion stack).
    adjacency = {n["id"]: list(n["prerequisites"]) for n in cleaned}
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {node_id: WHITE for node_id in adjacency}

    def visit(node_id: str) -> None:
        color[node_id] = GRAY
        for prereq in list(adjacency[node_id]):
            if color.get(prereq) == GRAY:
                adjacency[node_id].remove(prereq)
                logger.warning(
                    "dag_validator.cycle_broken",
                    node_id=node_id,
                    dropped_prereq=prereq,
                )
                continue
            if color.get(prereq) == WHITE:
                visit(prereq)
        color[node_id] = BLACK

    for node_id in list(adjacency.keys()):
        if color[node_id] == WHITE:
            visit(node_id)

    for n in cleaned:
        n["prerequisites"] = adjacency[n["id"]]

    _repair_degenerate_flat_structure(cleaned)
    _enforce_capstone_depth(cleaned)

    return cleaned


def _enforce_capstone_depth(nodes: list[dict]) -> None:
    """Guarantee staged depth for the single-shot fallback path: if every
    node except the last already has prerequisites (a staged chain with a
    flat tail), link the orphaned tail to its predecessor. Leaves partially
    flat graphs alone — the flat-repair above owns the fully-degenerate case
    and the test suite pins partial-flat as leave-as-is."""
    if len(nodes) < 4:
        return
    last = nodes[-1]
    if last.get("prerequisites"):
        return
    if not all(n.get("prerequisites") for n in nodes[:-1]):
        return
    prev_id = nodes[-2].get("id")
    if prev_id and prev_id != last.get("id"):
        logger.warning(
            "dag_validator.capstone_linked",
            node_id=last.get("id"),
            anchor=prev_id,
        )
        last["prerequisites"] = [prev_id]


def _repair_degenerate_flat_structure(nodes: list[dict]) -> None:
    """Belt-and-suspenders for a prompt/model failure, not the primary fix
    (that's a stronger system prompt in roadmap_agent.py): if every single
    node came back with zero prerequisites, the LLM produced a flat pile
    rather than any staged learning order at all, and the frontend would
    render every node as parallel siblings on one tier. Rather than ship
    that, fall back to chaining each node to the previous one in the
    model's own emitted order - a reasonable default sequence (the model
    already tends to emit nodes in a sensible rough order even when it
    forgets to encode prerequisites), not fabricated content since no
    node's title/description/id changes, only the (already-empty, already
    admittedly wrong) relationships. Only fires on this fully degenerate
    case - any real prerequisite anywhere is left untouched.
    """
    if len(nodes) < 4:
        return
    if any(n["prerequisites"] for n in nodes):
        return
    logger.warning("dag_validator.flat_structure_repaired", node_count=len(nodes))
    for i in range(1, len(nodes)):
        nodes[i]["prerequisites"] = [nodes[i - 1]["id"]]
