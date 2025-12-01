import requests
import json
import time
import subprocess
import sys
import os

def test_wide_scope():
    # Start the API in a subprocess
    print("Starting API server...")
    api_process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.app.main:app", "--host", "127.0.0.1", "--port", "8001"], # Use different port
        cwd=os.getcwd(),
        env={**os.environ, "PYTHONPATH": os.getcwd()}
    )
    
    try:
        # Wait for server to start
        print("Waiting for server to start...")
        for _ in range(10):
            try:
                requests.get("http://127.0.0.1:8001/health")
                print("Server is ready!")
                break
            except requests.exceptions.ConnectionError:
                time.sleep(2)
        else:
            print("Server failed to start.")
            return

        # Test Roadmap Generation for a NON-educational topic
        goal = "Advanced Pottery Glazing"
        print(f"\nRequesting roadmap for: {goal}")
        
        response = requests.post(
            "http://127.0.0.1:8001/generate-roadmap",
            json={"goal": goal}
        )
        
        if response.status_code == 200:
            print("\nSuccess! Roadmap generated:")
            data = response.json()
            # print(json.dumps(data, indent=2)) # Too verbose
            
            has_web_resources = False
            print("\nResources found:")
            for node in data.get("nodes", []):
                print(f"\nNode: {node['title']}")
                for res in node.get("resources", []):
                    print(f"  - [{res.get('type')}] {res.get('title')}")
                    if res.get("type") == "Web Resource":
                        has_web_resources = True
            
            if has_web_resources:
                print("\n[PASS] Found 'Web Resource' items! Wide scope is working.")
            else:
                print("\n[FAIL] No 'Web Resource' items found. Local search might be too broad or Web search failed.")
                
        else:
            print(f"\nError: {response.status_code}")
            print(response.text)
            
    finally:
        print("\nStopping server...")
        api_process.terminate()
        api_process.wait()

if __name__ == "__main__":
    test_wide_scope()
