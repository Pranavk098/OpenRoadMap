import glob
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

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


def run_generation_eval(notes: list) -> dict | None:
    """
    Runs generation-quality eval over data/manual/*.json ground truth by
    generating a roadmap for each skill and scoring it with EvaluationAgent.

    RoadmapAgent calls the OpenAI API directly (src/agents/roadmap_agent.py),
    so this requires OPENAI_API_KEY. If it's unavailable, returns None and
    records why in `notes` rather than fabricating a number.
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
        skill = ground_truth.get("skill")
        if not skill:
            continue

        try:
            nodes_data = roadmap_agent.generate_structure(skill)
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


def run_retrieval_eval(notes: list) -> dict:
    """
    Runs retrieval eval for every (ground-truth set) x (variant) combination.
    Each ground-truth set is reported separately so the gap between "easy
    known-item search" and "realistic learner-phrased" is a visible,
    interpretable finding rather than folded into one number.
    """
    results = {}
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
                r = evaluate_retrieval(variant, ground_truth_file=gt_path)
                if r.get("queries_evaluated", 0) == 0:
                    raise RuntimeError("no queries evaluated")
                set_result[out_key] = r
            except Exception as e:
                notes.append(f"retrieval.{set_key}.{out_key} unavailable: {e}")
                set_result[out_key] = None
        results[set_key] = set_result
    return results


def run_evaluation() -> dict:
    print("Starting Evaluation...")
    notes = []

    retrieval_results = run_retrieval_eval(notes)
    generation_results = run_generation_eval(notes)

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


if __name__ == "__main__":
    run_evaluation()
