from src.roadmap_engine import _ancestor_titles, _build_retrieval_query


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
