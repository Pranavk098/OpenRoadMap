import json
import os
import re
from bs4 import BeautifulSoup

# Configuration
INPUT_DIR = os.path.join("data", "processed")
OUTPUT_FILE = os.path.join("data", "processed", "unified_corpus.json")

SOURCES = ["coursera_ingested.json", "edx_ingested.json", "feedspot_ingested.json", "youtube_ingested.json", "manual_ingested.json", "urls_ingested.json"]

def clean_text(text):
    if not text:
        return ""
    # Remove HTML tags
    soup = BeautifulSoup(text, "html.parser")
    text = soup.get_text(separator=" ")
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def process_corpus():
    unified_data = []
    seen_urls = set()
    
    print("Merging and processing corpus...")
    
    for filename in SOURCES:
        filepath = os.path.join(INPUT_DIR, filename)
        if not os.path.exists(filepath):
            print(f"Warning: {filename} not found. Skipping.")
            continue
            
        print(f"Processing {filename}...")
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        for record in data:
            # Deduplication by URL (if available)
            url = record.get('url', '')
            if url and url in seen_urls:
                continue
            if url:
                seen_urls.add(url)
                
            # Clean text fields
            record['title'] = clean_text(record.get('title', ''))
            record['description'] = clean_text(record.get('description', ''))
            
            # Basic validation
            if not record['title']:
                continue
                
            unified_data.append(record)

    print(f"Total unique records: {len(unified_data)}")
    
    print(f"Saving unified corpus to {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(unified_data, f, indent=2)
    
    print("Processing complete.")

if __name__ == "__main__":
    process_corpus()
