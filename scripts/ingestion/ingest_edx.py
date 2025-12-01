import pandas as pd
import os
import json
import uuid

# Configuration
INPUT_FILE = os.path.join("data", "raw", "edx_courses.csv")
OUTPUT_FILE = os.path.join("data", "processed", "edx_ingested.json")

def ingest_edx():
    if not os.path.exists(INPUT_FILE):
        print(f"Error: Input file not found at {INPUT_FILE}")
        print("Please download the edX dataset and place it in data/raw/")
        return

    print(f"Loading data from {INPUT_FILE}...")
    try:
        df = pd.read_csv(INPUT_FILE)
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return

    ingested_data = []
    
    print(f"Processing {len(df)} records...")
    for _, row in df.iterrows():
        course_id = str(uuid.uuid4())
        
        # Extract fields based on common edX dataset schemas
        title = row.get('title', row.get('Title', 'Unknown Title'))
        summary = row.get('summary', row.get('Summary', ''))
        description_full = row.get('course_description', '')
        
        # Use summary if description is empty, or combine them
        description = summary if summary else description_full
        if not description:
            description = title # Fallback
            
        url = row.get('course_url', row.get('Link', ''))
        if not url or pd.isna(url):
             import urllib.parse
             encoded_title = urllib.parse.quote(title)
             url = f"https://www.edx.org/search?q={encoded_title}"

        institution = row.get('institution', '')
        
        # Create unified record
        record = {
            "id": course_id,
            "title": title,
            "description": description,
            "url": url,
            "source": "edX",
            "quality_score": 0.0, # edX dataset might not have ratings, default to 0 or normalize if available
            "published_date": "",
            "content_type": "Course",
            "raw_metadata": row.to_dict()
        }
        ingested_data.append(record)

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    
    print(f"Saving {len(ingested_data)} records to {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(ingested_data, f, indent=2)
    
    print("Ingestion complete.")

if __name__ == "__main__":
    ingest_edx()
