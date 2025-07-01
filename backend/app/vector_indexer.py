import os
import asyncio
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Set
from dataclasses import asdict
import json
import tempfile
import numpy as np

import openai
from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.models import (
    Distance, VectorParams, PointStruct, Filter, 
    FieldCondition, Match, Range, SearchRequest
)
import tiktoken

from .code_analyzer import CodeChunk, FileSummary, ModuleSummary


class VectorIndexer:
    """Vector indexer using OpenAI embeddings and Qdrant for semantic code search."""
    
    def __init__(
        self, 
        openai_api_key: Optional[str] = None,
        qdrant_url: str = "http://localhost:6333",
        qdrant_api_key: Optional[str] = None,
        collection_name: str = "halos_code_chunks",
        embedding_model: str = "text-embedding-3-small",
        max_tokens_per_chunk: int = 8000
    ):
        """Initialize the vector indexer."""
        self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        self.qdrant_url = qdrant_url
        self.qdrant_api_key = qdrant_api_key or os.getenv("QDRANT_API_KEY")
        self.collection_name = collection_name
        self.embedding_model = embedding_model
        self.max_tokens_per_chunk = max_tokens_per_chunk
        
        if not self.openai_api_key:
            raise ValueError("OpenAI API key is required. Set OPENAI_API_KEY environment variable.")
        
        # Initialize OpenAI client
        openai.api_key = self.openai_api_key
        self.openai_client = openai.OpenAI(api_key=self.openai_api_key)
        
        # Initialize tokenizer for token counting
        try:
            self.tokenizer = tiktoken.encoding_for_model(self.embedding_model)
        except KeyError:
            # Fallback to a common encoding
            self.tokenizer = tiktoken.get_encoding("cl100k_base")
        
        # Initialize Qdrant client
        try:
            if self.qdrant_api_key:
                self.qdrant_client = QdrantClient(
                    url=self.qdrant_url,
                    api_key=self.qdrant_api_key
                )
            else:
                self.qdrant_client = QdrantClient(url=self.qdrant_url)
            
            self._ensure_collection_exists()
            print(f"Vector indexer initialized with collection: {self.collection_name}")
            
        except Exception as e:
            print(f"Warning: Could not connect to Qdrant: {e}")
            self.qdrant_client = None
    
    def _ensure_collection_exists(self):
        """Ensure the Qdrant collection exists with proper configuration."""
        if not self.qdrant_client:
            return
        
        try:
            # Check if collection exists
            collections = self.qdrant_client.get_collections()
            collection_names = [col.name for col in collections.collections]
            
            if self.collection_name not in collection_names:
                # Create collection with appropriate vector size
                # text-embedding-3-small has 1536 dimensions
                vector_size = 1536 if "3-small" in self.embedding_model else 1536
                
                self.qdrant_client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=vector_size,
                        distance=Distance.COSINE
                    )
                )
                print(f"Created Qdrant collection: {self.collection_name}")
            else:
                print(f"Using existing Qdrant collection: {self.collection_name}")
                
        except Exception as e:
            print(f"Error ensuring collection exists: {e}")
    
    def _count_tokens(self, text: str) -> int:
        """Count tokens in text using the appropriate tokenizer."""
        return len(self.tokenizer.encode(text))
    
    def _prepare_chunk_for_embedding(self, chunk: CodeChunk) -> str:
        """Prepare a code chunk for embedding by creating a rich text representation."""
        parts = []
        
        # Add file context
        file_name = Path(chunk.path).name
        parts.append(f"File: {file_name}")
        
        # Add AST type and parent context
        if chunk.parent_symbol:
            parts.append(f"Inside {chunk.ast_type} '{chunk.parent_symbol}'")
        else:
            parts.append(f"Top-level {chunk.ast_type}")
        
        # Add docstring if available
        if chunk.docstring:
            parts.append(f"Documentation: {chunk.docstring}")
        
        # Add the actual code content
        parts.append(f"Code:\n{chunk.content}")
        
        # Join all parts
        full_text = "\n\n".join(parts)
        
        # Truncate if too long
        token_count = self._count_tokens(full_text)
        if token_count > self.max_tokens_per_chunk:
            # Prioritize keeping the code content
            code_part = f"Code:\n{chunk.content}"
            code_tokens = self._count_tokens(code_part)
            
            if code_tokens <= self.max_tokens_per_chunk:
                # Keep code and add as much context as possible
                remaining_tokens = self.max_tokens_per_chunk - code_tokens
                context_parts = parts[:-1]  # All parts except code
                context_text = "\n\n".join(context_parts)
                
                # Truncate context if needed
                if self._count_tokens(context_text) > remaining_tokens:
                    # Simple truncation - could be made smarter
                    context_text = context_text[:remaining_tokens * 4]  # Rough estimate
                
                full_text = f"{context_text}\n\n{code_part}"
            else:
                # Even code is too long, truncate it
                full_text = code_part[:self.max_tokens_per_chunk * 4]  # Rough estimate
        
        return full_text
    
    async def _get_embedding(self, text: str) -> List[float]:
        """Get embedding for text using OpenAI API."""
        try:
            response = await asyncio.to_thread(
                self.openai_client.embeddings.create,
                model=self.embedding_model,
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            print(f"Error getting embedding: {e}")
            return None
    
    async def index_chunks(self, chunks: List[CodeChunk], batch_size: int = 50) -> bool:
        """Index code chunks with embeddings in Qdrant."""
        if not self.qdrant_client:
            print("Qdrant client not available")
            return False
        
        if not chunks:
            print("No chunks to index")
            return True
        
        print(f"Starting to index {len(chunks)} chunks...")
        
        # Process chunks in batches
        total_batches = (len(chunks) + batch_size - 1) // batch_size
        
        for batch_idx in range(0, len(chunks), batch_size):
            batch_chunks = chunks[batch_idx:batch_idx + batch_size]
            batch_num = (batch_idx // batch_size) + 1
            
            print(f"Processing batch {batch_num}/{total_batches} ({len(batch_chunks)} chunks)")
            
            # Prepare texts for embedding
            texts = []
            for chunk in batch_chunks:
                text = self._prepare_chunk_for_embedding(chunk)
                texts.append(text)
            
            # Get embeddings for the batch
            embeddings = []
            for text in texts:
                embedding = await self._get_embedding(text)
                if embedding:
                    embeddings.append(embedding)
                else:
                    # Use zero vector as fallback
                    embeddings.append([0.0] * 1536)
                
                # Small delay to respect rate limits
                await asyncio.sleep(0.1)
            
            # Create points for Qdrant
            points = []
            for chunk, embedding in zip(batch_chunks, embeddings):
                # Create comprehensive payload
                payload = {
                    "id": chunk.id,
                    "path": chunk.path,
                    "file_name": Path(chunk.path).name,
                    "ast_type": chunk.ast_type,
                    "start_line": chunk.start_line,
                    "end_line": chunk.end_line,
                    "parent_symbol": chunk.parent_symbol or "",
                    "docstring": chunk.docstring or "",
                    "content": chunk.content,
                    "content_hash": chunk.hash,
                    
                    # Additional searchable fields
                    "language": self._detect_language(chunk.path),
                    "is_function": "function" in chunk.ast_type.lower(),
                    "is_class": "class" in chunk.ast_type.lower(),
                    "is_method": "method" in chunk.ast_type.lower(),
                    "has_docstring": bool(chunk.docstring),
                    "line_count": chunk.end_line - chunk.start_line + 1,
                }
                
                point = PointStruct(
                    id=self._generate_point_id(chunk),
                    vector=embedding,
                    payload=payload
                )
                points.append(point)
            
            # Upload batch to Qdrant
            try:
                self.qdrant_client.upsert(
                    collection_name=self.collection_name,
                    points=points
                )
                print(f"Uploaded batch {batch_num}/{total_batches} to Qdrant")
            except Exception as e:
                print(f"Error uploading batch {batch_num}: {e}")
                return False
        
        print(f"Successfully indexed {len(chunks)} chunks")
        return True
    
    def _detect_language(self, file_path: str) -> str:
        """Detect programming language from file extension."""
        ext_to_lang = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.tsx': 'typescript',
            '.jsx': 'javascript',
            '.java': 'java',
            '.cpp': 'cpp',
            '.c': 'c',
            '.h': 'c',
            '.hpp': 'cpp',
            '.cs': 'csharp',
            '.rb': 'ruby',
            '.go': 'go',
            '.rs': 'rust',
            '.php': 'php',
            '.swift': 'swift',
            '.kt': 'kotlin',
        }
        
        ext = Path(file_path).suffix.lower()
        return ext_to_lang.get(ext, 'unknown')
    
    def _generate_point_id(self, chunk: CodeChunk) -> str:
        """Generate a unique point ID for Qdrant."""
        # Use chunk hash as ID (converted to string)
        return chunk.hash
    
    async def semantic_search(
        self, 
        query: str, 
        limit: int = 20,
        score_threshold: float = 0.7,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Perform semantic search using vector similarity."""
        if not self.qdrant_client:
            print("Qdrant client not available")
            return []
        
        # Get query embedding
        query_embedding = await self._get_embedding(query)
        if not query_embedding:
            print("Failed to get query embedding")
            return []
        
        # Build filter conditions
        filter_conditions = None
        if filters:
            conditions = []
            
            if "language" in filters:
                conditions.append(
                    FieldCondition(key="language", match=Match(value=filters["language"]))
                )
            
            if "ast_type" in filters:
                conditions.append(
                    FieldCondition(key="ast_type", match=Match(value=filters["ast_type"]))
                )
            
            if "is_function" in filters:
                conditions.append(
                    FieldCondition(key="is_function", match=Match(value=filters["is_function"]))
                )
            
            if "is_class" in filters:
                conditions.append(
                    FieldCondition(key="is_class", match=Match(value=filters["is_class"]))
                )
            
            if "file_name" in filters:
                conditions.append(
                    FieldCondition(key="file_name", match=Match(value=filters["file_name"]))
                )
            
            if "min_line_count" in filters:
                conditions.append(
                    FieldCondition(
                        key="line_count", 
                        range=Range(gte=filters["min_line_count"])
                    )
                )
            
            if conditions:
                filter_conditions = Filter(must=conditions)
        
        # Perform search
        try:
            search_results = self.qdrant_client.search(
                collection_name=self.collection_name,
                query_vector=query_embedding,
                query_filter=filter_conditions,
                limit=limit,
                score_threshold=score_threshold
            )
            
            # Convert results to our format
            results = []
            for result in search_results:
                payload = result.payload
                results.append({
                    "id": payload["id"],
                    "path": payload["path"],
                    "file_name": payload["file_name"],
                    "content": payload["content"],
                    "ast_type": payload["ast_type"],
                    "start_line": payload["start_line"],
                    "end_line": payload["end_line"],
                    "parent_symbol": payload["parent_symbol"],
                    "docstring": payload["docstring"],
                    "language": payload["language"],
                    "is_function": payload["is_function"],
                    "is_class": payload["is_class"],
                    "score": result.score,
                    "search_type": "semantic"
                })
            
            return results
            
        except Exception as e:
            print(f"Error in semantic search: {e}")
            return []
    
    async def find_similar_chunks(
        self, 
        chunk_id: str, 
        limit: int = 10,
        score_threshold: float = 0.8
    ) -> List[Dict[str, Any]]:
        """Find chunks similar to a given chunk."""
        if not self.qdrant_client:
            return []
        
        # Get the chunk's vector
        try:
            point = self.qdrant_client.retrieve(
                collection_name=self.collection_name,
                ids=[chunk_id],
                with_vectors=True
            )
            
            if not point or not point[0].vector:
                print(f"Could not find vector for chunk {chunk_id}")
                return []
            
            # Search for similar vectors
            search_results = self.qdrant_client.search(
                collection_name=self.collection_name,
                query_vector=point[0].vector,
                limit=limit + 1,  # +1 to exclude the original chunk
                score_threshold=score_threshold
            )
            
            # Filter out the original chunk and convert results
            results = []
            for result in search_results:
                if result.payload["id"] != chunk_id:
                    payload = result.payload
                    results.append({
                        "id": payload["id"],
                        "path": payload["path"],
                        "content": payload["content"],
                        "ast_type": payload["ast_type"],
                        "start_line": payload["start_line"],
                        "end_line": payload["end_line"],
                        "parent_symbol": payload["parent_symbol"],
                        "score": result.score,
                        "search_type": "similar"
                    })
            
            return results[:limit]
            
        except Exception as e:
            print(f"Error finding similar chunks: {e}")
            return []
    
    async def find_entry_points(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Find potential entry points in the codebase."""
        if not self.qdrant_client:
            return []
        
        # Search for main functions, entry points, etc.
        entry_point_queries = [
            "main function entry point",
            "application startup initialization",
            "server start listen",
            "command line interface CLI",
            "route handler endpoint",
            "event handler callback"
        ]
        
        all_results = []
        seen_ids = set()
        
        for query in entry_point_queries:
            results = await self.semantic_search(
                query=query,
                limit=limit // len(entry_point_queries) + 2,
                score_threshold=0.6
            )
            
            for result in results:
                if result["id"] not in seen_ids:
                    result["entry_point_type"] = query
                    all_results.append(result)
                    seen_ids.add(result["id"])
        
        # Sort by score and return top results
        all_results.sort(key=lambda x: x["score"], reverse=True)
        return all_results[:limit]
    
    async def analyze_execution_flows(self, entry_points: List[str], depth: int = 3) -> Dict[str, Any]:
        """Analyze execution flows starting from entry points."""
        if not self.qdrant_client:
            return {}
        
        flows = {}
        
        for entry_point_id in entry_points:
            try:
                # Get the entry point chunk
                point = self.qdrant_client.retrieve(
                    collection_name=self.collection_name,
                    ids=[entry_point_id]
                )
                
                if not point:
                    continue
                
                entry_chunk = point[0].payload
                
                # Build execution flow by finding related functions
                flow = {
                    "entry_point": entry_chunk,
                    "flow_steps": [],
                    "total_depth": depth
                }
                
                # Use semantic search to find related functions
                current_content = entry_chunk["content"]
                
                for level in range(depth):
                    # Extract function calls and imports from current content
                    related_query = f"function call method invoke {current_content[:500]}"
                    
                    related_chunks = await self.semantic_search(
                        query=related_query,
                        limit=5,
                        score_threshold=0.6,
                        filters={"is_function": True}
                    )
                    
                    # Filter out chunks we've already seen
                    new_chunks = [
                        chunk for chunk in related_chunks 
                        if chunk["id"] not in [step["id"] for step in flow["flow_steps"]]
                        and chunk["id"] != entry_point_id
                    ]
                    
                    if new_chunks:
                        best_chunk = new_chunks[0]
                        flow["flow_steps"].append({
                            "level": level + 1,
                            "id": best_chunk["id"],
                            "path": best_chunk["path"],
                            "ast_type": best_chunk["ast_type"],
                            "parent_symbol": best_chunk["parent_symbol"],
                            "score": best_chunk["score"]
                        })
                        current_content = best_chunk["content"]
                    else:
                        break
                
                flows[entry_point_id] = flow
                
            except Exception as e:
                print(f"Error analyzing flow for {entry_point_id}: {e}")
        
        return flows
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """Get statistics about the vector collection."""
        if not self.qdrant_client:
            return {"error": "Qdrant client not available"}
        
        try:
            collection_info = self.qdrant_client.get_collection(self.collection_name)
            
            return {
                "collection_name": self.collection_name,
                "total_points": collection_info.points_count,
                "vector_size": collection_info.config.params.vectors.size,
                "distance_metric": collection_info.config.params.vectors.distance.name,
                "embedding_model": self.embedding_model,
                "status": collection_info.status.name
            }
        except Exception as e:
            return {"error": f"Could not get collection stats: {e}"}
    
    async def clear_collection(self) -> bool:
        """Clear all vectors from the collection."""
        if not self.qdrant_client:
            return False
        
        try:
            self.qdrant_client.delete_collection(self.collection_name)
            self._ensure_collection_exists()
            print(f"Cleared collection: {self.collection_name}")
            return True
        except Exception as e:
            print(f"Error clearing collection: {e}")
            return False 