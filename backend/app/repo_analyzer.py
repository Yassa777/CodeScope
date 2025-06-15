import os
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Set
import git
from git import Repo
import tempfile
import shutil
import asyncio
import aiohttp
import concurrent.futures
from datetime import datetime, timedelta
import json
import re

class RepoAnalyzer:
    def __init__(self, cache_dir: Optional[str] = None):
        """
        Initialize the repository analyzer.
        
        Args:
            cache_dir: Optional directory to store cloned repositories and analysis results
        """
        self.cache_dir = cache_dir or os.path.join(tempfile.gettempdir(), "halos_cache")
        self.analysis_cache_dir = os.path.join(self.cache_dir, "analysis")
        os.makedirs(self.cache_dir, exist_ok=True)
        os.makedirs(self.analysis_cache_dir, exist_ok=True)
        
        # Initialize thread pool for parallel processing
        self.thread_pool = concurrent.futures.ThreadPoolExecutor(max_workers=os.cpu_count())
        
        # File patterns to ignore
        self.ignore_patterns = {
            r'\.git/',
            r'node_modules/',
            r'\.env',
            r'\.DS_Store',
            r'\.idea/',
            r'\.vscode/',
            r'__pycache__/',
            r'\.pyc$',
            r'\.pyo$',
            r'\.pyd$',
            r'\.so$',
            r'\.dylib$',
            r'\.dll$',
            r'\.exe$',
            r'\.bin$',
            r'\.zip$',
            r'\.tar$',
            r'\.gz$',
            r'\.rar$',
            r'\.7z$',
            r'\.pdf$',
            r'\.doc$',
            r'\.docx$',
            r'\.xls$',
            r'\.xlsx$',
            r'\.ppt$',
            r'\.pptx$',
            r'\.jpg$',
            r'\.jpeg$',
            r'\.png$',
            r'\.gif$',
            r'\.ico$',
            r'\.svg$',
            r'\.mp3$',
            r'\.mp4$',
            r'\.mov$',
            r'\.avi$',
            r'\.wmv$',
        }
        self.ignore_regex = re.compile('|'.join(self.ignore_patterns))

    def get_repo_id(self, repo_url: str) -> str:
        """
        Generate a unique ID for a repository.
        
        Args:
            repo_url: URL of the repository
            
        Returns:
            Unique ID string
        """
        return hashlib.sha256(repo_url.encode()).hexdigest()

    async def _compute_file_hash(self, file_path: Path) -> str:
        """Compute SHA-256 hash of a file's contents asynchronously."""
        def _hash_file():
            sha256_hash = hashlib.sha256()
            with open(file_path, "rb") as f:
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
            return sha256_hash.hexdigest()
        
        return await asyncio.get_event_loop().run_in_executor(self.thread_pool, _hash_file)

    def _get_repo_dir(self, repo_url: str) -> Path:
        """Get the directory path for a repository."""
        repo_name = repo_url.split("/")[-1].replace(".git", "")
        return Path(self.cache_dir) / repo_name

    def _get_cache_path(self, repo_id: str) -> Path:
        """Get the path for cached analysis results."""
        return Path(self.analysis_cache_dir) / f"{repo_id}.json"

    async def _get_github_tree(self, owner: str, repo: str, branch: str = "main") -> Dict[str, Any]:
        """Get repository tree using GitHub API."""
        async with aiohttp.ClientSession() as session:
            # Get the default branch's SHA
            async with session.get(f"https://api.github.com/repos/{owner}/{repo}/branches/{branch}") as response:
                if response.status != 200:
                    raise Exception(f"Failed to get branch info: {await response.text()}")
                branch_info = await response.json()
                sha = branch_info["commit"]["sha"]

            # Get the tree recursively
            async with session.get(f"https://api.github.com/repos/{owner}/{repo}/git/trees/{sha}?recursive=1") as response:
                if response.status != 200:
                    raise Exception(f"Failed to get tree: {await response.text()}")
                return await response.json()

    async def clone_repository(self, repo_url: str, branch: str = "main") -> Path:
        """
        Clone a repository and return its local path.
        
        Args:
            repo_url: URL of the repository to clone
            branch: Branch to checkout
            
        Returns:
            Path to the cloned repository
        """
        repo_dir = self._get_repo_dir(repo_url)
        
        if repo_dir.exists():
            # Repository already exists, update it
            repo = Repo(repo_dir)
            origin = repo.remotes.origin
            await asyncio.to_thread(origin.pull)
        else:
            # Clone the repository with depth=1 for faster cloning
            repo = await asyncio.to_thread(
                Repo.clone_from,
                repo_url,
                repo_dir,
                depth=1
            )
        
        # Checkout the specified branch
        await asyncio.to_thread(repo.git.checkout, branch)
        
        return repo_dir

    def get_source_files(self, repo_path: Path) -> List[Path]:
        """
        Get all source files in the repository.
        
        Args:
            repo_path: Path to the repository
            
        Returns:
            List of paths to source files
        """
        source_extensions = {
            ".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".java", ".cpp", ".c", ".h",
            ".hpp", ".cs", ".rb", ".php", ".swift", ".kt", ".rs", ".css"
        }
        
        # Use git ls-files for faster file listing
        try:
            repo = Repo(repo_path)
            files = repo.git.ls_files('-z').split('\0')
            return [
                repo_path / f for f in files
                if f and Path(f).suffix in source_extensions and not self.ignore_regex.search(f)
            ]
        except git.GitCommandError:
            # Fallback to rglob if git command fails
            return [
                p for p in repo_path.rglob('*')
                if p.is_file() and p.suffix in source_extensions and not self.ignore_regex.search(str(p))
            ]

    async def analyze_repository(self, repo_path: Path) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Analyze a repository and return its structure and graph data.
        
        Args:
            repo_path: Path to the repository
            
        Returns:
            Tuple containing (structure, graph) data
        """
        # Get repository info
        repo = Repo(repo_path)
        commit_sha = repo.head.commit.hexsha
        
        # Check cache
        cache_path = self._get_cache_path(self.get_repo_id(str(repo_path)))
        if cache_path.exists():
            with open(cache_path) as f:
                cached = json.load(f)
                if cached.get("commit_sha") == commit_sha:
                    return cached["structure"], cached.get("graph", {})
        
        # Get source files
        source_files = self.get_source_files(repo_path)
        print(f"Found {len(source_files)} source files")
        
        # Create initial folder structure
        structure = {
            "id": self.get_repo_id(str(repo_path)),
            "name": repo_path.name,
            "url": str(repo_path),
            "branch": repo.active_branch.name,
            "commit_sha": commit_sha,
            "folders": {},
            "files": []
        }
        
        # Process files in parallel
        async def process_file(file_path: Path):
            relative_path = file_path.relative_to(repo_path)
            file_hash = await self._compute_file_hash(file_path)
            return {
                "path": str(relative_path),
                "hash": file_hash,
                "size": file_path.stat().st_size
            }
        
        # Process files concurrently
        tasks = [process_file(f) for f in source_files]
        file_results = await asyncio.gather(*tasks)
        print(f"Processed {len(file_results)} files")
        
        # Helper function to get or create folder
        def get_or_create_folder(parent: dict, folder_path: str) -> dict:
            if not folder_path:
                return parent
            parts = folder_path.split('/')
            current = parent
            for part in parts:
                if part not in current:
                    current[part] = {"folders": {}, "files": []}
                current = current[part]
            return current
        
        # Add files to structure
        for file_info in file_results:
            path = Path(file_info["path"])
            print(f"\nProcessing file: {path}")
            
            if len(path.parts) == 1:
                # Root file
                print(f"Adding root file: {path.name}")
                structure["files"].append(file_info)
            else:
                # File in a folder
                folder_path = str(path.parent)
                file_name = path.name
                
                # Get the parent folder
                parent_folder = get_or_create_folder(structure["folders"], folder_path)
                
                # Add file to the correct folder
                print(f"Adding file {file_name} to folder {folder_path}")
                parent_folder["files"].append(file_info)
        
        print("\nFinal structure:")
        print(json.dumps(structure, indent=2))
        
        # Create graph data
        graph = {
            "nodes": [],
            "edges": []
        }
        
        # Add root node
        graph["nodes"].append({
            "id": "root",
            "type": "folder",
            "name": "root"
        })
        
        # Add folder nodes and their relationships
        def add_folder_to_graph(folder_path: str, folder_data: dict):
            if folder_path != "root":
                graph["nodes"].append({
                    "id": folder_path,
                    "type": "folder",
                    "name": Path(folder_path).name
                })
                # Add edge from parent folder
                parent = str(Path(folder_path).parent) if Path(folder_path).parent.name else "root"
                graph["edges"].append({
                    "source": parent,
                    "target": folder_path,
                    "type": "contains"
                })
            
            # Process subfolders
            for subfolder_name, subfolder_data in folder_data.get("folders", {}).items():
                subfolder_path = f"{folder_path}/{subfolder_name}" if folder_path != "root" else subfolder_name
                add_folder_to_graph(subfolder_path, subfolder_data)
            
            # Process files in this folder
            for file_info in folder_data.get("files", []):
                file_path = file_info["path"]
                graph["nodes"].append({
                    "id": file_path,
                    "type": "file",
                    "name": Path(file_path).name,
                    "data": {
                        "size": file_info["size"],
                        "hash": file_info["hash"]
                    }
                })
                graph["edges"].append({
                    "source": folder_path if folder_path != "root" else "root",
                    "target": file_path,
                    "type": "contains"
                })
        
        # Process root-level files
        for file_info in structure["files"]:
            file_path = file_info["path"]
            graph["nodes"].append({
                "id": file_path,
                "type": "file",
                "name": Path(file_path).name,
                "data": {
                    "size": file_info["size"],
                    "hash": file_info["hash"]
                }
            })
            graph["edges"].append({
                "source": "root",
                "target": file_path,
                "type": "contains"
            })
        
        # Process folders
        for folder_name, folder_data in structure["folders"].items():
            add_folder_to_graph(folder_name, folder_data)
        
        # Cache the results
        with open(cache_path, 'w') as f:
            json.dump({
                "commit_sha": commit_sha,
                "structure": structure,
                "graph": graph
            }, f, indent=2)
        
        return structure, graph

    async def cleanup_old_files(self, max_age_days: int = 7):
        """Clean up old temporary files and cache entries."""
        cutoff = datetime.now() - timedelta(days=max_age_days)
        
        # Clean up old repositories
        for item in Path(self.cache_dir).iterdir():
            if item.is_dir() and item.name != "analysis":
                try:
                    mtime = datetime.fromtimestamp(item.stat().st_mtime)
                    if mtime < cutoff:
                        shutil.rmtree(item)
                except Exception as e:
                    print(f"Error cleaning up {item}: {e}")
        
        # Clean up old analysis cache
        for item in Path(self.analysis_cache_dir).iterdir():
            if item.is_file():
                try:
                    with open(item) as f:
                        data = json.load(f)
                        timestamp = datetime.fromisoformat(data["timestamp"])
                        if timestamp < cutoff:
                            item.unlink()
                except Exception as e:
                    print(f"Error cleaning up cache {item}: {e}")

    def cleanup(self, repo_id: str) -> None:
        """
        Clean up repository files.
        
        Args:
            repo_id: ID of the repository to clean up
        """
        cache_path = self._get_cache_path(repo_id)
        if cache_path.exists():
            cache_path.unlink() 