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

    return cleaned
