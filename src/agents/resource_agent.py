from duckduckgo_search import DDGS
from ..dependencies import get_qdrant_client, COLLECTION_NAME
from ..models import Resource

class ResourceAgent:
    def __init__(self):
        self.qdrant_client = get_qdrant_client()
        # Lazy load model
        self._model = None
        self.ddgs = DDGS()

    @property
    def model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer("all-MiniLM-L6-v2")
        return self._model

    def find_resources(self, query: str, limit: int = 3) -> list[Resource]:
        """
        Finds resources using Qdrant (local) and falls back to Web Search if needed.
        """
        resources = []
        
        # 1. Search Qdrant
        try:
            query_vector = self.model.encode(query, convert_to_numpy=True).tolist()
            search_results = self.qdrant_client.query_points(
                collection_name=COLLECTION_NAME,
                query=query_vector,
                limit=limit,
                with_payload=True,
                score_threshold=0.4 # Only return relevant results
            ).points
            
            for point in search_results:
                payload = point.payload
                resources.append(Resource(
                    id=str(point.id),
                    title=payload.get("title", "Unknown"),
                    url=payload.get("url", "#"),
                    description=payload.get("description", "")[:200] + "...",
                    type=payload.get("content_type", "resource")
                ))
        except Exception as e:
            print(f"Qdrant search failed: {e}")

        # 2. Fallback/Augment with Web Search if we don't have enough results
        if len(resources) < limit:
            print(f"Not enough local resources for '{query}'. Searching web...")
            try:
                web_results = self.ddgs.text(f"{query} tutorial course", max_results=limit - len(resources))
                if not web_results:
                    # Try broader search
                    print(f"Broadening search for '{query}'...")
                    web_results = self.ddgs.text(query, max_results=limit - len(resources))

                if web_results:
                    for res in web_results:
                        resources.append(Resource(
                            title=res.get("title", ""),
                            url=res.get("href", ""),
                            description=res.get("body", "")[:200] + "...",
                            type="Web Resource"
                        ))
                else:
                    # Last resort: Google Search Link
                    import urllib.parse
                    encoded_query = urllib.parse.quote(query)
                    resources.append(Resource(
                        title=f"Search Google for '{query}'",
                        url=f"https://www.google.com/search?q={encoded_query}",
                        description="No direct resources found. Click to search on Google.",
                        type="Search Link"
                    ))
            except Exception as e:
                print(f"Web search failed: {e}")
                # Last resort on error
                import urllib.parse
                encoded_query = urllib.parse.quote(query)
                resources.append(Resource(
                    title=f"Search Google for '{query}'",
                    url=f"https://www.google.com/search?q={encoded_query}",
                    description="Search failed. Click to search on Google.",
                    type="Search Link"
                ))
                
        return resources[:limit]


