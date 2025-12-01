import requests
import json
import time
import subprocess
import sys
import os

def test_api():
    # Start the API in a subprocess
    print("Starting API server...")
    # Assuming we are running from project root
    api_process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "src.main:app", "--host", "127.0.0.1", "--port", "8000"],
        cwd=os.getcwd(),
        env={**os.environ, "PYTHONPATH": os.getcwd()}
    )
    
    try:
        # Wait for server to start
        print("Waiting for server to start...")
        for _ in range(10):
            try:
                requests.get("http://127.0.0.1:8000/health")
                print("Server is ready!")
                break
            except requests.exceptions.ConnectionError:
                time.sleep(2)
        else:
            print("Server failed to start.")
            return

        # Test Roadmap Generation
        goal = "Learn Machine Learning"
        print(f"\nRequesting roadmap for: {goal}")
        
        response = requests.post(
            "http://127.0.0.1:8000/generate-roadmap",
            json={"goal": goal}
        )
        
        if response.status_code == 200:
            print("\nSuccess! Roadmap generated:")
            data = response.json()
            print(json.dumps(data, indent=2))
        else:
            print(f"\nError: {response.status_code}")
            print(response.text)
            
    finally:
        print("\nStopping server...")
        api_process.terminate()
        api_process.wait()

if __name__ == "__main__":
    test_api()
