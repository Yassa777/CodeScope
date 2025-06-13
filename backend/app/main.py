from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = FastAPI(
    title="Halos API",
    description="AI-powered code knowledge graph API",
    version="0.1.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Frontend dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class RepoRequest(BaseModel):
    url: str
    branch: Optional[str] = "main"

class AnalysisStatus(BaseModel):
    status: str
    progress: float
    message: Optional[str] = None

@app.get("/")
async def root():
    return {"message": "Welcome to Halos API"}

@app.post("/api/repo")
async def analyze_repository(repo: RepoRequest) -> Dict[str, Any]:
    """
    Start analysis of a new repository.
    Returns a job ID that can be used to track progress.
    """
    try:
        # TODO: Implement repository cloning and analysis
        return {
            "job_id": "temp_job_id",
            "status": "queued",
            "message": "Repository analysis started"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/repo/{repo_id}/status")
async def get_analysis_status(repo_id: str) -> AnalysisStatus:
    """
    Get the current status of a repository analysis.
    """
    # TODO: Implement status checking
    return AnalysisStatus(
        status="processing",
        progress=0.0,
        message="Analysis in progress"
    )

@app.get("/api/repo/{repo_id}/graph")
async def get_graph(repo_id: str, level: int = 1) -> Dict[str, Any]:
    """
    Get the graph data at the specified semantic zoom level.
    Level 1: Repository view (folders)
    Level 2: File view
    Level 3: Code block view (functions/classes)
    """
    if level not in [1, 2, 3]:
        raise HTTPException(status_code=400, detail="Invalid level. Must be 1, 2, or 3.")
    
    # TODO: Implement graph data retrieval
    return {
        "nodes": [],
        "edges": [],
        "level": level
    }

@app.get("/api/repo/{repo_id}/details")
async def get_node_details(repo_id: str, node_id: str) -> Dict[str, Any]:
    """
    Get detailed information about a specific node (file, function, or class).
    """
    # TODO: Implement node details retrieval
    return {
        "id": node_id,
        "type": "unknown",
        "content": "",
        "summary": "",
        "metadata": {}
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 