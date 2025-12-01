from .models import RoadmapNode, RoadmapResponse
from .agents.roadmap_agent import RoadmapAgent
from .agents.resource_agent import ResourceAgent
from .agents.eval_agent import EvaluationAgent

# Initialize agents
roadmap_agent = RoadmapAgent()
resource_agent = ResourceAgent()
eval_agent = EvaluationAgent()

def generate_roadmap(goal: str) -> RoadmapResponse:
    print(f"Orchestrator: Starting roadmap generation for '{goal}'...")
    
    # 1. Plan: Generate Structure
    print("Agent: RoadmapAgent working...")
    nodes_data = roadmap_agent.generate_structure(goal)
    
    roadmap_nodes = []
    
    # 2. Curate: Find Resources for each node
    print("Agent: ResourceAgent working...")
    for node_data in nodes_data:
        query = f"{node_data['title']}: {node_data['description']}"
        resources = resource_agent.find_resources(query, limit=3)
        
        roadmap_nodes.append(RoadmapNode(
            id=node_data["id"],
            title=node_data["title"],
            description=node_data["description"],
            prerequisites=node_data.get("prerequisites", []),
            resources=resources
        ))
        
    roadmap = RoadmapResponse(goal=goal, nodes=roadmap_nodes)
    
    # 3. Evaluate: Check Quality
    print("Agent: EvaluationAgent working...")
    eval_result = eval_agent.evaluate(roadmap)
    print(f"Evaluation Result: {eval_result}")
    
    return roadmap
