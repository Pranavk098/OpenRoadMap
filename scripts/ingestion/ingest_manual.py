import json
import os
import uuid

# Configuration
INPUT_FILE = os.path.join("data", "manual", "curated_resources.json")
OUTPUT_FILE = os.path.join("data", "processed", "manual_ingested.json")

def ingest_manual():
    if not os.path.exists(INPUT_FILE):
        print(f"Error: Input file not found at {INPUT_FILE}")
        return

    print(f"Loading data from {INPUT_FILE}...")
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        raw_data = json.load(f)

    ingested_data = []
    
    print(f"Processing {len(raw_data)} records...")
    for item in raw_data:
        # Generate a unique ID if not present
        resource_id = str(uuid.uuid4())
        
        # Create unified record
        record = {
            "id": resource_id,
            "title": item.get("title", "Unknown Title"),
            "description": item.get("description", ""),
            "url": item.get("url", ""),
            "source": item.get("source", "Manual"),
            "quality_score": item.get("quality_score", 0.5),
            "published_date": "",
            "content_type": item.get("type", "Resource"),
            "raw_metadata": item
        }
        ingested_data.append(record)

    # Ensure output directory exists
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    
    print(f"Saving {len(ingested_data)} records to {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(ingested_data, f, indent=2)
    
    print("Ingestion complete.")

if __name__ == "__main__":
    ingest_manual()
