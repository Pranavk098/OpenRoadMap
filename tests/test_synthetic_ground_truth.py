import sys
import os

# scripts/evaluation has no __init__.py (not a package) - import the module
# directly by putting its directory on sys.path.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts", "evaluation"))

import generate_synthetic_ground_truth as gsgt


def test_clean_title_for_query_strips_parentheticals_and_marketing_speak():
    title = "React - The Complete Guide (incl. Redux) [2023]"
    cleaned = gsgt.clean_title_for_query(title)
    assert "(" not in cleaned and ")" not in cleaned
    assert "complete guide" not in cleaned.lower()
    assert "2023" not in cleaned
    assert "react" in cleaned.lower()


def test_clean_title_for_query_strips_version_numbers():
    title = "Python 3.11 Bootcamp"
    cleaned = gsgt.clean_title_for_query(title)
    assert "3.11" not in cleaned
    assert "bootcamp" not in cleaned.lower()
    assert "python" in cleaned.lower()


def test_clean_title_for_query_falls_back_to_original_if_fully_stripped():
    # A title that is ENTIRELY catalog noise should not collapse to "".
    title = "(2023)"
    cleaned = gsgt.clean_title_for_query(title)
    assert cleaned  # non-empty


def test_generate_learner_query_variants_uses_templates_not_raw_title():
    title = "React - The Complete Guide (incl. Redux)"
    variants = gsgt.generate_learner_query_variants(title, n=2, seed="fixed-seed")
    assert len(variants) == 2
    for v in variants:
        # Should not just echo the raw catalog title back verbatim.
        assert v != title.lower()
        assert "complete guide" not in v
        # Should follow one of the known templates.
        assert any(v == t.format(topic=gsgt.clean_title_for_query(title).lower()) for t in gsgt.LEARNER_QUERY_TEMPLATES)


def test_generate_learner_query_variants_deterministic_with_seed():
    title = "Intro to Statistics"
    v1 = gsgt.generate_learner_query_variants(title, n=2, seed="abc")
    v2 = gsgt.generate_learner_query_variants(title, n=2, seed="abc")
    assert v1 == v2


def test_generate_learner_query_variants_respects_n():
    title = "Intro to Statistics"
    assert len(gsgt.generate_learner_query_variants(title, n=1, seed="x")) == 1
    assert len(gsgt.generate_learner_query_variants(title, n=3, seed="x")) == 3
    # n larger than available templates is clamped, not an error.
    assert len(gsgt.generate_learner_query_variants(title, n=100, seed="x")) == len(gsgt.LEARNER_QUERY_TEMPLATES)
