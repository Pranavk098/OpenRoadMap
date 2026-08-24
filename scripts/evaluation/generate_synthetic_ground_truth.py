import json
import os
import random
import re

# Configuration
INPUT_CORPUS = os.path.join("data", "processed", "unified_corpus.json")
OUTPUT_FILE = os.path.join("data", "evaluation", "retrieval_ground_truth.json")
SAMPLE_SIZE = 50

# Sentinel values injected by the ingestion scripts when a title column
# couldn't be resolved. Filtered here defensively even though the
# ingestion scripts now skip these records at the source - raw CSVs may
# not be re-ingestable in every environment, so this corpus could still
# contain older/unclean data.
DEGENERATE_TITLES = {"", "unknown title"}

# --- Realistic (learner-phrased) ground truth ---
#
# generate_ground_truth() above uses each corpus item's own title as the
# query - a known-item search against an (near-)exact string, which any
# reasonable dense retriever should ace. Real users search "how to learn
# react hooks", not "React - The Complete Guide (incl. Redux)". The
# functions below build a SECOND, separate, harder ground-truth set using
# learner-phrased query variants, so the eval harness can report the gap
# between "easy known-item search" and "realistic phrasing" as an
# interpretable finding instead of one misleadingly optimistic number.

REALISTIC_OUTPUT_FILE = os.path.join("data", "evaluation", "retrieval_ground_truth_realistic.json")
VARIANTS_PER_ITEM = 2
LLM_MODEL = "gpt-4o-mini"

# Catalog/marketing phrasing to strip before templating, so a variant isn't
# just the original title echoed back with a prefix glued on.
CATALOG_NOISE_PATTERNS = [
    r'\([^)]*\)',                                                              # parentheticals, e.g. "(incl. Redux)"
    r'\[[^\]]*\]',                                                             # bracketed notes
    r'\b(the complete guide|complete guide|masterclass|bootcamp|from scratch|for beginners|crash course|specialization)\b',
    r'\b(19|20)\d{2}\b',                                                       # bare 4-digit years
    r'\bv?\d+(?:\.\d+){1,2}\b',                                                # version numbers, e.g. "3.11", "v2.0"
]

LEARNER_QUERY_TEMPLATES = [
    "how to learn {topic}",
    "beginner guide to {topic}",
    "{topic} for beginners",
    "intro to {topic}",
]


def clean_title_for_query(title: str) -> str:
    """Strip catalog/marketing noise from a title before templating it."""
    cleaned = title
    for pattern in CATALOG_NOISE_PATTERNS:
        cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'[-:|]+', ' ', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned if cleaned else title.strip()


def generate_learner_query_variants(title: str, n: int = 2, seed=None) -> list:
    """
    Heuristic, template-based learner-phrased query variants.

    No API key or live service required - this is real, runnable logic
    (unlike generate_learner_query_llm below).
    """
    topic = clean_title_for_query(title).lower()
    n = min(n, len(LEARNER_QUERY_TEMPLATES))
    rng = random.Random(seed if seed is not None else topic)
    chosen_templates = rng.sample(LEARNER_QUERY_TEMPLATES, n)
    return [t.format(topic=topic) for t in chosen_templates]


def generate_learner_query_llm(title: str, client=None) -> str:
    """
    LLM-phrased alternative to generate_learner_query_variants: asks a
    model to rephrase a catalog title into a natural learner search query.

    CODE-COMPLETE BUT UNEXECUTED in this environment - there is no
    OPENAI_API_KEY / live OpenAI access available here, so this function
    has NOT been run or validated against real output. It is not called by
    generate_realistic_ground_truth() unless use_llm=True is passed
    explicitly.
    """
    if client is None:
        from src.dependencies import get_openai_client
        client = get_openai_client()  # raises ValueError if OPENAI_API_KEY is unset

    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You rewrite course catalog titles as short, natural search "
                    "queries a beginner learner would actually type. Return ONLY valid JSON."
                ),
            },
            {
                "role": "user",
                "content": (
                    f'Course title: "{title}"\n'
                    'Return a JSON object {"query": "..."} with a short, natural, '
                    "lowercase search query a beginner would type to find this topic - "
                    "not the catalog title itself."
                ),
            },
        ],
        response_format={"type": "json_object"},
    )
    return json.loads(response.choices[0].message.content)["query"]


def _load_items_for_realistic_variants():
    """
    Returns (items, source_description). items is a list of dicts with at
    least 'id', 'title', 'source' keys to generate learner-phrased queries
    from.

    Prefers the full ingested corpus (INPUT_CORPUS); falls back to the
    already-generated known-item ground truth file's source_item entries
    when the raw corpus isn't available in this environment (e.g. no
    data/processed/unified_corpus.json here), so the heuristic generator
    still has real, already-cleaned data to run against.
    """
    if os.path.exists(INPUT_CORPUS):
        with open(INPUT_CORPUS, 'r', encoding='utf-8') as f:
            corpus = json.load(f)
        sample = corpus if len(corpus) < SAMPLE_SIZE else random.sample(corpus, SAMPLE_SIZE)
        return sample, f"corpus sample from {INPUT_CORPUS}"

    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
            known_item_gt = json.load(f)
        items = []
        for entry in known_item_gt:
            ids = entry.get('relevant_resource_ids') or []
            if not ids:
                continue
            items.append({
                "id": ids[0],
                "title": entry['source_item']['title'],
                "source": entry['source_item'].get('source', ''),
            })
        return items, (
            f"fallback: source_item entries from already-generated {OUTPUT_FILE} "
            "(no raw corpus available in this environment)"
        )

    return [], "no corpus or existing ground truth file available"


def generate_realistic_ground_truth(use_llm: bool = False):
    """
    Builds data/evaluation/retrieval_ground_truth_realistic.json: a second,
    harder ground-truth set using learner-phrased queries instead of raw
    catalog titles. Kept separate from retrieval_ground_truth.json (the
    known-item/easy set) so both can be reported and compared.
    """
    items, source_desc = _load_items_for_realistic_variants()
    if not items:
        print(f"Error: no items available to generate realistic ground truth ({source_desc}).")
        return

    print(f"Generating learner-phrased ground truth from {len(items)} items ({source_desc})...")
    if use_llm:
        print("use_llm=True: calling OpenAI to phrase queries (requires OPENAI_API_KEY).")

    ground_truth = []
    seen_queries = set()
    skipped = 0

    for item in items:
        title = item.get('title', '')
        normalized_title = title.strip().lower() if isinstance(title, str) else ""
        if normalized_title in DEGENERATE_TITLES:
            skipped += 1
            continue

        if use_llm:
            try:
                variants = [generate_learner_query_llm(title)]
            except Exception as e:
                print(f"LLM query generation failed for '{title}': {e}")
                continue
        else:
            variants = generate_learner_query_variants(title, n=VARIANTS_PER_ITEM, seed=item.get('id', title))

        for query in variants:
            normalized_query = query.strip().lower() if isinstance(query, str) else ""
            if not normalized_query or normalized_query in seen_queries:
                skipped += 1
                continue
            seen_queries.add(normalized_query)
            ground_truth.append({
                "query": query,
                "relevant_resource_ids": [item['id']],
                "difficulty": "hard",
                "query_style": "learner_phrased_llm" if use_llm else "learner_phrased_heuristic",
                "source_item": {
                    "title": title,
                    "source": item.get('source', '')
                }
            })

    if skipped:
        print(f"Skipped {skipped} degenerate/duplicate/empty variant(s).")

    os.makedirs(os.path.dirname(REALISTIC_OUTPUT_FILE), exist_ok=True)
    print(f"Saving {len(ground_truth)} realistic ground truth items to {REALISTIC_OUTPUT_FILE}...")
    with open(REALISTIC_OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(ground_truth, f, indent=2)

    print("Realistic ground truth generation complete.")


def generate_ground_truth():
    if not os.path.exists(INPUT_CORPUS):
        print(f"Error: Corpus file not found at {INPUT_CORPUS}")
        print("Please run the ingestion and processing scripts first.")
        return

    print(f"Loading corpus from {INPUT_CORPUS}...")
    with open(INPUT_CORPUS, 'r', encoding='utf-8') as f:
        corpus = json.load(f)

    if len(corpus) < SAMPLE_SIZE:
        print(f"Warning: Corpus has fewer items ({len(corpus)}) than sample size ({SAMPLE_SIZE}). Using all items.")
        sample = corpus
    else:
        sample = random.sample(corpus, SAMPLE_SIZE)

    ground_truth = []
    seen_queries = set()
    skipped = 0

    print("Generating synthetic queries...")
    for item in sample:
        # Strategy: Use the title as the query (Known-Item Search)
        query = item['title']

        # Defensively skip degenerate queries (empty, sentinel "Unknown
        # Title" values from failed ingestion column mapping, or ones we've
        # already used) - an unanswerable query silently drags average
        # Recall down without surfacing a real retrieval problem.
        normalized = query.strip().lower() if isinstance(query, str) else ""
        if normalized in DEGENERATE_TITLES or normalized in seen_queries:
            skipped += 1
            continue
        seen_queries.add(normalized)

        # Create the ground truth entry
        entry = {
            "query": query,
            "relevant_resource_ids": [item['id']],
            "difficulty": "easy", # Exact title match is considered easy
            "source_item": {
                "title": item['title'],
                "source": item['source']
            }
        }
        ground_truth.append(entry)

    if skipped:
        print(f"Skipped {skipped} degenerate/duplicate title(s) when building ground truth.")

    # Ensure output directory exists
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

    print(f"Saving {len(ground_truth)} ground truth items to {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(ground_truth, f, indent=2)

    print("Ground truth generation complete.")

if __name__ == "__main__":
    generate_ground_truth()
    generate_realistic_ground_truth()
