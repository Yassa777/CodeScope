import os
import json
import hashlib
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
import openai
from datetime import datetime
import sqlite3
import aiosqlite

from .code_analyzer import CodeChunk, FileSummary, ModuleSummary


@dataclass
class ChunkSummary:
    """Represents a leaf-level one-liner summary of a code chunk."""
    chunk_id: str
    chunk_hash: str
    summary: str
    confidence: float
    model_used: str
    timestamp: datetime
    token_count: int
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            'timestamp': self.timestamp.isoformat()
        }


@dataclass
class HierarchicalSummary:
    """Represents a summary at any level of the hierarchy."""
    level: str  # chunk, file, directory, repository
    path: str
    summary: str
    components: List[str]  # List of component IDs that make up this summary
    centrality_score: float = 0.0
    importance_score: float = 0.0
    hash: str = ""
    
    def __post_init__(self):
        if not self.hash:
            self.hash = self._compute_hash()
    
    def _compute_hash(self) -> str:
        """Compute hash based on components and path."""
        content = f"{self.path}:{':'.join(sorted(self.components))}"
        return hashlib.sha256(content.encode()).hexdigest()


class HierarchicalSummarizer:
    """
    Implements hierarchical code summarization:
    1. Chunk-level one-liners (cheap model)
    2. File-level summaries (from chunk summaries)
    3. Directory-level summaries (from file summaries)
    4. Repository-level summary (from directory summaries)
    """
    
    def __init__(self, cache_dir: str = None, openai_api_key: str = None):
        self.cache_dir = cache_dir or os.path.join(os.path.expanduser("~"), ".scout_cache")
        self.summary_cache_dir = os.path.join(self.cache_dir, "summaries")
        os.makedirs(self.summary_cache_dir, exist_ok=True)
        
        # Store API key for lazy initialization
        self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        self.openai_client = None  # Initialize lazily
        
        # Database for caching
        self.db_path = os.path.join(self.cache_dir, "summaries.db")
        self._init_database()
        
        # Model configurations
        self.cheap_model = "gpt-3.5-turbo"  # For chunk-level summaries
        self.powerful_model = "gpt-4o-mini"  # For higher-level summaries
        
    def _init_database(self):
        """Initialize SQLite database for caching summaries."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS chunk_summaries (
                chunk_hash TEXT PRIMARY KEY,
                chunk_id TEXT,
                summary TEXT,
                confidence REAL,
                model_used TEXT,
                timestamp TEXT,
                token_count INTEGER
            )
        """)
        
        conn.execute("""
            CREATE TABLE IF NOT EXISTS hierarchical_summaries (
                hash TEXT PRIMARY KEY,
                level TEXT,
                path TEXT,
                summary TEXT,
                components TEXT,  -- JSON array
                centrality_score REAL,
                importance_score REAL,
                timestamp TEXT
            )
        """)
        
        conn.commit()
        conn.close()
    
    def _get_openai_client(self):
        """Get OpenAI client, initializing it lazily."""
        if self.openai_client is None:
            if not self.openai_api_key:
                raise ValueError("OpenAI API key not configured. Set OPENAI_API_KEY environment variable.")
            self.openai_client = openai.AsyncOpenAI(api_key=self.openai_api_key)
        return self.openai_client
    
    async def _get_cached_chunk_summary(self, chunk_hash: str) -> Optional[ChunkSummary]:
        """Retrieve cached chunk summary by hash."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT * FROM chunk_summaries WHERE chunk_hash = ?", 
                (chunk_hash,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return ChunkSummary(
                        chunk_id=row[1],
                        chunk_hash=row[0],
                        summary=row[2],
                        confidence=row[3],
                        model_used=row[4],
                        timestamp=datetime.fromisoformat(row[5]),
                        token_count=row[6]
                    )
                return None
    
    async def _cache_chunk_summary(self, summary: ChunkSummary):
        """Cache a chunk summary."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO chunk_summaries 
                (chunk_hash, chunk_id, summary, confidence, model_used, timestamp, token_count)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                summary.chunk_hash,
                summary.chunk_id,
                summary.summary,
                summary.confidence,
                summary.model_used,
                summary.timestamp.isoformat(),
                summary.token_count
            ))
            await db.commit()
    
    async def _generate_chunk_summary(self, chunk: CodeChunk) -> ChunkSummary:
        """Generate a one-liner summary for a code chunk using the cheap model."""
        # Check cache first
        cached = await self._get_cached_chunk_summary(chunk.hash)
        if cached:
            print(f"📋 Using cached summary for {chunk.id}")
            return cached
        
        # Create prompt for one-liner summary
        prompt = self._create_chunk_summary_prompt(chunk)
        
        try:
            print(f"🤖 Generating summary for chunk {chunk.id}")
            client = self._get_openai_client()
            response = await client.chat.completions.create(
                model=self.cheap_model,
                messages=[
                    {"role": "system", "content": "You are a code analysis expert. Generate concise one-line summaries."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=50,
                temperature=0.1
            )
            
            summary_text = response.choices[0].message.content.strip()
            token_count = response.usage.total_tokens
            
            # Create summary object
            summary = ChunkSummary(
                chunk_id=chunk.id,
                chunk_hash=chunk.hash,
                summary=summary_text,
                confidence=0.8,  # Default confidence for successful generation
                model_used=self.cheap_model,
                timestamp=datetime.now(),
                token_count=token_count
            )
            
            # Cache the summary
            await self._cache_chunk_summary(summary)
            print(f"✅ Generated and cached summary for {chunk.id}")
            
            return summary
            
        except Exception as e:
            print(f"❌ Failed to generate summary for {chunk.id}: {e}")
            # Return fallback summary
            return ChunkSummary(
                chunk_id=chunk.id,
                chunk_hash=chunk.hash,
                summary=f"{chunk.ast_type} in {Path(chunk.path).name}",
                confidence=0.3,
                model_used="fallback",
                timestamp=datetime.now(),
                token_count=0
            )
    
    def _create_chunk_summary_prompt(self, chunk: CodeChunk) -> str:
        """Create prompt for generating chunk-level summary."""
        context = ""
        if chunk.parent_symbol:
            context = f" (inside {chunk.parent_symbol})"
        
        docstring_context = ""
        if chunk.docstring:
            docstring_context = f"\nDocstring: {chunk.docstring[:100]}..."
        
        return f"""Generate a concise one-line summary (max 10 words) for this {chunk.ast_type}{context}:

File: {Path(chunk.path).name}
Lines {chunk.start_line}-{chunk.end_line}
{docstring_context}

Code:
{chunk.content[:500]}...

Summary (one line, max 10 words):"""
    
    async def summarize_chunks(self, chunks: List[CodeChunk]) -> List[ChunkSummary]:
        """Generate summaries for a list of chunks."""
        print(f"📝 Generating summaries for {len(chunks)} chunks...")
        
        # Process chunks in batches to avoid rate limiting
        batch_size = 5
        summaries = []
        
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            batch_tasks = [self._generate_chunk_summary(chunk) for chunk in batch]
            batch_summaries = await asyncio.gather(*batch_tasks)
            summaries.extend(batch_summaries)
            
            # Small delay between batches
            if i + batch_size < len(chunks):
                await asyncio.sleep(0.5)
        
        print(f"✅ Generated {len(summaries)} chunk summaries")
        return summaries
    
    async def _generate_file_summary(
        self, 
        file_path: str, 
        chunk_summaries: List[ChunkSummary],
        centrality_scores: Dict[str, float] = None
    ) -> HierarchicalSummary:
        """Generate file-level summary from chunk summaries."""
        if not chunk_summaries:
            return HierarchicalSummary(
                level="file",
                path=file_path,
                summary=f"Empty file: {Path(file_path).name}",
                components=[]
            )
        
        # Sort chunk summaries by centrality score (if available) or line number
        if centrality_scores:
            chunk_summaries.sort(
                key=lambda cs: centrality_scores.get(cs.chunk_id, 0.0),
                reverse=True
            )
        else:
            # Fallback: sort by chunk ID which contains line numbers
            chunk_summaries.sort(key=lambda cs: cs.chunk_id)
        
        # Create prompt for file-level summary
        chunk_list = "\n".join([
            f"- {cs.summary}" for cs in chunk_summaries[:10]  # Top 10 chunks
        ])
        
        prompt = f"""Generate a comprehensive summary for this file based on its components:

File: {Path(file_path).name}
Components ({len(chunk_summaries)} total):
{chunk_list}

Generate a 2-3 sentence summary describing:
1. The primary purpose of this file
2. Key functionality it provides
3. How it fits into the larger system

Summary:"""
        
        try:
            client = self._get_openai_client()
            response = await client.chat.completions.create(
                model=self.powerful_model,
                messages=[
                    {"role": "system", "content": "You are a senior software architect analyzing code structure."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=200,
                temperature=0.2
            )
            
            summary_text = response.choices[0].message.content.strip()
            
        except Exception as e:
            print(f"❌ Failed to generate file summary for {file_path}: {e}")
            summary_text = f"File containing {len(chunk_summaries)} components including functions and classes"
        
        return HierarchicalSummary(
            level="file",
            path=file_path,
            summary=summary_text,
            components=[cs.chunk_id for cs in chunk_summaries],
            centrality_score=max([centrality_scores.get(cs.chunk_id, 0.0) for cs in chunk_summaries], default=0.0),
            importance_score=len(chunk_summaries) / 10.0  # Simple importance based on chunk count
        )
    
    async def _generate_directory_summary(
        self, 
        dir_path: str, 
        file_summaries: List[HierarchicalSummary]
    ) -> HierarchicalSummary:
        """Generate directory-level summary from file summaries."""
        if not file_summaries:
            return HierarchicalSummary(
                level="directory",
                path=dir_path,
                summary=f"Empty directory: {Path(dir_path).name}",
                components=[]
            )
        
        # Sort files by importance score
        file_summaries.sort(key=lambda fs: fs.importance_score, reverse=True)
        
        file_list = "\n".join([
            f"- {Path(fs.path).name}: {fs.summary[:100]}..."
            for fs in file_summaries[:8]  # Top 8 files
        ])
        
        prompt = f"""Generate a summary for this directory based on its files:

Directory: {Path(dir_path).name}
Files ({len(file_summaries)} total):
{file_list}

Generate a 2-3 sentence summary describing:
1. The primary purpose of this directory/module
2. Key functionality it provides
3. How it contributes to the overall system

Summary:"""
        
        try:
            client = self._get_openai_client()
            response = await client.chat.completions.create(
                model=self.powerful_model,
                messages=[
                    {"role": "system", "content": "You are a senior software architect analyzing system architecture."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=200,
                temperature=0.2
            )
            
            summary_text = response.choices[0].message.content.strip()
            
        except Exception as e:
            print(f"❌ Failed to generate directory summary for {dir_path}: {e}")
            summary_text = f"Directory containing {len(file_summaries)} files with various functionality"
        
        return HierarchicalSummary(
            level="directory",
            path=dir_path,
            summary=summary_text,
            components=[fs.path for fs in file_summaries],
            importance_score=sum(fs.importance_score for fs in file_summaries) / len(file_summaries)
        )
    
    async def generate_hierarchical_summary(
        self, 
        chunks: List[CodeChunk],
        centrality_scores: Dict[str, float] = None
    ) -> Dict[str, Any]:
        """
        Generate complete hierarchical summary following the original plan:
        1. Generate chunk-level summaries
        2. Generate file-level summaries  
        3. Generate directory-level summaries
        4. Generate repository-level summary
        """
        print("🏗️ Starting hierarchical summarization...")
        
        # Step 1: Generate chunk-level summaries
        chunk_summaries = await self.summarize_chunks(chunks)
        
        # Step 2: Group chunks by file and generate file summaries
        chunks_by_file = {}
        for chunk_summary in chunk_summaries:
            # Extract file path from chunk_id (format: path:start:end)
            chunk_id = chunk_summary.chunk_id
            file_path = ':'.join(chunk_id.split(':')[:-2])  # Remove :start:end
            
            if file_path not in chunks_by_file:
                chunks_by_file[file_path] = []
            chunks_by_file[file_path].append(chunk_summary)
        
        print(f"📁 Generating summaries for {len(chunks_by_file)} files...")
        file_summaries = []
        for file_path, file_chunk_summaries in chunks_by_file.items():
            file_summary = await self._generate_file_summary(
                file_path, 
                file_chunk_summaries, 
                centrality_scores
            )
            file_summaries.append(file_summary)
        
        # Step 3: Group files by directory and generate directory summaries
        files_by_dir = {}
        for file_summary in file_summaries:
            dir_path = str(Path(file_summary.path).parent)
            if dir_path not in files_by_dir:
                files_by_dir[dir_path] = []
            files_by_dir[dir_path].append(file_summary)
        
        print(f"📂 Generating summaries for {len(files_by_dir)} directories...")
        directory_summaries = []
        for dir_path, dir_file_summaries in files_by_dir.items():
            dir_summary = await self._generate_directory_summary(dir_path, dir_file_summaries)
            directory_summaries.append(dir_summary)
        
        # Step 4: Generate repository-level summary
        repository_summary = await self._generate_repository_summary(directory_summaries)
        
        print("✅ Hierarchical summarization complete!")
        
        return {
            "chunk_summaries": [cs.to_dict() for cs in chunk_summaries],
            "file_summaries": [asdict(fs) for fs in file_summaries],
            "directory_summaries": [asdict(ds) for ds in directory_summaries],
            "repository_summary": asdict(repository_summary),
            "stats": {
                "total_chunks": len(chunk_summaries),
                "total_files": len(file_summaries),
                "total_directories": len(directory_summaries),
                "cache_hits": sum(1 for cs in chunk_summaries if cs.model_used != "fallback"),
                "api_calls": sum(1 for cs in chunk_summaries if cs.model_used == self.cheap_model) + len(file_summaries) + len(directory_summaries) + 1
            }
        }
    
    async def _generate_repository_summary(
        self, 
        directory_summaries: List[HierarchicalSummary]
    ) -> HierarchicalSummary:
        """Generate repository-level summary from directory summaries."""
        if not directory_summaries:
            return HierarchicalSummary(
                level="repository",
                path=".",
                summary="Empty repository",
                components=[]
            )
        
        # Sort directories by importance
        directory_summaries.sort(key=lambda ds: ds.importance_score, reverse=True)
        
        dir_list = "\n".join([
            f"- {Path(ds.path).name}: {ds.summary[:150]}..."
            for ds in directory_summaries[:6]  # Top 6 directories
        ])
        
        prompt = f"""Generate a high-level summary for this repository based on its main directories:

Repository Structure:
{dir_list}

Generate a 3-4 sentence summary describing:
1. What this codebase does (its primary purpose)
2. Key architectural components and their roles
3. Technology stack and patterns used
4. Overall system design approach

Summary:"""
        
        try:
            client = self._get_openai_client()
            response = await client.chat.completions.create(
                model=self.powerful_model,
                messages=[
                    {"role": "system", "content": "You are a principal engineer reviewing a complete codebase for architectural understanding."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=300,
                temperature=0.2
            )
            
            summary_text = response.choices[0].message.content.strip()
            
        except Exception as e:
            print(f"❌ Failed to generate repository summary: {e}")
            summary_text = f"Repository with {len(directory_summaries)} main components providing various functionality"
        
        return HierarchicalSummary(
            level="repository",
            path=".",
            summary=summary_text,
            components=[ds.path for ds in directory_summaries],
            importance_score=sum(ds.importance_score for ds in directory_summaries) / len(directory_summaries)
        ) 