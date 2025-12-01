import pandas as pd
import os
import json
import uuid

# Configuration
INPUT_FILE = os.path.join("data", "raw", "coursera_courses.csv")
OUTPUT_FILE = os.path.join("data", "processed", "coursera_ingested.json")

def ingest_coursera():
    if not os.path.exists(INPUT_FILE):
        print(f"Error: Input file not found at {INPUT_FILE}")
        print("Please download the Coursera dataset and place it in data/raw/")
        return

    print(f"Loading data from {INPUT_FILE}...")
    try:
        df = pd.read_csv(INPUT_FILE)
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return

    # Normalize columns (adjust based on actual CSV headers)
    # Expected headers from Kaggle dataset: course_title, course_organization, course_rating, etc.
    # We will map them to our unified schema.
    
    ingested_data = []
    
    print(f"Processing {len(df)} records...")
    for _, row in df.iterrows():
        # Generate a unique ID
        course_id = str(uuid.uuid4())
        
        # Extract fields with fallbacks
        title = row.get('course_title', row.get('Title', 'Unknown Title'))
        org = row.get('course_organization', row.get('Organization', ''))
        rating = row.get('course_rating', row.get('Rating', 0))
        difficulty = row.get('course_difficulty', row.get('Difficulty', ''))
        
        # Construct description from available info
        description = f"Offered by {org}. Difficulty: {difficulty}. Rating: {rating}."
        
        # Construct search URL if direct URL is missing
        import urllib.parse
        encoded_title = urllib.parse.quote(title)
        url = f"https://www.coursera.org/search?query={encoded_title}"

        # Create unified record
        record = {
            "id": course_id,
            "title": title,
            "description": description,
            "url": url,
            "source": "Coursera",
            "quality_score": float(rating) if pd.notnull(rating) else 0.0,
            "published_date": "", # Not usually available in this dataset
            "content_type": "Course",
            "raw_metadata": row.to_dict()
        }
        ingested_data.append(record)

    # Ensure output directory exists
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    
    print(f"Saving {len(ingested_data)} records to {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(ingested_data, f, indent=2)
    
    print("Ingestion complete.")

if __name__ == "__main__":
    ingest_coursera()
