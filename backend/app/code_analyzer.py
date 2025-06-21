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

LANGUAGES = {
    "python":     Language(tspy.language()),
    "javascript": Language(tsjs.language()),
    "typescript": Language(tst.language_typescript()),
    "tsx":        Language(tst.language_tsx()),
}

class CodeAnalyzer:
    def __init__(self, cache_dir: Optional[str] = None):
        """Initialize the code analyzer with Tree-Sitter support."""
        self.cache_dir = cache_dir or os.path.join(tempfile.gettempdir(), "halos_code_cache")
        self.summary_cache_dir = os.path.join(self.cache_dir, "summaries")
        self.chunk_cache_dir = os.path.join(self.cache_dir, "chunks")
        
        os.makedirs(self.cache_dir, exist_ok=True)
        os.makedirs(self.summary_cache_dir, exist_ok=True)
        os.makedirs(self.chunk_cache_dir, exist_ok=True)
        
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
        if lang:
            return Parser(LANGUAGES[lang])
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

    def parse_file(self, file_path: Path) -> List[CodeChunk]:
        """Parse a file into code chunks using Tree-Sitter."""
        parser = self._get_parser_for_file(file_path)
        if not parser:
            return []
        try:
            with open(file_path, 'rb') as f:
                source_code = f.read()
            tree = parser.parse(source_code)
            if not tree:
                print(f"No parse tree generated for file: {file_path}")
                return []
            print(f"Root node type for {file_path}: {tree.root_node.type}")
            # Collect all unique node types in the AST
            def collect_node_types(node, types):
                types.add(node.type)
                for child in node.children:
                    collect_node_types(child, types)
            node_types = set()
            collect_node_types(tree.root_node, node_types)
            print(f"Unique node types in {file_path}: {sorted(node_types)}")
            chunks = []
            # If file is large, chunk it first
            if self._is_large_file(file_path):
                file_chunks = self._chunk_large_file(file_path, source_code.decode('utf-8'))
                for i, chunk_content in enumerate(file_chunks):
                    chunk_tree = parser.parse(chunk_content.encode('utf-8'))
                    if chunk_tree:
                        chunks.extend(self._process_ast_node(
                            chunk_tree.root_node, 
                            chunk_content.encode('utf-8'), 
                            str(file_path),
                            i * 1000  # Approximate line offset
                        ))
            else:
                chunks = self._process_ast_node(
                    tree.root_node, 
                    source_code, 
                    str(file_path)
                )
            return chunks
        except Exception as e:
            print(f"Error parsing file {file_path}: {e}")
            return []

    def _process_ast_node(self, node: Node, source_code: bytes, file_path: str, line_offset: int = 0) -> List[CodeChunk]:
        """Process an AST node and extract code chunks."""
        chunks = []
        
        # Define significant node types that should become chunks
        significant_types = {
            'function_definition', 'method_definition', 'class_definition',
            'function_declaration', 'method_declaration', 'class_declaration',
            'module', 'program', 'source_file'
        }
        
        if node.type in significant_types:
            # Extract content for this node
            content = source_code[node.start_byte:node.end_byte].decode('utf-8')
            
            # Get metadata
            docstring = self._extract_docstring(node, source_code)
            parent_symbol = self._get_parent_symbol(node, source_code)
            
            # Create chunk
            chunk = CodeChunk(
                id=f"{file_path}:{node.start_point[0] + line_offset}:{node.end_point[0] + line_offset}",
                path=file_path,
                start_line=node.start_point[0] + line_offset,
                end_line=node.end_point[0] + line_offset,
                ast_type=node.type,
                content=content,
                parent_symbol=parent_symbol,
                docstring=docstring
            )
            chunks.append(chunk)
        
        # Process children
        for child in node.children:
            chunks.extend(self._process_ast_node(child, source_code, file_path, line_offset))
        
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
        
        return {
            "repository": str(repo_path),
            "total_files": len(source_files),
            "total_chunks": len(all_chunks),
            "modules": modules,
            "chunks": [asdict(chunk) for chunk in all_chunks]
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