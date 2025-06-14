import os
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import git
from git import Repo
import tempfile
import shutil
import asyncio

class RepoAnalyzer:
    def __init__(self, cache_dir: Optional[str] = None):
        """
        Initialize the repository analyzer.
        
        Args:
            cache_dir: Optional directory to store cloned repositories and analysis results
        """
        self.cache_dir = cache_dir or os.path.join(tempfile.gettempdir(), "halos_cache")
        os.makedirs(self.cache_dir, exist_ok=True)

    def get_repo_id(self, repo_url: str) -> str:
        """
        Generate a unique ID for a repository.
        
        Args:
            repo_url: URL of the repository
            
        Returns:
            Unique ID string
        """
        return hashlib.sha256(repo_url.encode()).hexdigest()

    def _compute_file_hash(self, file_path: Path) -> str:
        """Compute SHA-256 hash of a file's contents."""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def _get_repo_dir(self, repo_url: str) -> Path:
        """Get the directory path for a repository."""
        repo_name = repo_url.split("/")[-1].replace(".git", "")
        return Path(self.cache_dir) / repo_name

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
            # Clone the repository
            repo = await asyncio.to_thread(Repo.clone_from, repo_url, repo_dir)
        
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
            ".hpp", ".cs", ".rb", ".php", ".swift", ".kt", ".rs"
        }
        
        source_files = []
        for ext in source_extensions:
            source_files.extend(repo_path.rglob(f"*{ext}"))
        
        return source_files

    def analyze_repository(self, repo_path: Path) -> Dict[str, Any]:
        """
        Analyze a repository and return its structure.
        
        Args:
            repo_path: Path to the repository
            
        Returns:
            Dictionary containing repository analysis results
        """
        source_files = self.get_source_files(repo_path)
        
        # Create initial folder structure
        structure = {
            "id": self.get_repo_id(str(repo_path)),
            "name": repo_path.name,
            "url": str(repo_path),
            "branch": "main",  # TODO: Get actual branch
            "folders": {},
            "files": []
        }
        
        # Process each source file
        for file_path in source_files:
            relative_path = file_path.relative_to(repo_path)
            file_hash = self._compute_file_hash(file_path)
            
            # Add file to structure
            structure["files"].append({
                "path": str(relative_path),
                "hash": file_hash,
                "size": file_path.stat().st_size
            })
            
            # Update folder structure
            current = structure["folders"]
            for part in relative_path.parts[:-1]:
                if part not in current:
                    current[part] = {"folders": {}, "files": []}
                current = current[part]["folders"]
        
        return structure

    def cleanup(self, repo_id: str) -> None:
        """
        Clean up repository files.
        
        Args:
            repo_id: ID of the repository to clean up
        """
        # TODO: Implement cleanup logic
        pass 