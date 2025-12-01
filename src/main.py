from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from .models import RoadmapRequest, RoadmapResponse
from .roadmap_engine import generate_roadmap
import uvicorn

app = FastAPI(title="OpenRoadMap API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/generate-roadmap", response_model=RoadmapResponse)
async def create_roadmap(request: RoadmapRequest):
    try:
        roadmap = generate_roadmap(request.goal)
        return roadmap
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)
