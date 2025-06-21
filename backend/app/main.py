from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
import asyncio
import tempfile
import shutil
from pathlib import Path
from .code_analyzer import CodeAnalyzer

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Initialize the code analyzer
analyzer = CodeAnalyzer()

class RepoTreeRequest(BaseModel):
    repo_url: str
    token: str = None

class RepoAnalysisRequest(BaseModel):
    repo_url: str
    token: str = None

# Helper to parse repo URL
def parse_repo_url(url: str):
    from urllib.parse import urlparse
    u = urlparse(url)
    if u.hostname != "github.com":
        return None, None
    parts = u.path.lstrip("/").split("/")
    if len(parts) < 2:
        return None, None
    owner, repo = parts[:2]
    return owner, repo.replace('.git', '')

# Helper to build tree
def build_tree(flat):
    root = {}
    for item in flat:
        parts = item['path'].split('/')
        current = root
        for idx, part in enumerate(parts):
            if part not in current:
                current[part] = {
                    'id': item['sha'] + '-' + str(idx),
                    'name': part,
                    'path': '/'.join(parts[:idx+1]),
                    'type': item['type'] if idx == len(parts)-1 else 'tree',
                    'children': {}
                }
            current = current[part]['children']
    def object_to_array(obj):
        return [
            {**node, 'children': object_to_array(node['children']) if node['type'] == 'tree' else None}
            for node in obj.values()
        ]
    return object_to_array(root)

async def clone_repository(repo_url: str, owner: str, repo: str) -> Path:
    """Clone a repository to a temporary directory."""
    import git
    from git import Repo
    
    temp_dir = Path(tempfile.mkdtemp())
    repo_path = temp_dir / repo
    
    try:
        # Clone the repository
        Repo.clone_from(repo_url, repo_path, depth=1)
        return repo_path
    except Exception as e:
        # Clean up on error
        if repo_path.exists():
            shutil.rmtree(repo_path)
        raise e

@app.post("/api/repo/tree")
async def get_repo_tree(request: RepoTreeRequest):
    """Get repository file tree from GitHub API."""
    owner, repo = parse_repo_url(request.repo_url)
    if not owner or not repo:
        raise HTTPException(status_code=400, detail="Invalid GitHub repository URL")
    
    headers = {"Accept": "application/vnd.github+json"}
    if request.token:
        headers["Authorization"] = f"Bearer {request.token}"
    
    async with httpx.AsyncClient() as client:
        # 1. Get default branch
        repo_resp = await client.get(f"https://api.github.com/repos/{owner}/{repo}", headers=headers)
        if repo_resp.status_code != 200:
            raise HTTPException(status_code=repo_resp.status_code, detail=f"Failed to load repository: {repo_resp.text}")
        repo_data = repo_resp.json()
        branch = repo_data.get('default_branch', 'main')
        
        # 2. Get tree
        tree_resp = await client.get(f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1", headers=headers)
        if tree_resp.status_code != 200:
            raise HTTPException(status_code=tree_resp.status_code, detail=f"Failed to load tree: {tree_resp.text}")
        tree_data = tree_resp.json()
        if tree_data.get('truncated'):
            print("Warning: GitHub truncated the response – large repositories may need pagination or sub‑tree loading.")
        tree = build_tree(tree_data['tree'])
        return {"tree": tree}

@app.post("/api/repo/analyze")
async def analyze_repository(request: RepoAnalysisRequest):
    """Analyze a repository using Tree-Sitter and generate code structure."""
    owner, repo = parse_repo_url(request.repo_url)
    if not owner or not repo:
        raise HTTPException(status_code=400, detail="Invalid GitHub repository URL")
    
    repo_url = f"https://github.com/{owner}/{repo}.git"
    
    try:
        # Clone the repository
        repo_path = await clone_repository(repo_url, owner, repo)
        
        # Analyze the repository
        analysis_result = await analyzer.analyze_repository(repo_path)
        
        # Clean up
        if repo_path.exists():
            shutil.rmtree(repo_path)
        
        return analysis_result
        
    except Exception as e:
        # Clean up on error
        if 'repo_path' in locals() and repo_path.exists():
            shutil.rmtree(repo_path)
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

@app.get("/api/analysis/{analysis_id}")
async def get_analysis(analysis_id: str):
    """Get cached analysis results."""
    # TODO: Implement caching and retrieval
    raise HTTPException(status_code=404, detail="Analysis not found")

@app.get("/api/analysis/{analysis_id}/modules")
async def get_modules(analysis_id: str):
    """Get module structure for an analysis."""
    # TODO: Implement module retrieval
    raise HTTPException(status_code=404, detail="Analysis not found")

@app.get("/api/analysis/{analysis_id}/files/{file_path:path}")
async def get_file_details(analysis_id: str, file_path: str):
    """Get detailed file analysis."""
    # TODO: Implement file detail retrieval
    raise HTTPException(status_code=404, detail="File not found")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 