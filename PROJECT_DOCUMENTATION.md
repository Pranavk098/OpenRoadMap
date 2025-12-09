# 📘 OpenRoadMap: Comprehensive Project Documentation

## 1. Project Overview
**OpenRoadMap** is an intelligent, AI-powered educational platform designed to generate personalized learning paths for any given topic. Unlike static roadmap websites, OpenRoadMap uses Large Language Models (LLMs) to dynamically structure a curriculum and a Vector Database to populate that curriculum with high-quality, relevant resources (courses, videos, articles) from across the web.

### Core Objectives
1.  **Dynamic Generation**: Create unique roadmaps for niche topics (e.g., "Sourdough Baking", "Quantum Computing") where standard guides don't exist.
2.  **Resource Aggregation**: Centralize learning materials from Coursera, edX, YouTube, and the open web.
3.  **Quality Assurance**: Ensure resources are relevant and accessible.

---

## 2. System Architecture

The application follows a modern, decoupled architecture:

### A. Frontend (The "Face")
*   **Framework**: React (Vite)
*   **Visualization**: React Flow (for interactive node-based graphs).
*   **Styling**: Tailwind CSS (Yellow/Black "Construction" theme).
*   **Key Components**:
    *   `Roadmap.jsx`: The core canvas where the learning graph is rendered.
    *   `Sidebar.jsx`: Displays resource details when a node is clicked.
    *   `Landing.jsx`: Entry point with search and popular tags.

### B. Backend (The "Brain")
*   **Framework**: FastAPI (Python).
*   **Orchestrator**: `roadmap_engine.py` manages the flow between agents.
*   **Agents**:
    *   **RoadmapAgent**: Uses OpenAI (GPT-4o/3.5) to generate the JSON structure of the roadmap (nodes, edges, prerequisites).
    *   **ResourceAgent**: Queries the Vector Database to find content for each node. Falls back to DuckDuckGo web search if the database is empty or lacks coverage.
    *   **EvaluationAgent**: Scores the generated roadmap using metrics like BERTScore and ROUGE-L.

### C. Database (The "Memory")
*   **Vector Database**: Qdrant.
*   **Role**: Stores embeddings (mathematical representations) of educational content.
*   **Deployment**: Docker (Local) / Qdrant Cloud (Production).

---

## 3. Vector Database & Retrieval Strategy

The heart of OpenRoadMap's resource recommendation is its Vector Database.

### A. The Challenge
Traditional keyword search fails when terms don't match exactly (e.g., searching for "ML" vs "Machine Learning"). Vector search solves this by understanding *meaning*.

### B. Implementation Details
*   **Embedding Model**: `all-MiniLM-L6-v2` (via `sentence-transformers` / `fastembed`).
    *   This model converts text into a 384-dimensional vector.
    *   It is lightweight and optimized for semantic similarity.
*   **Ingestion Pipeline**:
    *   **Sources**: CSV datasets (Coursera, edX), Web Scraping (`ingest_urls.py`), Manual curation.
    *   **Process**: Raw Data -> Clean Text -> Vectorize -> Qdrant Index.

### C. Experiments & Optimization
We conducted rigorous experiments to find the best retrieval strategy and validate the roadmap generation quality.

#### 1. Retrieval Strategy Experiments (Resource Agent)
We tested three strategies using a "Known-Item Search" dataset (N=50 queries).

*   **Experiment 1: Baseline (Semantic Search)**
    *   **Method**: Pure Cosine Similarity search in Qdrant.
    *   **Result**: Recall@5: **0.58**, NDCG@5: **0.58**.
    *   **Verdict**: Strong baseline. Fast and effective for exact topic matches.

*   **Experiment 2: Multi-Factor Re-ranking**
    *   **Method**: Weighted score = $0.35 \times Semantic + 0.25 \times Quality + 0.15 \times Recency$.
    *   **Hypothesis**: Boost "high authority" domains (Coursera) over "low authority" ones.
    *   **Result**: Recall@5: 0.56, NDCG@5: 0.54.
    *   **Analysis**: The score dropped because our ground truth dataset contained specific YouTube videos. The re-ranker "punished" these correct answers in favor of Coursera courses. While the metric dropped, the *user experience* likely improved by surfacing higher-quality content.

*   **Experiment 3: Cross-Encoder Re-ranking**
    *   **Method**: Two-stage retrieval. (1) Get top 20 from Qdrant. (2) Re-rank using a Cross-Encoder (`ms-marco-MiniLM-L-6-v2`).
    *   **Result**: Recall@5: 0.58, NDCG@5: 0.57.
    *   **Analysis**: Comparable to baseline but significantly slower (200ms vs 10ms).
    *   **Decision**: For the production MVP, we stuck with the **Baseline** for its speed/performance balance.

#### 2. Roadmap Structure Experiments (Roadmap Agent)
We evaluated the quality of the AI-generated roadmap structures (the sequence of topics) using NLP metrics.

*   **Metric 1: ROUGE-L (Lexical Overlap)**
    *   **What it measures**: The longest common subsequence of words between the generated roadmap topics and a human-curated syllabus.
    *   **Why we use it**: It tells us if the AI is using the "correct terminology" (e.g., "React Hooks" vs "React Functions").
    *   **Result**: High overlap indicates the AI follows standard curriculum conventions.

*   **Metric 2: BERTScore (Semantic Similarity)**
    *   **What it measures**: The similarity in *meaning* between the generated topics and the ground truth, even if the words are different.
    *   **Why we use it**: If the AI says "Data Cleaning" and the syllabus says "Data Preprocessing", ROUGE would fail, but BERTScore understands they are the same thing.
    *   **Result**: Consistently high scores (>0.85), proving the AI understands the *concepts* of the domain, not just the keywords.

---

## 4. Deep Dive: Vector Database & Search Logic

The heart of OpenRoadMap's resource recommendation is its Vector Database.

### A. Why Qdrant?
We chose **Qdrant** for three reasons:
1.  **HNSW Indexing**: It uses Hierarchical Navigable Small World graphs, which allows for approximate nearest neighbor search in logarithmic time ($O(\log N)$). This means search remains fast even as we add millions of resources.
2.  **Payload Filtering**: We can filter results by metadata (e.g., `content_type="video"`) *while* searching, which is crucial for specific user queries.
3.  **Rust Core**: It is extremely memory-efficient, which allowed us to run it on the free tier of Render/Qdrant Cloud.

### B. The Search Algorithm (Cosine Similarity)
When a user asks for "Machine Learning", we don't look for the words "Machine", "Learning".
1.  **Vectorization**: We convert the query into a 384-dimensional vector using `all-MiniLM-L6-v2`.
2.  **Similarity Calculation**: We calculate the cosine of the angle between the query vector and every resource vector in the database.
    $$ \text{similarity} = \cos(\theta) = \frac{\mathbf{A} \cdot \mathbf{B}}{\|\mathbf{A}\| \|\mathbf{B}\|} $$
3.  **Ranking**: Resources with the smallest angle (highest cosine similarity) are returned. This captures *conceptual* closeness.

### C. The Fallback Mechanism (DuckDuckGo vs Google)
What happens if the Vector Database is empty or returns no relevant results? We have a robust two-stage fallback:

1.  **Stage 1: DuckDuckGo Search (Programmatic)**
    *   We use the `duckduckgo-search` library to perform a real, programmatic web search (e.g., `query + " tutorial course"`).
    *   We parse the results and present them as "Web Resources" in the UI.
    *   **Why DDG?**: It has a free, permissive API that doesn't require a credit card, unlike the Google Custom Search API.

2.  **Stage 2: Google Search Link (Last Resort)**
    *   If DuckDuckGo fails (e.g., rate limiting) or returns zero results, we generate a **direct hyperlink** to a Google Search.
    *   **Difference**: We do *not* scrape Google. We simply give the user a link that says "Search Google for 'X'". When clicked, it opens a new tab with the Google search results. This ensures the user is never left with a dead end.

---

## 5. Development Journey

### Phase 1: Foundation
*   We started by fixing broken ingestion scripts that were failing to populate Qdrant.
*   We implemented `search_test.py` to verify that the database was actually returning results.

### Phase 2: The Multi-Agent Refactor
*   Originally, the code was a monolithic script.
*   We refactored it into `src/agents/`, creating specialized agents. This allows us to upgrade the "Resource Finder" without breaking the "Roadmap Generator".

### Phase 3: Frontend Polish
*   Moved from a basic HTML output to a React application.
*   Implemented the "Node-Edge" visualization using React Flow.
*   **Key Challenge**: Handling mobile responsiveness. We discovered that `localhost` calls failed on mobile devices, leading us to implement environment variable configuration (`VITE_API_URL`).

### Phase 4: Deployment & Optimization (The "OOM" Saga)
*   **The Problem**: When deploying to Render (Free Tier), the application kept crashing with "Out of Memory" (OOM) errors.
*   **The Investigation**: We found that `torch` and `sentence-transformers` were consuming >500MB of RAM just to load.
*   **The Solution**:
    1.  **Lazy Loading**: We refactored `ResourceAgent` to only load the model when a request comes in, not at startup.
    2.  **FastEmbed**: We replaced the heavy PyTorch dependency with `fastembed`, a lightweight ONNX-based library. This reduced memory usage by ~50%.
    3.  **Build Script**: We created a custom `build.sh` to force Render to use a modern Python version (3.11) to support these new tools.

---

## 5. Future Roadmap

1.  **User Accounts**: Allow users to save their roadmaps.
2.  **Community Features**: "Upvote" resources to improve the ranking algorithm (Reinforcement Learning from Human Feedback).
3.  **Cross-Encoder V2**: Optimize the re-ranker to run on a separate microservice for better performance.

---
*Documentation generated by OpenRoadMap AI Assistant*
