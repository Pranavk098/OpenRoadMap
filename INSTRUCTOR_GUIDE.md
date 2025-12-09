# OpenRoadMap - Instructor Guide

Welcome to the **OpenRoadMap** project! This guide will help you set up and run the application locally for evaluation.

## 📋 Prerequisites

Ensure you have the following installed on your system:
*   **Python 3.11+**
*   **Node.js 16+** & **npm**
*   **Git**

## 🚀 Setup Instructions

### 1. Clone the Repository
```bash
git clone <repository_url>
cd OpenRoadMap
```

### 2. Backend Setup
The backend is built with **FastAPI** and uses **Qdrant** (Vector DB) and **FastEmbed** (Embeddings).

1.  **Create a Virtual Environment** (Optional but recommended):
    ```bash
    python -m venv venv
    # Windows
    .\venv\Scripts\activate
    # Mac/Linux
    source venv/bin/activate
    ```

2.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

3.  **Environment Configuration**:
    *   Create a `.env` file in the root directory.
    *   Add your OpenAI API Key (required for the Agentic features):
        ```env
        OPENAI_API_KEY=sk-your-key-here
        QDRANT_URL=:memory:  # Use in-memory Qdrant for local testing, or a cloud URL
        ```
    *   *Note: If you want to use Qdrant Cloud, provide `QDRANT_URL` and `QDRANT_API_KEY`.*

### 3. Frontend Setup
The frontend is built with **React** and **Vite**.

1.  **Navigate to Frontend Directory**:
    ```bash
    cd frontend
    ```

2.  **Install Dependencies**:
    ```bash
    npm install
    ```

3.  **Start the Frontend**:
    ```bash
    npm run dev
    ```
    *   The UI will run at `http://localhost:5173`.

## 🏃‍♂️ Execution Guide

### Step 1: Ingest Data (The "Brain")
Before running the app, you need to populate the vector database with learning resources.

**From the root directory:**
```bash
python scripts/ingestion/vectorize_corpus.py
```
*   *This will download the embedding model (`BAAI/bge-small-en-v1.5`) and index the data.*

### Step 2: Start the Backend API
Open a new terminal in the root directory:
```bash
uvicorn src.main:app --reload
```
*   The API will run at `http://localhost:8000`.
*   Swagger Docs: `http://localhost:8000/docs`

### Step 3: Use the Application
1.  Open `http://localhost:5173` in your browser.
2.  Enter a skill (e.g., "React", "Python", "Machine Learning").
3.  The system will:
    *   Generate a structured roadmap (using OpenAI).
    *   Retrieve relevant resources for each topic (using Qdrant + Query Expansion).

## 🧪 Verification & Evaluation (The Logic Check)

To verify the core logic (Roadmap Generation + Resource Retrieval + Query Expansion) without running the full frontend:

1.  **Run the Generator Script**:
    ```bash
    python scripts/generate_roadmap.py "Data Science"
    ```

2.  **Check the Output**:
    *   **Console**: You will see the roadmap stages printed directly to the terminal, followed by the **Resource Links** found for each stage.
    *   **JSON File**: A file named `roadmap_output.json` is created with the full structured data.

    *Verify that:*
    *   The roadmap steps are logical for "Data Science".
    *   The resource links are relevant and point to valid URLs (Coursera, EdX, etc.).
    *   The system found resources even if the exact topic name wasn't in the database (proving Query Expansion worked).

## 📂 Project Structure
*   `src/`: Backend source code (Agents, API, Models).
*   `frontend/`: React frontend code.
*   `scripts/`: Utility scripts.
    *   `ingestion/`: Data processing and vectorization.
    *   `evaluation/`: Benchmarking and synthetic data generation.
    *   `setup/`: Initial data setup.
*   `data/`: Data storage (Corpus, Manual Roadmaps).

---
*Created by Pranav Koduru*
