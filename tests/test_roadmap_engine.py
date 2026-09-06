from src.models import Resource
from src.roadmap_engine import (
    _ancestor_titles,
    _build_retrieval_query,
    _diversify_resources,
)


def _res(title, url, rtype="Course"):
    return Resource(title=title, url=url, description="d", type=rtype)


def _node(id_, title, prereqs=None, search_query=None, description="desc"):
    n = {"id": id_, "title": title, "description": description, "prerequisites": prereqs or []}
    if search_query is not None:
        n["search_query"] = search_query
    return n


def test_ancestor_titles_for_root_node_is_empty():
    nodes = {"a": _node("a", "Fundamentals")}
    assert _ancestor_titles("a", nodes) == []


def test_ancestor_titles_walks_chain_root_first():
    nodes = {
        "a": _node("a", "Fundamentals"),
        "b": _node("b", "Hooks & Effects", prereqs=["a"]),
        "c": _node("c", "Advanced Patterns", prereqs=["b"]),
    }
    assert _ancestor_titles("c", nodes) == ["Fundamentals", "Hooks & Effects"]


def test_ancestor_titles_handles_cycle_defensively():
    # Should never happen post-dag_validator, but must not infinite-loop.
    nodes = {
        "a": _node("a", "A", prereqs=["b"]),
        "b": _node("b", "B", prereqs=["a"]),
    }
    result = _ancestor_titles("a", nodes)
    assert isinstance(result, list)  # terminates without raising


def test_build_retrieval_query_uses_search_query_and_ancestor_path():
    nodes_data = [
        _node("fundamentals", "Fundamentals", search_query="React JSX components tutorial"),
        _node(
            "hooks",
            "Hooks & Effects",
            prereqs=["fundamentals"],
            search_query="React useState useEffect tutorial",
        ),
    ]
    nodes_by_id = {n["id"]: n for n in nodes_data}

    query = _build_retrieval_query("React Development", nodes_by_id["hooks"], nodes_by_id)

    assert query == "React Development > Fundamentals > Hooks & Effects: React useState useEffect tutorial"


def test_build_retrieval_query_falls_back_to_title_description_when_search_query_missing():
    nodes_data = [_node("basics", "Basics", description="Learn the basics")]
    nodes_by_id = {n["id"]: n for n in nodes_data}

    query = _build_retrieval_query("Learn Guitar", nodes_by_id["basics"], nodes_by_id)

    assert query == "Learn Guitar > Basics: Basics: Learn the basics"


# --- _diversify_resources ----------------------------------------------------


def test_diversify_dedups_shared_url_across_nodes_keeping_first():
    node0 = [_res("A", "https://example.com/shared"), _res("B", "https://example.com/b")]
    node1 = [_res("C", "https://example.com/shared"), _res("D", "https://example.com/d")]
    out = _diversify_resources([node0, node1])
    assert [r.url for r in out[0]] == ["https://example.com/shared", "https://example.com/b"]
    assert [r.url for r in out[1]] == ["https://example.com/d"]


def test_diversify_never_empties_node_with_candidates():
    # Every URL already seen: old code left the node with zero resources.
    node0 = [_res("A", "https://example.com/x")]
    node1 = [_res("B", "https://example.com/x")]
    out = _diversify_resources([node0, node1])
    assert len(out[0]) == 1
    assert len(out[1]) == 1  # kept as duplicate rather than empty


def test_diversify_redundant_search_link_dropped_but_empty_node_keeps_its_own():
    s0 = _res("Search Google for 'q0'", "https://www.google.com/search?q=q0", "Search Link")
    real = _res("Real", "https://example.com/real")
    s1 = _res("Search Google for 'q1'", "https://www.google.com/search?q=q1", "Search Link")
    out = _diversify_resources([[s0], [real, s1]])
    assert out[0][0].type == "Search Link"  # only resource: kept despite cap
    assert [r.title for r in out[1]] == ["Real"]  # redundant fallback trimmed


def test_diversify_caps_same_type_at_two_per_node():
    nodes = [
        [_res("V1", "https://v/1", "Video"), _res("V2", "https://v/2", "Video"), _res("V3", "https://v/3", "Video")]
    ]
    out = _diversify_resources(nodes)
    assert len(out[0]) == 2


def test_diversify_preserves_order_and_mixed_types():
    nodes = [[_res("V", "https://v/1", "Video"), _res("C", "https://c/1", "Course")]]
    out = _diversify_resources(nodes)
    assert [r.type for r in out[0]] == ["Video", "Course"]
