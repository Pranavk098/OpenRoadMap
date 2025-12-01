import sys
import os
sys.path.append(os.getcwd())

try:
    from src.agents.resource_agent import ResourceAgent
    print("Import successful")
    agent = ResourceAgent()
    print("Agent initialized")
    results = agent.find_resources("React", limit=1)
    print(f"Found {len(results)} results")
    for res in results:
        print(f" - {res.title} (ID: {res.id})")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
