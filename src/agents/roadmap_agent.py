import json
import os

import structlog

from ..dependencies import get_openai_client

logger = structlog.get_logger(__name__)

DEFAULT_MODEL = "gpt-4o-mini"

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

SYSTEM_PROMPT = "You are an expert curriculum designer."


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
            "title, description, the ids of any prerequisite nodes, and a "
            "search_query: a short, keyword-focused search-engine query "
            "(not prose) that would find a good tutorial/course for that "
            "node specifically, e.g. 'React hooks useState useEffect "
            "tutorial' rather than a sentence describing the topic."
        )

        response = await self.client.chat.completions.create(
            model=self.model,
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
