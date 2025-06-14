from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncio
import os
import shutil
from datetime import datetime
import logging
from typing import Dict, Optional, List
from .repo_analyzer import RepoAnalyzer
from .graph_builder import GraphBuilder

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Add CORS middleware with WebSocket support
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Initialize analyzer and graph builder
analyzer = RepoAnalyzer()
graph_builder = GraphBuilder()

# Store active analysis jobs and WebSocket connections
active_jobs: Dict[str, dict] = {}
active_websockets: Dict[str, List[WebSocket]] = {}

class RepoRequest(BaseModel):
    url: str
    branch: str = "main"

async def update_status(repo_id: str, status: dict):
    """Update analysis status and notify WebSocket clients."""
    try:
        # Update job status
        active_jobs[repo_id] = status
        
        # Notify all connected WebSocket clients
        if repo_id in active_websockets:
            disconnected_websockets = []
            for ws in active_websockets[repo_id]:
                try:
                    await ws.send_json(status)
                except WebSocketDisconnect:
                    disconnected_websockets.append(ws)
                except Exception as e:
                    logger.error(f"Error sending status to WebSocket: {str(e)}")
                    disconnected_websockets.append(ws)
            
            # Remove disconnected WebSockets
            for ws in disconnected_websockets:
                if ws in active_websockets[repo_id]:
                    active_websockets[repo_id].remove(ws)
            
            # Clean up empty lists
            if not active_websockets[repo_id]:
                del active_websockets[repo_id]
    except Exception as e:
        logger.error(f"Error updating status: {str(e)}")

@app.post("/api/repo")
async def analyze_repo(request: RepoRequest):
    """Start repository analysis."""
    try:
        # Generate unique ID for this analysis
        repo_id = analyzer.get_repo_id(request.url)
        
        # Check if analysis already exists
        if repo_id in active_jobs:
            return {"id": repo_id, "status": active_jobs[repo_id]}
        
        # Initialize analysis status
        await update_status(repo_id, {
            "status": "processing",
            "progress": 0,
            "error": None,
            "message": "Starting analysis...",
            "started_at": datetime.utcnow().isoformat()
        })
        
        # Start analysis in background
        asyncio.create_task(process_repo(repo_id, request.url, request.branch))
        
        return {"id": repo_id, "status": active_jobs[repo_id]}
    except Exception as e:
        logger.error(f"Error starting analysis: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/repo/{repo_id}")
async def get_analysis_status(repo_id: str):
    """Get analysis status."""
    if repo_id not in active_jobs:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return active_jobs[repo_id]

@app.get("/api/repo/{repo_id}/graph")
async def get_analysis_graph(repo_id: str):
    """Get analysis graph data."""
    if repo_id not in active_jobs:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return active_jobs[repo_id].get("graph", {})

@app.websocket("/ws/repo/{repo_id}")
async def websocket_endpoint(websocket: WebSocket, repo_id: str):
    """WebSocket endpoint for real-time status updates."""
    try:
        await websocket.accept()
        logger.info(f"WebSocket connection accepted for repo_id: {repo_id}")
        
        # Add WebSocket to active connections
        if repo_id not in active_websockets:
            active_websockets[repo_id] = []
        active_websockets[repo_id].append(websocket)
        
        # Send initial status if available
        if repo_id in active_jobs:
            try:
                await websocket.send_json(active_jobs[repo_id])
            except Exception as e:
                logger.error(f"Error sending initial status: {str(e)}")
        
        # Keep connection alive and handle disconnection
        while True:
            try:
                # Wait for any message (we don't need to process it)
                await websocket.receive_text()
            except WebSocketDisconnect:
                logger.info(f"WebSocket disconnected for repo_id: {repo_id}")
                break
            except Exception as e:
                logger.error(f"WebSocket error: {str(e)}")
                break
    except Exception as e:
        logger.error(f"Error in WebSocket connection: {str(e)}")
    finally:
        # Remove WebSocket from active connections
        if repo_id in active_websockets and websocket in active_websockets[repo_id]:
            active_websockets[repo_id].remove(websocket)
            if not active_websockets[repo_id]:
                del active_websockets[repo_id]
        logger.info(f"WebSocket connection cleaned up for repo_id: {repo_id}")

async def process_repo(repo_id: str, repo_url: str, branch: str):
    """Process repository analysis in background."""
    try:
        # Initialize repo_path before try block
        repo_path = None
        
        # Update status to processing
        await update_status(repo_id, {
            "status": "processing",
            "progress": 0,
            "error": None,
            "message": "Starting repository analysis..."
        })
        
        # Clone repository
        repo_path = await analyzer.clone_repository(repo_url, branch)
        
        # Update status
        await update_status(repo_id, {
            "status": "processing",
            "progress": 10,
            "error": None,
            "message": "Repository cloned successfully"
        })
        
        # Analyze repository
        structure, graph = await analyzer.analyze_repository(repo_path)
        
        # Update status to completed but keep in active_jobs
        await update_status(repo_id, {
            "status": "completed",
            "progress": 100,
            "error": None,
            "message": "Analysis completed successfully",
            "structure": structure,
            "graph": graph,
            "completed_at": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error processing repository {repo_id}: {str(e)}")
        # Update status to error but keep in active_jobs
        await update_status(repo_id, {
            "status": "error",
            "progress": 0,
            "error": str(e),
            "message": "Analysis failed"
        })
    finally:
        # Clean up repository
        if repo_path and os.path.exists(repo_path):
            try:
                shutil.rmtree(repo_path)
                logger.info(f"Cleaned up repository directory: {repo_path}")
            except Exception as e:
                logger.error(f"Error cleaning up repository directory: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 