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

    @field_validator("goal")
    @classmethod
    def validate_goal(cls, v: str) -> str:
        return validate_goal_value(v)


class Resource(BaseModel):
    id: Optional[str] = None
    title: str
    url: str
    description: str
    type: Optional[str] = "resource"


class RoadmapNode(BaseModel):
    id: str
    title: str
    description: str
    resources: List[Resource] = []
    prerequisites: List[str] = []
    progress: Optional[int] = 0  # 0-100 percent


class RoadmapResponse(BaseModel):
    goal: str
    nodes: List[RoadmapNode]
    github_repo: Optional[str] = None
