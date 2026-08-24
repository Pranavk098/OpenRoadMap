import asyncio
import glob
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

# See evaluate_retrieval.py for why: non-ASCII ground-truth text crashes
# Windows' default console codepage otherwise.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Add project root to path
sys.path.append(os.getcwd())

from scripts.evaluation.evaluate_retrieval import (
    GROUND_TRUTH_FILE,
    GROUND_TRUTH_FILE_REALISTIC,
    evaluate_retrieval,
)
from src.agents.eval_agent import EvaluationAgent
from src.models import RoadmapNode, RoadmapResponse

# Retrieval variants compared, keyed by their real, existing technique name -
# never an invented one ("MultiFactor"/"CrossEncoder" never existed in this
# codebase and have been retired). "mmr_reranked" is this track's own
# implementation (src/reranker.py); a separate backend track may add its own
# hybrid/reranking stages to the serving path later, which would show up
# here as additional real variants once they exist - not simulated ahead of
# time.
RETRIEVAL_VARIANTS = [
    ("baseline", "dense_baseline"),
    ("mmr", "mmr_reranked"),
]

# Ground-truth sets compared. See generate_synthetic_ground_truth.py.
GROUND_TRUTH_SETS = [
    (
        "known_item_search",
        GROUND_TRUTH_FILE,
        "Query = the corpus item's own title (near-exact match). Easy / known-item search.",
    ),
    (
        "realistic_learner_phrased",
        GROUND_TRUTH_FILE_REALISTIC,
        "Query = a heuristically generated learner-phrased variant of the title "
        "(e.g. 'how to learn react hooks'), not the catalog title. Harder, more "
        "representative of real usage.",
    ),
]

RESULTS_FILES = [
    os.path.join("data", "evaluation", "results.json"),
    os.path.join("frontend", "public", "eval-results.json"),
]


def get_commit_sha():
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, cwd=os.getcwd()).strip()
    except Exception:
        return None


def load_ground_truth(file_path):
    with open(file_path, "r") as f:
        return json.load(f)


async def run_generation_eval(notes: list) -> dict | None:
    """
    Runs generation-quality eval over data/manual/*.json ground truth by
    generating a roadmap for each skill and scoring it with EvaluationAgent.

    RoadmapAgent calls the OpenAI API directly (src/agents/roadmap_agent.py),
    so this requires OPENAI_API_KEY. If it's unavailable, returns None and
    records why in `notes` rather than fabricating a number.

    Not every data/manual/*.json file is a roadmap ground-truth file - e.g.
    curated_resources.json is the resource corpus (a flat list), not a
    {"skill": ..., "roadmap": [...]} document. Files that don't match the
    expected shape are skipped with a note, not treated as a fatal error -
    one bad/unrelated file in that directory shouldn't discard every other
    result (this previously crashed the whole run with an unhandled
    AttributeError, losing real retrieval results computed earlier in the
    same run).
    """
    try:
        from src.agents.roadmap_agent import RoadmapAgent
        roadmap_agent = RoadmapAgent()  # raises ValueError if OPENAI_API_KEY unset
    except Exception as e:
        notes.append(f"generation eval unavailable: could not initialize RoadmapAgent ({e}). Requires OPENAI_API_KEY.")
        return None

    eval_agent = EvaluationAgent()
    manual_data_dir = os.path.join("data", "manual")
    json_files = glob.glob(os.path.join(manual_data_dir, "*.json"))

    per_skill = []
    for file_path in json_files:
        ground_truth = load_ground_truth(file_path)
        if not isinstance(ground_truth, dict):
            notes.append(f"generation eval: skipped {os.path.basename(file_path)} (not a roadmap ground-truth document).")
            continue
        skill = ground_truth.get("skill")
        if not skill:
            continue

        try:
            nodes_data = await roadmap_agent.generate_structure(skill)
            roadmap_nodes = [
                RoadmapNode(
                    id=n["id"],
                    title=n["title"],
                    description=n["description"],
                    prerequisites=n.get("prerequisites", []),
                    resources=[]
                ) for n in nodes_data
            ]
            generated_roadmap = RoadmapResponse(goal=skill, nodes=roadmap_nodes)
        except Exception as e:
            notes.append(f"generation failed for '{skill}': {e}")
            continue

        gt_topics = []
        for stage in ground_truth.get("roadmap", []):
            gt_topics.extend(stage.get("topics", []))

        metrics = eval_agent.evaluate_roadmap_structure(generated_roadmap, gt_topics)
        per_skill.append({"skill": skill, "metrics": metrics})

    if not per_skill:
        notes.append("generation eval produced no results (no usable manual ground-truth files).")
        return None

    n = len(per_skill)
    return {
        "coverage": sum(r["metrics"]["coverage"] for r in per_skill) / n,
        "precision": sum(r["metrics"]["precision"] for r in per_skill) / n,
        "rouge_l": sum(r["metrics"]["rouge_l"] for r in per_skill) / n,
        "bert_score": sum(r["metrics"]["bert_score"] for r in per_skill) / n,
        "roadmaps_evaluated": n,
        "per_skill": per_skill,
    }


async def run_retrieval_eval(notes: list) -> dict:
    """
    Runs retrieval eval for every (ground-truth set) x (variant) combination.
    Each ground-truth set is reported separately so the gap between "easy
    known-item search" and "realistic learner-phrased" is a visible,
    interpretable finding rather than folded into one number.

    Shares a single ResourceAgent (and therefore a single event loop, via
    the caller's asyncio.run()) across every combination - see the docstring
    on evaluate_retrieval() for why reusing async Qdrant/HTTP clients across
    separate asyncio.run() calls previously broke mid-run.
    """
    results = {}

    any_gt_exists = any(os.path.exists(gt_path) for _, gt_path, _ in GROUND_TRUTH_SETS)
    resource_agent = None
    if any_gt_exists:
        from src.agents.resource_agent import ResourceAgent
        resource_agent = ResourceAgent()

    for set_key, gt_path, description in GROUND_TRUTH_SETS:
        set_result = {"description": description}

        if not os.path.exists(gt_path):
            notes.append(f"retrieval.{set_key} unavailable: ground truth file not found at {gt_path}.")
            for _, out_key in RETRIEVAL_VARIANTS:
                set_result[out_key] = None
            results[set_key] = set_result
            continue

        for variant, out_key in RETRIEVAL_VARIANTS:
            try:
                r = await evaluate_retrieval(variant, ground_truth_file=gt_path, resource_agent=resource_agent)
                if r.get("queries_evaluated", 0) == 0:
                    raise RuntimeError("no queries evaluated")
                set_result[out_key] = r
            except Exception as e:
                notes.append(f"retrieval.{set_key}.{out_key} unavailable: {e}")
                set_result[out_key] = None
        results[set_key] = set_result
    return results


async def _run_evaluation_async() -> dict:
    print("Starting Evaluation...")
    notes = []

    try:
        retrieval_results = await run_retrieval_eval(notes)
    except Exception as e:
        notes.append(f"retrieval eval crashed: {e}")
        retrieval_results = {set_key: {"description": desc, **{out_key: None for _, out_key in RETRIEVAL_VARIANTS}}
                              for set_key, _, desc in GROUND_TRUTH_SETS}

    try:
        generation_results = await run_generation_eval(notes)
    except Exception as e:
        notes.append(f"generation eval crashed: {e}")
        generation_results = None

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "commit_sha": get_commit_sha(),
        "retrieval": retrieval_results,
        "generation": generation_results,
        "notes": notes,
    }

    for path in RESULTS_FILES:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2)
        print(f"Wrote results to {path}")

    print("\n=== Evaluation Summary ===")
    print(json.dumps(output, indent=2, default=str))
    return output


def run_evaluation() -> dict:
    return asyncio.run(_run_evaluation_async())


if __name__ == "__main__":
    run_evaluation()
