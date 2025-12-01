import sys
import os

# Add src to path
sys.path.append(os.path.join(os.getcwd(), "src"))

from src.agents.resource_agent import ResourceAgent

def verify():
    agent = ResourceAgent()
    print("Searching for 'Real Python'...")
    results = agent.find_resources("Real Python", limit=10)
    
    found = False
    for res in results:
        print(f"- {res.title} ({res.url})")
        if "Real Python" in res.title or "realpython.com" in res.url:
            found = True
            
    if found:
        print("\nSUCCESS: Found 'Real Python' in results!")
    else:
        print("\nFAILURE: 'Real Python' not found.")

if __name__ == "__main__":
    verify()
