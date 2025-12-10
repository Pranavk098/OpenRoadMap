# 🚀 OpenRoadMap

**OpenRoadMap** is an AI-powered platform that generates personalized learning roadmaps for any skill. It combines the power of Large Language Models (LLMs) with a curated database of high-quality educational resources to guide learners from beginner to expert.

![OpenRoadMap Landing Page](https://github.com/Pranavk098/OpenRoadMap/assets/placeholder/landing.png)

## ✨ Features

*   **AI-Generated Roadmaps**: Enter any topic (e.g., "Machine Learning", "Sourdough Baking") and get a structured, step-by-step learning path.
*   **Smart Resource Retrieval**: Each step in the roadmap is populated with relevant courses, videos, and articles from top platforms (Coursera, edX, YouTube, etc.).
*   **Interactive UI**: A modern, responsive interface built with React and React Flow for visualizing your learning journey.
*   **Quality Evaluation**: Built-in evaluation metrics (Recall, NDCG, BERTScore) to ensure the quality and relevance of generated roadmaps.
*   **Extensible Database**: Easily expand the resource database by ingesting data from CSVs or scraping URLs.

## 🛠️ Tech Stack

### Frontend
*   **React**: UI library
*   **Vite**: Build tool
*   **Tailwind CSS**: Styling
*   **React Flow**: Interactive node-based graphs
*   **Lucide React**: Icons

### Backend
*   **FastAPI**: High-performance Python web framework
*   **Qdrant**: Vector database for semantic search
*   **Sentence Transformers**: Text embeddings (`all-MiniLM-L6-v2`)
*   **OpenAI API**: LLM for roadmap generation (`gpt-4o` or `gpt-3.5-turbo`)
*   **DuckDuckGo Search**: Fallback for real-time web resources

## 🚀 Getting Started

### Prerequisites
*   Node.js (v16+)
*   Python (v3.9+)
*   Docker (for Qdrant)
*   Git
*   check if the .env file is present as it contains the API Keys.

### 1. Clone the Repository
```bash
git clone https://github.com/Pranavk098/OpenRoadMap.git
cd OpenRoadMap
```

### 2. Backend Setup
1.  **Create a virtual environment**:
    ```bash
    python -m venv data_env
    source data_env/bin/activate  # On Windows: data_env\Scripts\activate
    ```
2.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```
3.  **Set up environment variables**:
    Create a `.env` file in the root directory:
    ```env
    OPENAI_API_KEY=your_openai_api_key_here
    QDRANT_URL=http://localhost:6333
    ```
4.  **Start Qdrant**:
    ```bash
    docker-compose up -d
    ```
5.  **Ingest Data** (Optional but recommended):
    ```bash
    # Ingest default datasets
    python scripts/ingestion/process_corpus.py
    python scripts/ingestion/vectorize_corpus.py
    ```
6.  **Run the Server**:
    ```bash
    uvicorn src.main:app --reload
    ```

### 3. Frontend Setup
1.  **Navigate to frontend directory**:
    ```bash
    cd frontend
    ```
2.  **Install dependencies**:
    ```bash
    npm install
    ```
3.  **Run the development server**:
    ```bash
    npm run dev
    ```
4.  **Open in Browser**:
    Visit `http://localhost:5173`

## 📊 Evaluation

OpenRoadMap includes a robust evaluation suite to measure the quality of retrieval and generation.

```bash
# Run the full evaluation pipeline
python scripts/evaluation/run_evaluation.py
```

Metrics tracked:
*   **Retrieval**: Recall@K, NDCG@K
*   **Generation**: BERTScore, ROUGE-L

---
*Built by Pranav Koduru, Nikhil Akula, Vishnu Gurram*
