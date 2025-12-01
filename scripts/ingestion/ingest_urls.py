import requests
from bs4 import BeautifulSoup
import json
import os
import uuid

# Configuration
INPUT_FILE = os.path.join("data", "manual", "urls_to_ingest.txt")
OUTPUT_FILE = os.path.join("data", "processed", "urls_ingested.json")

def ingest_urls():
    if not os.path.exists(INPUT_FILE):
        print(f"Error: Input file not found at {INPUT_FILE}")
        print("Please create data/manual/urls_to_ingest.txt with one URL per line.")
        return

    print(f"Reading URLs from {INPUT_FILE}...")
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        urls = [line.strip() for line in f if line.strip()]

    ingested_data = []
    
    print(f"Processing {len(urls)} URLs...")
    for url in urls:
        try:
            print(f"Fetching {url}...")
            response = requests.get(url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract metadata
            title = soup.title.string.strip() if soup.title else url
            
            description = ""
            meta_desc = soup.find('meta', attrs={'name': 'description'}) or soup.find('meta', attrs={'property': 'og:description'})
            if meta_desc:
                description = meta_desc.get('content', '').strip()
            
            if not description:
                # Fallback to first paragraph
                p = soup.find('p')
                if p:
                    description = p.get_text().strip()[:200] + "..."
            
            resource_id = str(uuid.uuid4())
            
            record = {
                "id": resource_id,
                "title": title,
                "description": description,
                "url": url,
                "source": "Web Scraper",
                "quality_score": 0.8, # Default score for manual URLs
                "published_date": "",
                "content_type": "Web Resource",
                "raw_metadata": {"url": url}
            }
            ingested_data.append(record)
            
        except Exception as e:
            print(f"Failed to process {url}: {e}")

    # Ensure output directory exists
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    
    print(f"Saving {len(ingested_data)} records to {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(ingested_data, f, indent=2)
    
    print("Ingestion complete.")

if __name__ == "__main__":
    ingest_urls()
