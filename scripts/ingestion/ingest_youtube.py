import os
import json
import uuid
from googleapiclient.discovery import build
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

API_KEY = os.getenv("YOUTUBE_API_KEY")
OUTPUT_FILE = os.path.join("data", "processed", "youtube_ingested.json")

# Search terms to build the corpus
SEARCH_TERMS = [
    "machine learning course",
    "python programming tutorial",
    "data science roadmap",
    "web development full course",
    "artificial intelligence basics"
]

def ingest_youtube():
    if not API_KEY:
        print("Error: YOUTUBE_API_KEY not found in .env file.")
        return

    youtube = build('youtube', 'v3', developerKey=API_KEY)
    ingested_data = []
    
    print(f"Searching YouTube for {len(SEARCH_TERMS)} terms...")
    
    for term in SEARCH_TERMS:
        print(f"Searching for: {term}")
        try:
            request = youtube.search().list(
                part="snippet",
                maxResults=50,
                q=term,
                type="video",
                relevanceLanguage="en"
            )
            response = request.execute()
            
            for item in response.get('items', []):
                video_id = item['id']['videoId']
                snippet = item['snippet']
                
                record = {
                    "id": str(uuid.uuid4()),
                    "title": snippet['title'],
                    "description": snippet['description'],
                    "url": f"https://www.youtube.com/watch?v={video_id}",
                    "source": "YouTube",
                    "quality_score": 0.8, # Video content is high value
                    "published_date": snippet['publishedAt'],
                    "content_type": "Video",
                    "raw_metadata": {
                        "channelTitle": snippet['channelTitle'],
                        "videoId": video_id
                    }
                }
                ingested_data.append(record)
                
        except Exception as e:
            print(f"Error searching for {term}: {e}")

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    
    print(f"Saving {len(ingested_data)} records to {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(ingested_data, f, indent=2)
    
    print("Ingestion complete.")

if __name__ == "__main__":
    ingest_youtube()
