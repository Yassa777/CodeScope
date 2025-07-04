import os
import tempfile
import shutil
from pathlib import Path
from typing import Dict, Optional, Tuple, List
import validators
import git
from urllib.parse import urlparse
import re

class GitHubManager:
    """Manages GitHub repository cloning and validation."""
    
    def __init__(self, cache_dir: str = "/tmp/halos_repos"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
    
    def is_github_url(self, url: str) -> bool:
        """Check if the URL is a valid GitHub repository URL."""
        if not validators.url(url):
            return False
        
        parsed = urlparse(url)
        if parsed.hostname not in ['github.com', 'www.github.com']:
            return False
        
        # Check for valid repo path pattern: /owner/repo
        path_parts = parsed.path.strip('/').split('/')
        if len(path_parts) < 2:
            return False
        
        # Remove .git suffix if present
        if path_parts[-1].endswith('.git'):
            path_parts[-1] = path_parts[-1][:-4]
        
        return True
    
    def normalize_github_url(self, url: str) -> str:
        """Normalize GitHub URL to clone format."""
        # Remove trailing .git if present and ensure it's HTTPS
        if url.endswith('.git'):
            url = url[:-4]
        
        # Convert SSH to HTTPS
        if url.startswith('git@github.com:'):
            url = url.replace('git@github.com:', 'https://github.com/')
        
        # Ensure HTTPS protocol
        if not url.startswith('http'):
            url = 'https://github.com/' + url.lstrip('/')
        
        return url + '.git'
    
    def extract_repo_info(self, url: str) -> Tuple[str, str]:
        """Extract owner and repository name from GitHub URL."""
        parsed = urlparse(url)
        path_parts = parsed.path.strip('/').split('/')
        
        owner = path_parts[0]
        repo = path_parts[1]
        
        # Remove .git suffix if present
        if repo.endswith('.git'):
            repo = repo[:-4]
        
        return owner, repo
    
    def get_repo_cache_path(self, url: str) -> Path:
        """Get the local cache path for a repository."""
        owner, repo = self.extract_repo_info(url)
        return self.cache_dir / f"{owner}_{repo}"
    
    async def clone_or_update_repo(self, github_url: str, force_fresh: bool = False) -> Dict:
        """Clone or update a GitHub repository and return information."""
        if not self.is_github_url(github_url):
            raise ValueError(f"Invalid GitHub URL: {github_url}")
        
        normalized_url = self.normalize_github_url(github_url)
        owner, repo_name = self.extract_repo_info(github_url)
        cache_path = self.get_repo_cache_path(github_url)
        
        # Remove existing clone if force_fresh is True
        if force_fresh and cache_path.exists():
            shutil.rmtree(cache_path)
        
        try:
            if cache_path.exists() and (cache_path / '.git').exists():
                # Repository exists, try to update
                repo = git.Repo(cache_path)
                origin = repo.remotes.origin
                origin.pull()
                action = "updated"
            else:
                # Clone fresh repository
                if cache_path.exists():
                    shutil.rmtree(cache_path)
                
                repo = git.Repo.clone_from(normalized_url, cache_path, depth=1)
                action = "cloned"
            
            # Get repository information
            commit_info = repo.head.commit
            
            # Count files
            file_count = sum(1 for _ in cache_path.rglob('*') if _.is_file() and not str(_).startswith('.git'))
            
            # Get repository size
            repo_size = sum(f.stat().st_size for f in cache_path.rglob('*') if f.is_file() and not str(f).startswith('.git'))
            
            return {
                "action": action,
                "local_path": str(cache_path),
                "github_url": github_url,
                "owner": owner,
                "repository": repo_name,
                "commit_hash": commit_info.hexsha[:8],
                "commit_message": commit_info.message.strip(),
                "commit_author": commit_info.author.name,
                "commit_date": commit_info.committed_datetime.isoformat(),
                "file_count": file_count,
                "size_bytes": repo_size,
                "size_mb": round(repo_size / (1024 * 1024), 2)
            }
            
        except git.exc.GitCommandError as e:
            if "Authentication failed" in str(e):
                raise ValueError("Repository is private or authentication failed")
            elif "Repository not found" in str(e):
                raise ValueError("Repository not found or does not exist")
            else:
                raise ValueError(f"Git operation failed: {str(e)}")
        except Exception as e:
            raise ValueError(f"Failed to clone repository: {str(e)}")
    
    def list_cached_repos(self) -> List[Dict]:
        """List all cached repositories."""
        repos = []
        
        for repo_dir in self.cache_dir.iterdir():
            if repo_dir.is_dir() and (repo_dir / '.git').exists():
                try:
                    repo = git.Repo(repo_dir)
                    commit_info = repo.head.commit
                    
                    # Parse owner and repo name from directory name
                    parts = repo_dir.name.split('_', 1)
                    owner = parts[0] if len(parts) > 0 else "unknown"
                    repo_name = parts[1] if len(parts) > 1 else repo_dir.name
                    
                    # Get remote URL if available
                    remote_url = None
                    if repo.remotes:
                        remote_url = repo.remotes.origin.url
                    
                    file_count = sum(1 for _ in repo_dir.rglob('*') if _.is_file() and not str(_).startswith('.git'))
                    repo_size = sum(f.stat().st_size for f in repo_dir.rglob('*') if f.is_file() and not str(f).startswith('.git'))
                    
                    repos.append({
                        "local_path": str(repo_dir),
                        "owner": owner,
                        "repository": repo_name,
                        "github_url": remote_url,
                        "commit_hash": commit_info.hexsha[:8],
                        "commit_message": commit_info.message.strip(),
                        "commit_author": commit_info.author.name,
                        "commit_date": commit_info.committed_datetime.isoformat(),
                        "file_count": file_count,
                        "size_mb": round(repo_size / (1024 * 1024), 2),
                        "last_updated": repo_dir.stat().st_mtime
                    })
                except Exception:
                    # Skip directories that aren't valid git repos
                    continue
        
        return sorted(repos, key=lambda x: x['last_updated'], reverse=True)
    
    def delete_cached_repo(self, github_url: str) -> bool:
        """Delete a cached repository."""
        cache_path = self.get_repo_cache_path(github_url)
        
        if cache_path.exists():
            shutil.rmtree(cache_path)
            return True
        return False
    
    def cleanup_old_repos(self, max_repos: int = 10) -> int:
        """Clean up old cached repositories, keeping only the most recent ones."""
        repos = self.list_cached_repos()
        
        if len(repos) <= max_repos:
            return 0
        
        # Sort by last updated time and remove oldest
        repos_to_remove = repos[max_repos:]
        removed_count = 0
        
        for repo in repos_to_remove:
            repo_path = Path(repo['local_path'])
            if repo_path.exists():
                shutil.rmtree(repo_path)
                removed_count += 1
        
        return removed_count 