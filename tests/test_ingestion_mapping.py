import sys
import os

import pandas as pd
import pytest

# scripts/ingestion has no __init__.py (not a package) - import the modules
# directly by putting their directory on sys.path, same way the scripts
# themselves are run from the project root.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts", "ingestion"))

import ingest_coursera
import ingest_edx


# --- ingest_coursera.resolve_title ---

def test_resolve_title_missing_column_returns_none():
    # Neither 'course_title', 'Title', nor 'title' is present at all.
    df = pd.DataFrame([{"course_organization": "MIT", "course_rating": 4.5}])
    row = df.iloc[0]
    assert ingest_coursera.resolve_title(row) is None


def test_resolve_title_nan_value_returns_none():
    df = pd.DataFrame([{"course_title": float("nan"), "course_organization": "MIT"}])
    row = df.iloc[0]
    assert ingest_coursera.resolve_title(row) is None


def test_resolve_title_empty_string_returns_none():
    df = pd.DataFrame([{"course_title": "   "}])
    row = df.iloc[0]
    assert ingest_coursera.resolve_title(row) is None


def test_resolve_title_found_via_known_variant():
    df = pd.DataFrame([{"Title": "Intro to Statistics"}])
    row = df.iloc[0]
    assert ingest_coursera.resolve_title(row) == "Intro to Statistics"


# --- ingest_edx.resolve_title ---

def test_edx_resolve_title_missing_column_returns_none():
    df = pd.DataFrame([{"summary": "A great course"}])
    row = df.iloc[0]
    assert ingest_edx.resolve_title(row) is None


def test_edx_resolve_title_found():
    df = pd.DataFrame([{"title": "Intro to CS"}])
    row = df.iloc[0]
    assert ingest_edx.resolve_title(row) == "Intro to CS"


# --- End-to-end: a record with no usable title is skipped, not defaulted ---

def test_ingest_coursera_skips_row_with_no_title_column(tmp_path, monkeypatch, capsys):
    df = pd.DataFrame([
        {"course_title": "Real Course", "course_organization": "Org A"},
        {"course_organization": "Org B"},  # no title column at all -> must be skipped
    ])
    input_csv = tmp_path / "coursera_courses.csv"
    df.to_csv(input_csv, index=False)
    output_json = tmp_path / "coursera_ingested.json"

    monkeypatch.setattr(ingest_coursera, "INPUT_FILE", str(input_csv))
    monkeypatch.setattr(ingest_coursera, "OUTPUT_FILE", str(output_json))

    ingest_coursera.ingest_coursera()

    captured = capsys.readouterr()
    assert "skipping row" in captured.out

    import json
    with open(output_json, encoding="utf-8") as f:
        records = json.load(f)

    assert len(records) == 1
    assert records[0]["title"] == "Real Course"
    # The old buggy behavior injected the sentinel "Unknown Title" instead
    # of skipping - assert that never appears in the output.
    assert all(r["title"] != "Unknown Title" for r in records)


def test_ingest_edx_skips_duplicate_titles(tmp_path, monkeypatch, capsys):
    df = pd.DataFrame([
        {"title": "Same Course"},
        {"title": "Same Course"},  # duplicate -> must be skipped
    ])
    input_csv = tmp_path / "edx_courses.csv"
    df.to_csv(input_csv, index=False)
    output_json = tmp_path / "edx_ingested.json"

    monkeypatch.setattr(ingest_edx, "INPUT_FILE", str(input_csv))
    monkeypatch.setattr(ingest_edx, "OUTPUT_FILE", str(output_json))

    ingest_edx.ingest_edx()

    captured = capsys.readouterr()
    assert "duplicate title" in captured.out

    import json
    with open(output_json, encoding="utf-8") as f:
        records = json.load(f)

    assert len(records) == 1
