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

class RoadmapResponse(BaseModel):
    goal: str
    nodes: List[RoadmapNode]
