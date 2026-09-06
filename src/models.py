import re
from typing import List, Optional

from pydantic import BaseModel, field_validator

MAX_GOAL_LENGTH = 200
# C0 control characters and DEL. Goal is a short single-line phrase, so
# tabs/newlines/carriage returns are rejected along with the rest.
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x1f\x7f]")


def validate_goal_value(value: str) -> str:
    """Shared validation for a roadmap goal string.

    Used both by the RoadmapRequest pydantic validator (POST body) and by
    src/main.py for the GET /v1/roadmap/stream query parameter, so the two
    entry points enforce identical rules.
    """
    if not isinstance(value, str) or not value.strip():
        raise ValueError("goal must be a non-empty string")
    if len(value) > MAX_GOAL_LENGTH:
        raise ValueError(f"goal must be at most {MAX_GOAL_LENGTH} characters")
    if _CONTROL_CHAR_RE.search(value):
        raise ValueError("goal must not contain control characters")
    return value


class RoadmapRequest(BaseModel):
    goal: str
    # Learner level personalizes depth/scope: beginner gets more foundations,
    # advanced skips basics for depth + capstone. Defaults to beginner for
    # backward compat with existing clients that send only {goal}.
    level: str = "beginner"

    @field_validator("goal")
    @classmethod
    def validate_goal(cls, v: str) -> str:
        return validate_goal_value(v)

    @field_validator("level")
    @classmethod
    def validate_level(cls, v: str) -> str:
        v = (v or "beginner").strip().lower()
        if v not in ("beginner", "intermediate", "advanced"):
            raise ValueError("level must be beginner, intermediate, or advanced")
        return v


class Resource(BaseModel):
    id: Optional[str] = None
    title: str
    url: str
    description: str
    type: Optional[str] = "resource"
    # Diversity + freshness signals (all optional for backward compat with
    # cached roadmaps and existing tests that build bare resources).
    level: Optional[str] = None  # beginner/intermediate/advanced
    duration_min: Optional[int] = None
    free: Optional[bool] = None
    source: Optional[str] = None  # e.g. official docs, course, video


class RoadmapNode(BaseModel):
    id: str
    title: str
    description: str
    resources: List[Resource] = []
    prerequisites: List[str] = []
    progress: Optional[int] = 0  # 0-100 percent
    # Typed curriculum fields from the two-stage planner. Optional so old
    # cached roadmaps and unit tests with bare dicts still validate.
    node_type: Optional[str] = None  # foundation/concept/project/capstone
    est_hours: Optional[float] = None
    outcomes: List[str] = []


class RoadmapResponse(BaseModel):
    goal: str
    nodes: List[RoadmapNode]
    github_repo: Optional[str] = None
