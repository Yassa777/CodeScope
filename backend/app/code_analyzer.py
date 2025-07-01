import os
import hashlib
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Set
from dataclasses import dataclass, asdict
from tree_sitter import Language, Parser, Node
import tree_sitter_python        as tspy
import tree_sitter_javascript    as tsjs
import tree_sitter_typescript    as tst
import tempfile
import shutil
import asyncio
import aiohttp
from datetime import datetime
import re

@dataclass
class CodeChunk:
    """Represents a parsed code chunk with metadata."""
    id: str
    path: str
    start_line: int
    end_line: int
    ast_type: str
    content: str
    parent_symbol: Optional[str] = None
    docstring: Optional[str] = None
    hash: str = ""
    
    def __post_init__(self):
        if not self.hash:
            self.hash = self._compute_hash()
    
    def _compute_hash(self) -> str:
        """Compute SHA256 hash of file path + start_line + end_line."""
        content = f"{self.path}:{self.start_line}:{self.end_line}"
        return hashlib.sha256(content.encode()).hexdigest()

@dataclass
class FileSummary:
    """Represents a file-level summary."""
    path: str
    summary: str
    chunks: List[CodeChunk]
    functions: List[Dict[str, Any]]
    hash: str = ""
    
    def __post_init__(self):
        if not self.hash:
            self.hash = self._compute_hash()
    
    def _compute_hash(self) -> str:
        """Compute SHA256 hash of all chunk hashes."""
        chunk_hashes = sorted([chunk.hash for chunk in self.chunks])
        content = f"{self.path}:{':'.join(chunk_hashes)}"
        return hashlib.sha256(content.encode()).hexdigest()

@dataclass
class ModuleSummary:
    """Represents a module/directory-level summary."""
    path: str
    summary: str
    files: List[FileSummary]
    submodules: List['ModuleSummary']
    hash: str = ""
    
    def __post_init__(self):
        if not self.hash:
            self.hash = self._compute_hash()
    
    def _compute_hash(self) -> str:
        """Compute SHA256 hash of all file hashes."""
        file_hashes = sorted([f.hash for f in self.files])
        submodule_hashes = sorted([sm.hash for sm in self.submodules])
        content = f"{self.path}:{':'.join(file_hashes + submodule_hashes)}"
        return hashlib.sha256(content.encode()).hexdigest()

# Initialize languages with the modern Tree-sitter API (v0.20+)
def init_languages():
    languages = {}
    
    # Store the language capsules directly - no need for Language wrapper
    try:
        languages["python"] = tspy.language()
        print("✅ Python parser initialized")
    except Exception as e:
        print(f"❌ Failed to initialize Python parser: {e}")
    
    try:
        languages["javascript"] = tsjs.language()
        print("✅ JavaScript parser initialized")
    except Exception as e:
        print(f"❌ Failed to initialize JavaScript parser: {e}")
    
    try:
        languages["typescript"] = tst.language_typescript()
        print("✅ TypeScript parser initialized")
    except Exception as e:
        print(f"❌ Failed to initialize TypeScript parser: {e}")
    
    try:
        languages["tsx"] = tst.language_tsx()
        print("✅ TSX parser initialized")
    except Exception as e:
        print(f"❌ Failed to initialize TSX parser: {e}")
    
    return languages

LANGUAGES = init_languages()

class CodeAnalyzer:
    def __init__(self, 
                 cache_dir: str = None,
                 enable_lexical_index: bool = True,
                 enable_vector_index: bool = False,  # Disabled by default since we don't have Qdrant running
                 enable_dependency_graph: bool = False):  # Disabled by default since we don't have Memgraph running
        """Initialize the code analyzer with Tree-Sitter support."""
        self.cache_dir = cache_dir or os.path.join(tempfile.gettempdir(), "halos_code_cache")
        self.summary_cache_dir = os.path.join(self.cache_dir, "summaries")
        self.chunk_cache_dir = os.path.join(self.cache_dir, "chunks")
        
        os.makedirs(self.cache_dir, exist_ok=True)
        os.makedirs(self.summary_cache_dir, exist_ok=True)
        os.makedirs(self.chunk_cache_dir, exist_ok=True)
        
        # Initialize lexical indexer
        self.lexical_indexer = None
        if enable_lexical_index:
            try:
                from .lexical_indexer import LexicalIndexer
                index_dir = os.path.join(self.cache_dir, "lexical_index")
                self.lexical_indexer = LexicalIndexer(index_dir)
                print("✅ Lexical indexer initialized successfully")
            except ImportError as e:
                print(f"❌ ImportError initializing lexical indexer: {e}")
            except Exception as e:
                print(f"❌ Error initializing lexical indexer: {e}")
        
        # Initialize vector indexer
        self.vector_indexer = None
        if enable_vector_index:
            try:
                from .vector_indexer import VectorIndexer
                self.vector_indexer = VectorIndexer()
                print("✅ Vector indexer initialized successfully")
            except Exception as e:
                print(f"❌ Could not initialize vector indexer: {e}")
        
        # Initialize dependency graph builder
        self.dependency_graph_builder = None
        if enable_dependency_graph:
            try:
                from .dependency_graph import DependencyGraphBuilder
                self.dependency_graph_builder = DependencyGraphBuilder()
                print("✅ Dependency graph builder initialized successfully")
            except Exception as e:
                print(f"❌ Could not initialize dependency graph builder: {e}")
        
        # File patterns to ignore
        self.ignore_patterns = {
            r'\.git/', r'node_modules/', r'\.env', r'\.DS_Store',
            r'\.idea/', r'\.vscode/', r'__pycache__/', r'\.pyc$',
            r'\.pyo$', r'\.pyd$', r'\.so$', r'\.dylib$', r'\.dll$',
            r'\.exe$', r'\.bin$', r'\.zip$', r'\.tar$', r'\.gz$',
            r'\.rar$', r'\.7z$', r'\.pdf$', r'\.doc$', r'\.docx$',
            r'\.xls$', r'\.xlsx$', r'\.ppt$', r'\.pptx$', r'\.jpg$',
            r'\.jpeg$', r'\.png$', r'\.gif$', r'\.ico$', r'\.svg$',
            r'\.mp3$', r'\.mp4$', r'\.mov$', r'\.avi$', r'\.wmv$',
        }
        self.ignore_regex = re.compile('|'.join(self.ignore_patterns))

    def _get_parser_for_file(self, file_path: Path) -> Optional[Parser]:
        """Get the appropriate parser for a file based on its extension."""
        ext_to_lang = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.tsx': 'tsx',
        }
        lang = ext_to_lang.get(file_path.suffix.lower())
        if lang and lang in LANGUAGES:
            try:
                # Create parser and set language using the modern API
                parser = Parser()
                parser.set_language(LANGUAGES[lang])
                return parser
            except Exception as e:
                print(f"❌ Error creating parser for {lang}: {e}")
                return None
        return None

    def _is_large_file(self, file_path: Path, max_size_mb: int = 1) -> bool:
        """Check if a file is considered 'large' and needs chunking."""
        return file_path.stat().st_size > (max_size_mb * 1024 * 1024)

    def _chunk_large_file(self, file_path: Path, content: str, max_chunk_size: int = 1000) -> List[str]:
        """Break down large files into manageable chunks."""
        lines = content.split('\n')
        chunks = []
        current_chunk = []
        current_size = 0
        
        for line in lines:
            if current_size + len(line) > max_chunk_size and current_chunk:
                chunks.append('\n'.join(current_chunk))
                current_chunk = [line]
                current_size = len(line)
            else:
                current_chunk.append(line)
                current_size += len(line)
        
        if current_chunk:
            chunks.append('\n'.join(current_chunk))
        
        return chunks

    def _extract_docstring(self, node: Node, source_code: bytes) -> Optional[str]:
        """Extract docstring from a node if present."""
        # Look for docstring nodes (varies by language)
        for child in node.children:
            if child.type in ['string', 'string_literal', 'comment']:
                docstring = source_code[child.start_byte:child.end_byte].decode('utf-8')
                # Clean up docstring
                docstring = docstring.strip('"\'`')
                if docstring and len(docstring) > 10:  # Minimum meaningful length
                    return docstring
        return None

    def _get_parent_symbol(self, node: Node, source_code: bytes) -> Optional[str]:
        """Get the parent symbol name for a node."""
        # Walk up the tree to find function/class definitions
        current = node.parent
        while current:
            if current.type in ['function_definition', 'method_definition', 'class_definition', 'function_declaration', 'method_declaration', 'class_declaration']:
                # Find the name node
                for child in current.children:
                    if child.type == 'identifier':
                        return source_code[child.start_byte:child.end_byte].decode('utf-8')
            current = current.parent
        return None

    def _get_node_name(self, node: Node, src: bytes) -> Optional[str]:
        """
        Return the identifier text for a def/class/function/var node.
        Handles JS/TS ('identifier'), Python ('name'), and others.
        """
        for child in node.children:
            if child.type in {"identifier", "property_identifier", "type_identifier", "name"}:
                return src[child.start_byte:child.end_byte].decode("utf-8")
        return None

    def parse_file(self, file_path: Path) -> List[CodeChunk]:
        """Parse a file into code chunks using Tree-Sitter or fallback to text-based parsing."""
        # Try Tree-sitter first
        parser = self._get_parser_for_file(file_path)
        if parser:
            try:
                with open(file_path, 'rb') as f:
                    source_code = f.read()
                tree = parser.parse(source_code)
                if tree and tree.root_node:
                    print(f"✅ Tree-sitter parsed {file_path}: {tree.root_node.type}")
                    chunks = self._process_ast_node(
                        tree.root_node, 
                        source_code, 
                        str(file_path)
                    )
                    if chunks:
                        print(f"Generated {len(chunks)} chunks from {file_path}")
                        return chunks
            except Exception as e:
                print(f"⚠️ Tree-sitter failed for {file_path}: {e}")
        
        # Fallback to text-based parsing
        print(f"📝 Using text-based parsing for {file_path}")
        return self._parse_file_text_based(file_path)
    
    def _parse_file_text_based(self, file_path: Path) -> List[CodeChunk]:
        """Fallback text-based parsing when Tree-sitter is not available."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if not content.strip():
                return []
            
            chunks = []
            lines = content.split('\n')
            
            # Simple heuristic-based chunking
            current_chunk_start = 1
            current_chunk_lines = []
            current_function_or_class = None
            
            i = 0
            while i < len(lines):
                line = lines[i].strip()
                
                # Function/class detection
                if line.startswith(('def ', 'class ', 'function ', 'const ', 'let ', 'var ')):
                    # Save previous chunk if it exists
                    if current_chunk_lines:
                        chunk_content = '\n'.join(current_chunk_lines)
                        if chunk_content.strip():
                            chunks.append(CodeChunk(
                                id=f"{file_path}:{current_chunk_start}:{i}",
                                path=str(file_path),
                                start_line=current_chunk_start,
                                end_line=i,
                                ast_type="function" if "def " in line or "function" in line else "text_block",
                                content=chunk_content,
                                parent_symbol=current_function_or_class
                            ))
                    
                    # Start new chunk
                    current_chunk_start = i + 1
                    current_chunk_lines = [lines[i]]
                    
                    # Extract function/class name
                    if line.startswith(('def ', 'function ')):
                        parts = line.split('(')[0].split()
                        if len(parts) >= 2:
                            current_function_or_class = parts[1]
                    elif line.startswith('class '):
                        parts = line.split(':')[0].split()
                        if len(parts) >= 2:
                            current_function_or_class = parts[1]
                else:
                    current_chunk_lines.append(lines[i])
                
                i += 1
            
            # Add final chunk
            if current_chunk_lines:
                chunk_content = '\n'.join(current_chunk_lines)
                if chunk_content.strip():
                    chunks.append(CodeChunk(
                        id=f"{file_path}:{current_chunk_start}:{len(lines)}",
                        path=str(file_path),
                        start_line=current_chunk_start,
                        end_line=len(lines),
                        ast_type="text_block",
                        content=chunk_content,
                        parent_symbol=current_function_or_class
                    ))
            
            # If no meaningful chunks were found, create one big chunk
            if not chunks:
                chunks.append(CodeChunk(
                    id=f"{file_path}:1:{len(lines)}",
                    path=str(file_path),
                    start_line=1,
                    end_line=len(lines),
                    ast_type="file",
                    content=content
                ))
            
            return chunks
            
        except Exception as e:
            print(f"❌ Error in text-based parsing for {file_path}: {e}")
            return []

    def _process_ast_node(
        self,
        node: Node,
        source_code: bytes,
        file_path: str,
        line_offset: int = 0,
        parent_symbol: Optional[str] = None,
    ) -> List[CodeChunk]:
        """Process an AST node and extract code chunks."""
        chunks = []
        
        # Define significant node types that should become chunks
        significant_types = {
            'function_definition', 'method_definition', 'class_definition',
            'function_declaration', 'method_declaration', 'class_declaration',
            'module', 'program', 'source_file'
        }
        
        name_here = None
        if node.type in significant_types:
            name_here = self._get_node_name(node, source_code)
            docstring = self._extract_docstring(node, source_code)
            
            # Create chunk
            chunk = CodeChunk(
                id=f"{file_path}:{node.start_point[0] + line_offset}:{node.end_point[0] + line_offset}",
                path=file_path,
                start_line=node.start_point[0] + line_offset,
                end_line=node.end_point[0] + line_offset,
                ast_type=node.type,
                content=source_code[node.start_byte:node.end_byte].decode("utf-8"),
                parent_symbol=parent_symbol,
                docstring=docstring
            )
            chunks.append(chunk)
        
        current_parent_symbol = name_here or parent_symbol

        # Process children
        for child in node.children:
            chunks.extend(self._process_ast_node(child, source_code, file_path, line_offset, current_parent_symbol))
        
        return chunks

    def get_source_files(self, repo_path: Path) -> List[Path]:
        """Get all source files in the repository."""
        source_extensions = {
            ".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".java", ".cpp", ".c", ".h",
            ".hpp", ".cs", ".rb", ".php", ".swift", ".kt", ".rs", ".css"
        }
        
        source_files = []
        for file_path in repo_path.rglob('*'):
            if (file_path.is_file() and 
                file_path.suffix in source_extensions and 
                not self.ignore_regex.search(str(file_path))):
                source_files.append(file_path)
        
        return source_files

    async def analyze_repository(self, repo_path: Path) -> Dict[str, Any]:
        """Analyze a repository and return structured data."""
        print(f"Starting analysis of repository: {repo_path}")
        
        # Get all source files
        source_files = self.get_source_files(repo_path)
        print(f"Found {len(source_files)} source files")
        
        # Parse all files into chunks
        all_chunks = []
        for file_path in source_files:
            chunks = self.parse_file(file_path)
            all_chunks.extend(chunks)
            print(f"Parsed {file_path.name}: {len(chunks)} chunks")
        
        print(f"Total chunks generated: {len(all_chunks)}")
        
        # Index chunks lexically if indexer is available
        if self.lexical_indexer and all_chunks:
            print("Indexing chunks for lexical search...")
            self.lexical_indexer.index_chunks(all_chunks)
            index_stats = self.lexical_indexer.get_index_stats()
            print(f"Lexical index stats: {index_stats}")
        
        # Index chunks semantically if indexer is available
        vector_index_success = False
        if self.vector_indexer and all_chunks:
            print("Indexing chunks for semantic search...")
            vector_index_success = await self.vector_indexer.index_chunks(all_chunks)
            if vector_index_success:
                vector_stats = self.vector_indexer.get_collection_stats()
                print(f"Vector index stats: {vector_stats}")
        
        # Build dependency graph if builder is available
        dependency_graph = None
        dependency_graph_success = False
        if self.dependency_graph_builder and all_chunks:
            print("Building dependency graph...")
            dependency_graph = self.dependency_graph_builder.build_dependency_graph(all_chunks, str(repo_path))
            dependency_graph_success = dependency_graph is not None
            if dependency_graph_success:
                print(f"Dependency graph: {dependency_graph.number_of_nodes()} nodes, {dependency_graph.number_of_edges()} edges")
        
        # Group chunks by file
        chunks_by_file = {}
        for chunk in all_chunks:
            if chunk.path not in chunks_by_file:
                chunks_by_file[chunk.path] = []
            chunks_by_file[chunk.path].append(chunk)
        
        # Create file summaries (placeholder for now)
        file_summaries = []
        for file_path, chunks in chunks_by_file.items():
            # Sort chunks by start line
            chunks.sort(key=lambda c: c.start_line)
            
            file_summary = FileSummary(
                path=file_path,
                summary=f"File with {len(chunks)} code chunks",  # Placeholder
                chunks=chunks,
                functions=[chunk for chunk in chunks if 'function' in chunk.ast_type.lower()]
            )
            file_summaries.append(file_summary)
        
        # Create module structure
        modules = self._create_module_structure(file_summaries, str(repo_path))
        
        # Get centrality metrics if dependency graph is available
        centrality_metrics = {}
        if dependency_graph_success and self.dependency_graph_builder:
            centrality_metrics = self.dependency_graph_builder.compute_centrality_metrics()
        
        return {
            "repository": str(repo_path),
            "total_files": len(source_files),
            "total_chunks": len(all_chunks),
            "modules": modules,
            "chunks": [asdict(chunk) for chunk in all_chunks],
            "lexical_index_available": self.lexical_indexer is not None,
            "vector_index_available": self.vector_indexer is not None and vector_index_success,
            "dependency_graph_available": self.dependency_graph_builder is not None and dependency_graph_success,
            "centrality_metrics": centrality_metrics
        }

    def _create_module_structure(self, file_summaries: List[FileSummary], repo_path: str) -> List[ModuleSummary]:
        """Create a hierarchical module structure from file summaries."""
        # Group files by directory
        files_by_dir = {}
        for file_summary in file_summaries:
            file_path = Path(file_summary.path)
            relative_path = file_path.relative_to(Path(repo_path))
            dir_path = str(relative_path.parent)
            
            if dir_path not in files_by_dir:
                files_by_dir[dir_path] = []
            files_by_dir[dir_path].append(file_summary)
        
        # Create module summaries
        modules = []
        for dir_path, files in files_by_dir.items():
            module_summary = ModuleSummary(
                path=dir_path or "root",
                summary=f"Module with {len(files)} files",  # Placeholder
                files=files,
                submodules=[]  # Will be populated recursively
            )
            modules.append(module_summary)
        
        return modules 

    def search_code(
        self, 
        query: str, 
        search_type: str = "bm25", 
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Search code using the lexical indexer."""
        if not self.lexical_indexer:
            print("Lexical indexer not available")
            return []
        
        return self.lexical_indexer.search(query, limit=limit, search_type=search_type)
    
    def search_by_symbol(self, symbol: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search for code chunks containing a specific symbol."""
        if not self.lexical_indexer:
            print("Lexical indexer not available")
            return []
        
        return self.lexical_indexer.search_by_symbol(symbol, limit=limit)
    
    def search_by_file(self, file_path: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get all code chunks from a specific file."""
        if not self.lexical_indexer:
            print("Lexical indexer not available")
            return []
        
        return self.lexical_indexer.search_by_file(file_path, limit=limit) 
    
    async def semantic_search(
        self, 
        query: str, 
        limit: int = 20,
        score_threshold: float = 0.7,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Search code using semantic vector similarity."""
        if not self.vector_indexer:
            print("Vector indexer not available")
            return []
        
        return await self.vector_indexer.semantic_search(
            query=query, 
            limit=limit, 
            score_threshold=score_threshold, 
            filters=filters
        )
    
    async def find_similar_chunks(
        self, 
        chunk_id: str, 
        limit: int = 10,
        score_threshold: float = 0.8
    ) -> List[Dict[str, Any]]:
        """Find chunks semantically similar to a given chunk."""
        if not self.vector_indexer:
            print("Vector indexer not available")
            return []
        
        return await self.vector_indexer.find_similar_chunks(
            chunk_id=chunk_id, 
            limit=limit, 
            score_threshold=score_threshold
        )
    
    async def find_entry_points(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Find potential entry points in the codebase using semantic search."""
        if not self.vector_indexer:
            print("Vector indexer not available")
            return []
        
        return await self.vector_indexer.find_entry_points(limit=limit)
    
    async def analyze_execution_flows(
        self, 
        entry_points: List[str], 
        depth: int = 3
    ) -> Dict[str, Any]:
        """Analyze execution flows starting from entry points."""
        if not self.vector_indexer:
            print("Vector indexer not available")
            return {}
        
        return await self.vector_indexer.analyze_execution_flows(
            entry_points=entry_points, 
            depth=depth
        )
    
    async def hybrid_search(
        self,
        query: str,
        limit: int = 20,
        lexical_weight: float = 0.3,
        semantic_weight: float = 0.7
    ) -> List[Dict[str, Any]]:
        """Perform hybrid search combining lexical and semantic results."""
        results = []
        
        # Get lexical results
        lexical_results = []
        if self.lexical_indexer:
            lexical_results = self.search_code(query, search_type="bm25", limit=limit)
            for result in lexical_results:
                result["search_score"] = result.get("score", 0) * lexical_weight
                result["search_method"] = "lexical"
        
        # Get semantic results
        semantic_results = []
        if self.vector_indexer:
            semantic_results = await self.semantic_search(query, limit=limit)
            for result in semantic_results:
                result["search_score"] = result.get("score", 0) * semantic_weight
                result["search_method"] = "semantic"
        
        # Combine and deduplicate results
        seen_ids = set()
        combined_results = []
        
        # Add all results
        for result in lexical_results + semantic_results:
            if result["id"] not in seen_ids:
                combined_results.append(result)
                seen_ids.add(result["id"])
            else:
                # If we've seen this chunk, boost its score
                for existing in combined_results:
                    if existing["id"] == result["id"]:
                        existing["search_score"] += result["search_score"] * 0.5  # Boost for appearing in both
                        existing["search_method"] = "hybrid"
                        break
        
        # Sort by combined score
        combined_results.sort(key=lambda x: x["search_score"], reverse=True)
        
        return combined_results[:limit] 

    def query_dependencies(
        self, 
        node_id: str, 
        direction: str = "both", 
        depth: int = 1
    ) -> List[Dict[str, Any]]:
        """Query dependencies using the dependency graph."""
        if not self.dependency_graph_builder:
            print("Dependency graph builder not available")
            return []
        
        return self.dependency_graph_builder.query_dependencies(node_id, direction, depth)
    
    def get_call_graph(self):
        """Get the call graph from the dependency graph builder."""
        if not self.dependency_graph_builder:
            print("Dependency graph builder not available")
            return None
        
        return self.dependency_graph_builder.get_call_graph()
    
    def get_import_graph(self):
        """Get the import graph from the dependency graph builder."""
        if not self.dependency_graph_builder:
            print("Dependency graph builder not available")
            return None
        
        return self.dependency_graph_builder.get_import_graph()
    
    def get_dependency_graph(self):
        """Get the full dependency graph."""
        if not self.dependency_graph_builder:
            print("Dependency graph builder not available")
            return None
        
        return self.dependency_graph_builder.graph
    
    def get_centrality_metrics(self) -> Dict[str, Dict[str, float]]:
        """Get centrality metrics for the call graph."""
        if not self.dependency_graph_builder:
            print("Dependency graph builder not available")
            return {}
        
        return self.dependency_graph_builder.compute_centrality_metrics() 