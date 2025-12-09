from duckduckgo_search import DDGS
try:
    from src.dependencies import get_qdrant_client, get_openai_client, COLLECTION_NAME
    from src.models import Resource
except ImportError:
    from ..dependencies import get_qdrant_client, get_openai_client, COLLECTION_NAME
    from ..models import Resource

class ResourceAgent:
    def __init__(self):
        self.qdrant_client = get_qdrant_client()
        self.openai_client = get_openai_client()
        # Lazy load model
        self._model = None
        self.ddgs = DDGS()

    @property
    def model(self):
        if self._model is None:
            from fastembed import TextEmbedding
            # FastEmbed uses "BAAI/bge-small-en-v1.5" by default which is better, 
            # and it is definitely supported.
            self._model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
        return self._model

    def expand_query(self, original_query: str) -> list[str]:
        """
        Expands the user query into multiple variations using an LLM.
        """
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that expands search queries. Generate 3 distinct, specific search queries based on the user's input. Return them as a comma-separated list. Do not include numbering or quotes."},
                    {"role": "user", "content": f"Expand this search query: {original_query}"}
                ],
                max_tokens=50,
                temperature=0.7
            )
            content = response.choices[0].message.content.strip()
            # Split by comma and clean up
            variations = [q.strip() for q in content.split(',')]
            # Add original query to the list
            variations.append(original_query)
            # Deduplicate
            return list(set(variations))
        except Exception as e:
            print(f"Query expansion failed: {e}")
            return [original_query]

    def find_resources(self, query: str, limit: int = 3) -> list[Resource]:
        """
        Finds resources using Qdrant (local) and falls back to Web Search if needed.
        Uses Query Expansion to improve recall.
        """
        resources = []
        seen_urls = set()
        
        # 1. Expand Query
        print(f"Expanding query: '{query}'...")
        expanded_queries = self.expand_query(query)
        print(f"Expanded queries: {expanded_queries}")

        # 2. Search Qdrant for ALL queries
        try:
            # Embed all queries at once
            query_vectors = list(self.model.embed(expanded_queries))
            
            # Perform batch search (conceptually, Qdrant doesn't have a simple "OR" for vectors, 
            # so we search for each and combine)
            all_points = []
            for vec in query_vectors:
                search_results = self.qdrant_client.query_points(
                    collection_name=COLLECTION_NAME,
                    query=vec.tolist(),
                    limit=limit,
                    with_payload=True,
                    score_threshold=0.4
                ).points
                all_points.extend(search_results)
            
            # Deduplicate by ID and sort by score
            unique_points = {}
            for point in all_points:
                if point.id not in unique_points:
                    unique_points[point.id] = point
                else:
                    # Keep the one with higher score if needed, or just first found
                    if point.score > unique_points[point.id].score:
                        unique_points[point.id] = point
            
            # Sort by score descending
            sorted_points = sorted(unique_points.values(), key=lambda x: x.score, reverse=True)
            
            for point in sorted_points:
                payload = point.payload
                url = payload.get("url", "#")
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                
                resources.append(Resource(
                    id=str(point.id),
                    title=payload.get("title", "Unknown"),
                    url=url,
                    description=payload.get("description", "")[:200] + "...",
                    type=payload.get("content_type", "resource")
                ))
        except Exception as e:
            print(f"Qdrant search failed: {e}")

        # 3. Fallback/Augment with Web Search if we don't have enough results
        if len(resources) < limit:
            print(f"Not enough local resources for '{query}'. Searching web...")
            try:
                # Use the original query for web search to avoid spamming DDG
                web_results = self.ddgs.text(f"{query} tutorial course", max_results=limit - len(resources))
                if not web_results:
                    # Try broader search
                    print(f"Broadening search for '{query}'...")
                    web_results = self.ddgs.text(query, max_results=limit - len(resources))

                if web_results:
                    for res in web_results:
                        url = res.get("href", "")
                        if url in seen_urls:
                            continue
                        seen_urls.add(url)
                        
                        resources.append(Resource(
                            title=res.get("title", ""),
                            url=url,
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


