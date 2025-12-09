from typing import List, Optional
from pydantic import BaseModel, Field

class RoadmapStage(BaseModel):
    stage: int
    title: str
    topics: List[str]
    estimated_time: str

class Roadmap(BaseModel):
    skill: str
    prerequisites: List[str]
    roadmap: List[RoadmapStage]
    source: str = Field(default="manual_annotation")
    annotator: Optional[str] = None
