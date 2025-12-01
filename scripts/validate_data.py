import json
import os
import sys
from pathlib import Path
from roadmap_schema import Roadmap

def validate_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Validate using Pydantic model
        Roadmap(**data)
        print(f"✅ Valid: {file_path}")
        return True
    except json.JSONDecodeError:
        print(f"❌ Invalid JSON: {file_path}")
        return False
    except Exception as e:
        print(f"❌ Schema Error in {file_path}: {e}")
        return False

def main():
    base_dir = Path(__file__).parent.parent / 'data'
    if not base_dir.exists():
        print(f"Data directory not found: {base_dir}")
        return

    success_count = 0
    fail_count = 0

    for root, _, files in os.walk(base_dir):
        for file in files:
            if file.endswith('.json'):
                file_path = Path(root) / file
                if validate_file(file_path):
                    success_count += 1
                else:
                    fail_count += 1

    print(f"\nValidation Complete. Success: {success_count}, Failed: {fail_count}")
    
    if fail_count > 0:
        sys.exit(1)

if __name__ == "__main__":
    main()
