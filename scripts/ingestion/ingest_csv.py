import pandas as pd
import os
import json
import uuid
import sys

# Configuration
# Usage: python scripts/ingestion/ingest_csv.py <path_to_csv> <source_name>
# Example: python scripts/ingestion/ingest_csv.py data/raw/udemy_courses.csv Udemy

def ingest_csv(input_file, source_name):
    if not os.path.exists(input_file):
        print(f"Error: Input file not found at {input_file}")
        return

    output_filename = f"{source_name.lower()}_ingested.json"
    output_file = os.path.join("data", "processed", output_filename)

    print(f"Loading data from {input_file}...")
    try:
        df = pd.read_csv(input_file)
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return

    ingested_data = []
    
    print(f"Processing {len(df)} records...")
    for _, row in df.iterrows():
        # Flexible column mapping (adjust as needed)
        title = row.get('course_title', row.get('title', row.get('Title', 'Unknown Title')))
        url = row.get('url', row.get('link', row.get('Link', '')))
        
        # Description construction
        desc_cols = ['description', 'summary', 'headline', 'subject']
        description = ""
        for col in desc_cols:
            if col in row and pd.notnull(row[col]):
                description = str(row[col])
                break
        
        if not description:
            description = title # Fallback

        # Generate search URL if missing
        if not url or pd.isna(url):
             import urllib.parse
             encoded_title = urllib.parse.quote(str(title))
             url = f"https://www.google.com/search?q={encoded_title} {source_name} course"

        record = {
            "id": str(uuid.uuid4()),
            "title": str(title),
            "description": str(description),
            "url": str(url),
            "source": source_name,
            "quality_score": 0.5,
            "published_date": "",
            "content_type": "Course",
            "raw_metadata": row.to_dict()
        }
        ingested_data.append(record)

    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    print(f"Saving {len(ingested_data)} records to {output_file}...")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(ingested_data, f, indent=2)
    
    print(f"Ingestion complete. Output: {output_file}")
    print(f"NOTE: You must add '{output_filename}' to the SOURCES list in scripts/ingestion/process_corpus.py")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python scripts/ingestion/ingest_csv.py <path_to_csv> <source_name>")
    else:
        ingest_csv(sys.argv[1], sys.argv[2])
