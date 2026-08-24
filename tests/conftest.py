import os

# Several modules under test build module-level singletons at import time
# (e.g. src.roadmap_engine's `roadmap_agent = RoadmapAgent()`) that require
# OPENAI_API_KEY to exist just to construct the client - no real key value
# is ever used since tests mock the client itself. Set this before any test
# module imports anything under src/.
os.environ.setdefault("OPENAI_API_KEY", "test-key-for-tests")
