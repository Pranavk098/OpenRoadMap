from src.dag_validator import MAX_NODES, validate_dag


def _node(node_id, prereqs=None):
    return {"id": node_id, "title": node_id, "description": node_id, "prerequisites": prereqs or []}


def _has_cycle(nodes):
    adjacency = {n["id"]: n["prerequisites"] for n in nodes}
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {node_id: WHITE for node_id in adjacency}

    def visit(node_id):
        color[node_id] = GRAY
        for prereq in adjacency[node_id]:
            if color[prereq] == GRAY:
                return True
            if color[prereq] == WHITE and visit(prereq):
                return True
        color[node_id] = BLACK
        return False

    return any(visit(node_id) for node_id in adjacency if color[node_id] == WHITE)


def test_empty_input_returns_empty():
    assert validate_dag([]) == []


def test_normal_case_passes_through_unchanged():
    nodes = [_node("a"), _node("b", ["a"]), _node("c", ["b"]), _node("d", ["c"])]
    result = validate_dag(nodes)
    assert [n["id"] for n in result] == ["a", "b", "c", "d"]
    assert result[1]["prerequisites"] == ["a"]
    assert result[3]["prerequisites"] == ["c"]


def test_dangling_prerequisite_reference_is_dropped():
    nodes = [_node("a"), _node("b", ["a", "ghost"]), _node("c", ["b"]), _node("d", ["c"])]
    result = validate_dag(nodes)
    by_id = {n["id"]: n for n in result}
    assert by_id["b"]["prerequisites"] == ["a"]


def test_self_reference_is_dropped():
    nodes = [_node("a", ["a"]), _node("b", ["a"]), _node("c", ["b"]), _node("d", ["c"])]
    result = validate_dag(nodes)
    by_id = {n["id"]: n for n in result}
    assert by_id["a"]["prerequisites"] == []


def test_cycle_is_broken():
    # a -> c -> b -> a is a 3-cycle; d is untouched.
    nodes = [_node("a", ["c"]), _node("b", ["a"]), _node("c", ["b"]), _node("d")]
    result = validate_dag(nodes)
    assert not _has_cycle(result)
    # No nodes were dropped, only an edge.
    assert {n["id"] for n in result} == {"a", "b", "c", "d"}


def test_two_node_cycle_is_broken():
    nodes = [_node("a", ["b"]), _node("b", ["a"]), _node("c"), _node("d")]
    result = validate_dag(nodes)
    assert not _has_cycle(result)


def test_oversized_dag_is_truncated_to_max_nodes():
    nodes = [_node(f"n{i}", [f"n{i - 1}"] if i > 0 else []) for i in range(15)]
    result = validate_dag(nodes)
    assert len(result) == MAX_NODES
    assert not _has_cycle(result)


def test_undersized_dag_is_not_fabricated():
    nodes = [_node("a"), _node("b", ["a"])]
    result = validate_dag(nodes)
    # No fabricated/padded nodes - truthfulness constraint over hitting MIN_NODES.
    assert len(result) == 2


def test_preserves_extra_fields_like_search_query():
    nodes = [{**_node("a"), "search_query": "python basics tutorial"}]
    result = validate_dag(nodes)
    assert result[0]["search_query"] == "python basics tutorial"


def test_fully_flat_structure_is_repaired_into_a_chain():
    # A degenerate LLM response: every node has zero prerequisites, which
    # would render as one undifferentiated tier on the frontend instead of
    # a staged path. Should be repaired into a sequential chain following
    # the model's own emitted order, not left flat.
    nodes = [_node("a"), _node("b"), _node("c"), _node("d"), _node("e")]
    result = validate_dag(nodes)
    assert [n["id"] for n in result] == ["a", "b", "c", "d", "e"]
    assert result[0]["prerequisites"] == []
    assert result[1]["prerequisites"] == ["a"]
    assert result[2]["prerequisites"] == ["b"]
    assert result[3]["prerequisites"] == ["c"]
    assert result[4]["prerequisites"] == ["d"]
    assert not _has_cycle(result)


def test_flat_structure_repair_does_not_fire_with_any_real_prerequisite():
    # Only ONE node has a real prerequisite - not degenerate, leave as-is.
    nodes = [_node("a"), _node("b"), _node("c", ["a"]), _node("d")]
    result = validate_dag(nodes)
    by_id = {n["id"]: n for n in result}
    assert by_id["b"]["prerequisites"] == []
    assert by_id["d"]["prerequisites"] == []
    assert by_id["c"]["prerequisites"] == ["a"]


def test_flat_structure_repair_skipped_below_four_nodes():
    nodes = [_node("a"), _node("b"), _node("c")]
    result = validate_dag(nodes)
    assert all(n["prerequisites"] == [] for n in result)
