import feedparser
import os
import json
import uuid
from datetime import datetime

# Configuration
OUTPUT_FILE = os.path.join("data", "processed", "feedspot_ingested.json")

# List of RSS feeds to crawl (Example list, can be expanded)
RSS_FEEDS = [
    "https://feeds.feedburner.com/eLearningIndustry",
    "https://www.edutopia.org/rss.xml",
    "https://thelearningagencylab.com/feed/",
    # Add more educational feeds here
]

def ingest_feedspot():
    ingested_data = []
    
    print(f"Crawling {len(RSS_FEEDS)} RSS feeds...")
    
    for feed_url in RSS_FEEDS:
        print(f"Parsing {feed_url}...")
        try:
            feed = feedparser.parse(feed_url)
            
            for entry in feed.entries:
                post_id = str(uuid.uuid4())
                title = entry.get('title', 'No Title')
                link = entry.get('link', '')
                summary = entry.get('summary', entry.get('description', ''))
                published = entry.get('published', entry.get('updated', ''))
                
                # Basic cleaning of summary (remove HTML tags if needed, but we'll do that in preprocessing)
                
                record = {
                    "id": post_id,
                    "title": title,
                    "description": summary,
                    "url": link,
                    "source": "Feedspot",
                    "quality_score": 0.5, # Default score for blogs
                    "published_date": published,
                    "content_type": "Article",
                    "raw_metadata": {k: v for k, v in entry.items() if k in ['author', 'tags']}
                }
                ingested_data.append(record)
                
        except Exception as e:
            print(f"Failed to parse {feed_url}: {e}")

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    
    print(f"Saving {len(ingested_data)} records to {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(ingested_data, f, indent=2)
    
    print("Ingestion complete.")

if __name__ == "__main__":
    ingest_feedspot()
