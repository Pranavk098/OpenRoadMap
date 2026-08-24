import json
import os
import urllib.parse
import uuid

import pandas as pd

# Configuration
INPUT_FILE = os.path.join("data", "raw", "coursera_courses.csv")
OUTPUT_FILE = os.path.join("data", "processed", "coursera_ingested.json")

TITLE_COLUMNS = ('course_title', 'Title', 'title')


def resolve_title(row):
    """
    Try known column name variants for the title field.
    Returns the stripped title string, or None if none of the known
    columns are present, or the value is missing (NaN) / empty after
    stripping.
    """
    for col in TITLE_COLUMNS:
        if col in row and pd.notnull(row[col]):
            candidate = str(row[col]).strip()
            if candidate:
                return candidate
    return None


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

    ingested_data = []
    seen_titles = set()
    skipped = 0

    print(f"Processing {len(df)} records...")
    for idx, row in df.iterrows():
        title = resolve_title(row)

        if title is None:
            print(f"Warning: skipping row {idx} - no usable title found. Columns present: {list(df.columns)}")
            skipped += 1
            continue

        if title in seen_titles:
            print(f"Warning: skipping row {idx} - duplicate title '{title}'.")
            skipped += 1
            continue
        seen_titles.add(title)

        # Generate a unique ID
        course_id = str(uuid.uuid4())

        # Extract remaining fields with fallbacks
        org = row.get('course_organization', row.get('Organization', ''))
        rating = row.get('course_rating', row.get('Rating', 0))
        difficulty = row.get('course_difficulty', row.get('Difficulty', ''))

        # Construct description from available info
        description = f"Offered by {org}. Difficulty: {difficulty}. Rating: {rating}."

        # Construct search URL if direct URL is missing
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

    if skipped:
        print(f"Skipped {skipped} of {len(df)} rows due to missing/duplicate titles.")

    # Ensure output directory exists
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

    print(f"Saving {len(ingested_data)} records to {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(ingested_data, f, indent=2)

    print("Ingestion complete.")

if __name__ == "__main__":
    ingest_coursera()
