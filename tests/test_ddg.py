from duckduckgo_search import DDGS

def test_ddg():
    print("Testing DuckDuckGo Search...")
    backends = ['api', 'html', 'lite']
    for backend in backends:
        print(f"\nTesting backend: {backend}")
        try:
            ddgs = DDGS()
            results = ddgs.text("Advanced Pottery Glazing tutorial", max_results=3, backend=backend)
            print(f"Found {len(results)} results.")
            for res in results:
                print(f"- {res.get('title')} ({res.get('href')})")
            if results:
                print("Success!")
                break
        except Exception as e:
            print(f"Error with {backend}: {e}")

if __name__ == "__main__":
    test_ddg()
