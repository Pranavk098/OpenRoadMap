import json
import os

import structlog

from ..dependencies import get_openai_client

logger = structlog.get_logger(__name__)

# Switched from gpt-4o-mini after a live comparison (see DECISIONS.md):
# gpt-4.1-nano is consistently ~30-40% faster on this structure-generation
# call (both non-reasoning models, so no reasoning-effort latency risk),
# cheaper on both input and output tokens, and produced comparably
# coherent, correctly-staged output across every goal tested - the one
# real tradeoff observed is a mild lean toward simpler/more linear DAGs
# (fewer multi-prerequisite convergence nodes) than gpt-4o-mini, not
# incorrect or flat structure.
DEFAULT_MODEL = "gpt-4.1-nano"

# Strict OpenAI structured-outputs schema. This replaces the old few-shot
# examples (React / Sourdough / Agile, ~1,200+ wasted input tokens/call)
# with a hard schema guarantee, so the model no longer needs examples to
# learn the output shape.
ROADMAP_JSON_SCHEMA = {
    "name": "roadmap_structure",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "nodes": {
                "type": "array",
                "minItems": 4,
                "maxItems": 10,
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {
                            "type": "string",
                            "pattern": "^[a-z0-9_]{2,32}$",
                        },
                        "title": {"type": "string", "maxLength": 48},
                        "description": {"type": "string", "maxLength": 160},
                        "search_query": {
                            "type": "string",
                            "maxLength": 80,
                        },
                        "prerequisites": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    "required": ["id", "title", "description", "search_query", "prerequisites"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["nodes"],
        "additionalProperties": False,
    },
}

# A thin one-line system prompt gave the model no actual curriculum-design
# principles to apply, so it fell back to whatever pattern was statistically
# convenient for the goal - the most common user complaint this caused was a
# roadmap that "felt random": most nodes with no prerequisites at all
# (a flat pile rather than a staged path), or nodes ordered by association
# rather than genuine dependency. This prompt states the actual rules a
# curriculum designer would apply, so structure is a reasoned output rather
# than an artifact of the model's prior.
SYSTEM_PROMPT = (
    "You are an expert curriculum designer building a prerequisite-ordered "
    "learning roadmap - a directed acyclic graph, not a flat reading list. "
    "Apply these rules:\n"
    "1. Staged progression: nodes should span beginner -> intermediate -> "
    "advanced. Early nodes are true foundations (no prerequisites); later "
    "nodes build on specific earlier nodes.\n"
    "2. Genuine prerequisites only: a node should list a prerequisite only "
    "if you could not reasonably tackle it without that specific prior "
    "knowledge - not 'everything that came before it'. Most non-foundational "
    "nodes should have exactly 1-2 prerequisites, not zero and not five.\n"
    "3. Avoid an all-parallel structure: if every node ends up with no "
    "prerequisites, the roadmap has failed to model any real learning "
    "order. Aim for a mix - some nodes genuinely can be tackled in "
    "parallel once their prerequisites are met, but the overall shape "
    "should read as a staged path, not a single flat tier.\n"
    "4. Right-sized scope: cover the goal's real learning path end to end "
    "without padding - omit a step only a specialist would need, and don't "
    "split one coherent topic into multiple near-duplicate nodes."
)


class RoadmapAgent:
    def __init__(self, client=None, model: str | None = None):
        self.client = client or get_openai_client()
        # Configurable via env var; defaults to the cheaper mini model since
        # this is a well-within-range structured task. Set ROADMAP_MODEL=gpt-4o
        # to switch back to the larger model.
        self.model = model or os.getenv("ROADMAP_MODEL", DEFAULT_MODEL)

    async def generate_structure(self, goal: str) -> list:
        """
        Generates the DAG structure (nodes and prerequisites) for a given goal.
        """
        prompt = (
            f'Create a learning roadmap for the goal: "{goal}".\n'
            "Produce between 4 and 10 nodes that logically cover the "
            "necessary steps to achieve this goal, each with a short id, "
            "title, description, the ids of any prerequisite nodes (per "
            "the system prompt's rules on genuine, staged prerequisites), "
            "and a search_query: a short, keyword-focused search-engine "
            "query (not prose) that would find a good tutorial/course for "
            "that node specifically, e.g. 'React hooks useState useEffect "
            "tutorial' rather than a sentence describing the topic."
        )

        response = await self.client.chat.completions.create(
            model=self.model,
            # Low, non-zero temperature: this is a structured reasoning task
            # (staged prerequisite ordering) where run-to-run consistency
            # matters more than creative variety, but 0 risks degenerate/
            # repetitive phrasing across very different goals.
            temperature=0.3,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_schema", "json_schema": ROADMAP_JSON_SCHEMA},
        )

        try:
            dag_json = json.loads(response.choices[0].message.content)
            return dag_json.get("nodes", [])
        except (json.JSONDecodeError, AttributeError, IndexError, TypeError) as e:
            logger.warning("roadmap_agent.parse_failed", error=str(e))
            return []
