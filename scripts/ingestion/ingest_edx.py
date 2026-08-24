import pandas as pd
import os
import json
import uuid
import urllib.parse

# Configuration
INPUT_FILE = os.path.join("data", "raw", "edx_courses.csv")
OUTPUT_FILE = os.path.join("data", "processed", "edx_ingested.json")

TITLE_COLUMNS = ('title', 'Title')


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

        course_id = str(uuid.uuid4())

        # Extract fields based on common edX dataset schemas
        summary = row.get('summary', row.get('Summary', ''))
        description_full = row.get('course_description', '')

        # Use summary if description is empty, or combine them
        description = summary if summary else description_full
        if not description:
            description = title # Fallback

        url = row.get('course_url', row.get('Link', ''))
        if not url or pd.isna(url):
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

    if skipped:
        print(f"Skipped {skipped} of {len(df)} rows due to missing/duplicate titles.")

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

    print(f"Saving {len(ingested_data)} records to {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(ingested_data, f, indent=2)

    print("Ingestion complete.")

if __name__ == "__main__":
    ingest_edx()
