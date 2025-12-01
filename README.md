# OpenRoadMap Backend

This is the backend service for OpenRoadMap, an AI-powered personalized learning roadmap generator.

## Project Structure

```text
DataAug/
├── src/                    # Source code
│   ├── main.py             # FastAPI Entry point
│   ├── roadmap_engine.py   # Orchestrator
│   ├── agents/             # AI Agents (Roadmap, Resource, Eval)
│   └── ...
├── scripts/                # Utility scripts
│   ├── ingestion/          # Data ingestion (Qdrant)
│   └── evaluation/         # Evaluation metrics & scripts
├── tests/                  # Integration tests
├── data/                   # Data storage
└── requirements.txt        # Python dependencies
```

## Setup

1.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

2.  **Environment Variables**:
    Create a `.env` file with:
    ```
    OPENAI_API_KEY=sk-...
    QDRANT_URL=http://localhost:6333
    ```

3.  **Run Qdrant**:
    ```bash
    docker-compose up -d
    ```

## Usage

**Start the API**:
```bash
uvicorn src.main:app --reload
```

**Generate a Roadmap**:
POST `http://localhost:8000/generate-roadmap`
```json
{
  "goal": "Learn Python"
}
```

## Evaluation

Run the evaluation suite:
```bash
python scripts/evaluation/run_evaluation.py
```
