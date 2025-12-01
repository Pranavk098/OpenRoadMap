import json
from ..dependencies import get_openai_client

class RoadmapAgent:
    def __init__(self):
        self.client = get_openai_client()

    def generate_structure(self, goal: str) -> list:
        """
        Generates the DAG structure (nodes and prerequisites) for a given goal.
        """
        prompt = f"""
        Create a learning roadmap for the goal: "{goal}".
        Return a JSON object with a list of "nodes". 
        Each node must have:
        - "id": unique string id (e.g., "basics", "advanced_topic")
        - "title": short display title
        - "description": brief explanation of what to learn
        - "prerequisites": list of node ids that must be completed before this one
        
        Ensure the roadmap is logical and covers the necessary steps.
        Return ONLY valid JSON.
        """
        
        response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are an expert curriculum designer."},
                {"role": "user", "content": """Create a learning roadmap for the goal: "React Development".
Return a JSON object with a list of "nodes". 
Each node must have:
- "id": unique string id (e.g., "basics", "advanced_topic")
- "title": short display title
- "description": brief explanation of what to learn
- "prerequisites": list of node ids that must be completed before this one

Ensure the roadmap is logical and covers the necessary steps.
Return ONLY valid JSON."""},
                {"role": "assistant", "content": """{
  "nodes": [
    {
      "id": "fundamentals",
      "title": "Fundamentals",
      "description": "JSX, Components, Props & State",
      "prerequisites": []
    },
    {
      "id": "hooks_effects",
      "title": "Hooks & Effects",
      "description": "useState, useEffect, Custom Hooks",
      "prerequisites": ["fundamentals"]
    },
    {
      "id": "routing_state",
      "title": "Routing & State Management",
      "description": "React Router, Context API, Redux Toolkit",
      "prerequisites": ["hooks_effects"]
    },
    {
      "id": "advanced_patterns",
      "title": "Advanced Patterns",
      "description": "HOCs, Render Props, Performance Optimization",
      "prerequisites": ["routing_state"]
    }
  ]
}"""},
                {"role": "user", "content": """Create a learning roadmap for the goal: "Sourdough Bread Baking"."""},
                {"role": "assistant", "content": """{
  "nodes": [
    {
      "id": "starter",
      "title": "The Starter",
      "description": "Creating Starter, Feeding Schedule, Discard",
      "prerequisites": []
    },
    {
      "id": "dough_management",
      "title": "Dough Management",
      "description": "Autolyse, Folding, Bulk Fermentation",
      "prerequisites": ["starter"]
    },
    {
      "id": "baking",
      "title": "Baking",
      "description": "Shaping, Scoring, Oven Spring",
      "prerequisites": ["dough_management"]
    }
  ]
}"""},
                {"role": "user", "content": """Create a learning roadmap for the goal: "Agile Project Management"."""},
                {"role": "assistant", "content": """{
  "nodes": [
    {
      "id": "agile_manifesto",
      "title": "Agile Manifesto",
      "description": "Values, Principles, Waterfall vs Agile",
      "prerequisites": []
    },
    {
      "id": "scrum_framework",
      "title": "Scrum Framework",
      "description": "Roles, Events, Artifacts",
      "prerequisites": ["agile_manifesto"]
    },
    {
      "id": "kanban_lean",
      "title": "Kanban & Lean",
      "description": "WIP Limits, Flow, Kaizen",
      "prerequisites": ["scrum_framework"]
    }
  ]
}"""},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        
        try:
            dag_json = json.loads(response.choices[0].message.content)
            return dag_json.get("nodes", [])
        except json.JSONDecodeError:
            print("Error decoding LLM response")
            return []
