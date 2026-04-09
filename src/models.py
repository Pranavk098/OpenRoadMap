from pydantic import BaseModel
from typing import List, Optional

class RoadmapRequest(BaseModel):
    goal: str
    
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
