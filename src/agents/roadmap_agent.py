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


PHASE_JSON_SCHEMA = {
    "name": "roadmap_phases",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "phases": {
                "type": "array",
                "minItems": 3,
                "maxItems": 4,
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "maxLength": 40},
                        "focus": {"type": "string", "maxLength": 120},
                    },
                    "required": ["name", "focus"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["phases"],
        "additionalProperties": False,
    },
}

# Node schema for stage-2 expansion: typed curriculum nodes with effort +
# outcomes so the frontend can render duration/difficulty and the retriever
# can match resource level. Prerequisites here are phase-local ids; the
# engine rewrites them to global ids and stitches cross-phase edges.
STAGE2_NODE_SCHEMA = {
    "name": "phase_nodes",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "nodes": {
                "type": "array",
                "minItems": 2,
                "maxItems": 3,
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {
                            "type": "string",
                            "pattern": "^[a-z0-9_]{2,32}$",
                        },
                        "title": {"type": "string", "maxLength": 48},
                        "description": {"type": "string", "maxLength": 160},
                        "search_query": {"type": "string", "maxLength": 80},
                        "prerequisites": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "node_type": {"type": "string"},
                        "est_hours": {"type": "number"},
                        "outcomes": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    "required": [
                        "id",
                        "title",
                        "description",
                        "search_query",
                        "prerequisites",
                        "node_type",
                        "est_hours",
                        "outcomes",
                    ],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["nodes"],
        "additionalProperties": False,
    },
}

LEVEL_GUIDANCE = {
    "beginner": (
        "The learner is a BEGINNER: weight the first half toward true "
        "foundations (no prerequisites), keep jargon minimal, include one "
        "guided setup/first-win node early."
    ),
    "intermediate": (
        "The learner is INTERMEDIATE: compress basics into a single refresher "
        "node, spend most nodes on core techniques and one applied project."
    ),
    "advanced": (
        "The learner is ADVANCED: skip basics entirely, focus on deep topics, "
        "tradeoffs, and a capstone that proves production readiness."
    ),
}


class RoadmapAgent:
    def __init__(self, client=None, model: str | None = None):
        self.client = client or get_openai_client()
        # Configurable via env var; defaults to the cheaper mini model since
        # this is a well-within-range structured task. Set ROADMAP_MODEL=gpt-4o
        # to switch back to the larger model.
        self.model = model or os.getenv("ROADMAP_MODEL", DEFAULT_MODEL)

    async def generate_structure(self, goal: str, level: str = "beginner") -> list:
        """
        Two-stage curriculum planner (falls back to the legacy single call).

        Stage 1 plans 3-4 named phases; stage 2 expands each phase into 2-3
        typed nodes in parallel. Cross-phase edges chain phases in order so
        the result is staged by construction, not by hoping the model emits
        prerequisites. Any stage failure falls back to _generate_single_shot.
        """
        level = (level or "beginner").strip().lower()
        if level not in LEVEL_GUIDANCE:
            level = "beginner"
        try:
            phases = await self._plan_phases(goal, level)
            if not phases:
                return await self._generate_single_shot(goal)
            import asyncio as _asyncio

            expansions = await _asyncio.gather(
                *(self._expand_phase(goal, level, i, p, phases) for i, p in enumerate(phases)),
                return_exceptions=True,
            )
            nodes: list = []
            for exp in expansions:
                if isinstance(exp, list) and exp:
                    nodes.extend(exp)
            if len(nodes) >= 4:
                return self._stitch_cross_phase_edges(nodes, len(phases))
            return await self._generate_single_shot(goal)
        except Exception as e:
            logger.warning("roadmap_agent.two_stage_failed", error=str(e))
            try:
                return await self._generate_single_shot(goal)
            except Exception:
                return []

    async def _plan_phases(self, goal: str, level: str) -> list:
        prompt = (
            f'Plan a learning roadmap for the goal: "{goal}".\n'
            f"{LEVEL_GUIDANCE[level]}\n"
            "Return 3-4 sequential phases (foundations first, capstone last), "
            "each with a short name and one-line focus. No nodes yet."
        )
        response = await self.client.chat.completions.create(
            model=self.model,
            temperature=0.3,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_schema", "json_schema": PHASE_JSON_SCHEMA},
        )
        try:
            data = json.loads(response.choices[0].message.content)
            phases = data.get("phases", [])
            return [p for p in phases if p.get("name")][:4]
        except (json.JSONDecodeError, AttributeError, IndexError, TypeError) as e:
            logger.warning("roadmap_agent.phases_parse_failed", error=str(e))
            return []

    async def _expand_phase(
        self, goal: str, level: str, phase_index: int, phase: dict, all_phases: list
    ) -> list:
        phase_name = phase.get("name", f"Phase {phase_index + 1}")
        phase_focus = phase.get("focus", "")
        prompt = (
            f'Goal: "{goal}". Phase {phase_index + 1}/{len(all_phases)}: "{phase_name}" — {phase_focus}.\n'
            f"{LEVEL_GUIDANCE[level]}\n"
            "Produce 2-3 nodes for THIS phase only. node_type must be one of "
            "foundation/concept/project/capstone (capstone only in the last "
            "phase). est_hours is a realistic 1-20 hour estimate. outcomes are "
            "1-3 concrete skills ('can X'). prerequisites reference only ids "
            "from THIS phase response; cross-phase ordering is handled "
            "separately. Include a keyword search_query per node."
        )
        response = await self.client.chat.completions.create(
            model=self.model,
            temperature=0.3,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_schema", "json_schema": STAGE2_NODE_SCHEMA},
        )
        try:
            data = json.loads(response.choices[0].message.content)
            raw_nodes = data.get("nodes", [])
        except (json.JSONDecodeError, AttributeError, IndexError, TypeError) as e:
            logger.warning("roadmap_agent.phase_parse_failed", error=str(e))
            return []
        # Prefix ids per phase so parallel expansions cannot collide, and
        # rewrite phase-local prerequisite refs to the prefixed ids.
        prefix = f"p{phase_index}_"
        id_map = {}
        for n in raw_nodes:
            old = n.get("id", "node")
            safe = "".join(c if (c.isalnum() or c == "_") else "_" for c in old.lower())[:24] or "node"
            id_map[old] = f"{prefix}{safe}"
        stitched = []
        for n in raw_nodes:
            nid = id_map.get(n.get("id"), f"{prefix}node")
            prereqs = [id_map[p] for p in (n.get("prerequisites") or []) if p in id_map and id_map[p] != nid]
            node_type = (n.get("node_type") or "concept").strip().lower()
            if node_type not in ("foundation", "concept", "project", "capstone"):
                node_type = "capstone" if phase_index == len(all_phases) - 1 else "concept"
            try:
                est = float(n.get("est_hours", 4))
            except (TypeError, ValueError):
                est = 4.0
            est = max(1.0, min(20.0, est))
            stitched.append(
                {
                    "id": nid,
                    "title": n.get("title", "")[:48],
                    "description": n.get("description", "")[:160],
                    "search_query": (n.get("search_query", "") or "")[:80],
                    "prerequisites": prereqs,
                    "_phase": phase_index,
                    "node_type": node_type,
                    "est_hours": est,
                    "outcomes": [str(o)[:80] for o in (n.get("outcomes") or [])[:3]],
                }
            )
        return stitched

    def _stitch_cross_phase_edges(self, nodes: list, num_phases: int) -> list:
        """Chain phases in order: each non-first-phase root gains an edge to
        the last node of the previous phase. Guarantees staged depth by
        construction; intra-phase edges from the model are preserved."""
        by_phase: dict = {}
        for n in nodes:
            by_phase.setdefault(n.get("_phase", 0), []).append(n)
        for phase_i in range(1, num_phases):
            prev_nodes = by_phase.get(phase_i - 1, [])
            cur_nodes = by_phase.get(phase_i, [])
            if not prev_nodes or not cur_nodes:
                continue
            anchor = prev_nodes[-1]["id"]
            for n in cur_nodes:
                if not n.get("prerequisites"):
                    n["prerequisites"] = [anchor]
        for n in nodes:
            n.pop("_phase", None)
        return nodes[:10]

    async def _generate_single_shot(self, goal: str) -> list:
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
