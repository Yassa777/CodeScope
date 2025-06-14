from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
from typing import Dict, Any, Optional
from pathlib import Path
import asyncio
import os
import shutil
from .repo_analyzer import RepoAnalyzer
from .graph_builder import GraphBuilder
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

# Initialize analyzer and graph builder
repo_analyzer = RepoAnalyzer()
graph_builder = GraphBuilder()

# Store analysis jobs
analysis_jobs: Dict[str, Dict[str, Any]] = {}

class RepoRequest(BaseModel):
    url: HttpUrl
    branch: Optional[str] = "main"

class AnalysisStatus(BaseModel):
    status: str
    progress: float
    message: Optional[str] = None
    current_file: Optional[str] = None

@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Welcome to Halos API"}

@app.post("/api/repo")
async def analyze_repo(request: RepoRequest, background_tasks: BackgroundTasks):
    """Start repository analysis."""
    try:
        repo_id = repo_analyzer.get_repo_id(str(request.url))
        
        # Check if analysis is already in progress
        if repo_id in analysis_jobs and analysis_jobs[repo_id]["status"] == "processing":
            return {"id": repo_id, "status": "processing"}
        
        # Initialize analysis status
        analysis_jobs[repo_id] = {
            "status": "processing",
            "progress": 0,
            "error": None
        }
        
        # Start analysis in background
        background_tasks.add_task(process_repo, repo_id, str(request.url), request.branch)
        
        return {"id": repo_id, "status": "processing"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def process_repo(repo_id: str, url: str, branch: str):
    """Process repository in background."""
    try:
        # Clone repository
        repo_path = await repo_analyzer.clone_repository(url, branch)
        if not repo_path:
            raise Exception("Failed to clone repository")
        
        # Get repository structure
        structure = repo_analyzer.analyze_repository(repo_path)
        if not structure:
            raise Exception("Failed to analyze repository")
        
        # Build graph
        graph = graph_builder.build_repository_graph(structure)
        
        # Process files
        for file_info in structure["files"]:
            file_path = repo_path / file_info["path"]
            if file_path.exists():
                graph_builder.process_file(file_path, file_info["path"])
        
        # Update status
        analysis_jobs[repo_id] = {
            "status": "completed",
            "progress": 100,
            "error": None,
            "structure": structure,
            "graph": graph_builder.get_graph_data()
        }
        
    except Exception as e:
        analysis_jobs[repo_id] = {
            "status": "error",
            "progress": 0,
            "error": str(e)
        }
    finally:
        # Cleanup
        if repo_path and repo_path.exists():
            shutil.rmtree(repo_path)

@app.get("/api/repo/{repo_id}")
async def get_analysis_status(repo_id: str):
    """Get analysis status."""
    if repo_id not in analysis_jobs:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return analysis_jobs[repo_id]

@app.get("/api/repo/{repo_id}/graph")
async def get_graph(repo_id: str, level: int = 1):
    """Get graph data."""
    if repo_id not in analysis_jobs:
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    status = analysis_jobs[repo_id]
    if status["status"] != "completed":
        raise HTTPException(status_code=400, detail="Analysis not completed")
    
    return graph_builder.get_graph_data(level)

@app.get("/api/repo/{repo_id}/node/{node_id}")
async def get_node_details(repo_id: str, node_id: str):
    """Get node details."""
    if repo_id not in analysis_jobs:
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    status = analysis_jobs[repo_id]
    if status["status"] != "completed":
        raise HTTPException(status_code=400, detail="Analysis not completed")
    
    details = graph_builder.get_node_details(node_id)
    if not details:
        raise HTTPException(status_code=404, detail="Node not found")
    
    return details

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 