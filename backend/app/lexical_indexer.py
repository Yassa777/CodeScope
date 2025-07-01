import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Set
from dataclasses import asdict
import tempfile

from whoosh import fields, index
from whoosh.index import open_dir
from whoosh.qparser import QueryParser, MultifieldParser
from whoosh.query import Term, And, Or, Phrase
from whoosh.scoring import BM25F
from whoosh.analysis import StandardAnalyzer, KeywordAnalyzer
from whoosh.filedb.filestore import FileStorage

from .code_analyzer import CodeChunk, FileSummary, ModuleSummary


class LexicalIndexer:
    """Lexical indexer using Whoosh for BM25 and exact matching."""
    
    def __init__(self, index_dir: Optional[str] = None):
        """Initialize the lexical indexer."""
        self.index_dir = index_dir or os.path.join(tempfile.gettempdir(), "halos_lexical_index")
        os.makedirs(self.index_dir, exist_ok=True)
        
        # Define schema for code chunks
        self.schema = fields.Schema(
            id=fields.ID(stored=True, unique=True),
            path=fields.TEXT(stored=True, analyzer=KeywordAnalyzer()),
            content=fields.TEXT(stored=True, analyzer=StandardAnalyzer()),
            ast_type=fields.KEYWORD(stored=True),
            start_line=fields.NUMERIC(stored=True),
            end_line=fields.NUMERIC(stored=True),
            parent_symbol=fields.TEXT(stored=True, analyzer=KeywordAnalyzer()),
            docstring=fields.TEXT(stored=True, analyzer=StandardAnalyzer()),
            
            # Additional searchable fields
            symbols=fields.TEXT(analyzer=KeywordAnalyzer()),  # Extracted identifiers
            comments=fields.TEXT(analyzer=StandardAnalyzer()),  # Comments
            imports=fields.TEXT(analyzer=KeywordAnalyzer()),  # Import statements
            
            # Exact match fields
            exact_content=fields.KEYWORD(),  # For exact string matching
            exact_symbols=fields.KEYWORD(),  # For exact symbol matching
        )
        
        self.ix = None
        self._create_or_open_index()
    
    def _create_or_open_index(self):
        """Create a new index or open existing one."""
        try:
            if index.exists_in(self.index_dir):
                self.ix = index.open_dir(self.index_dir)
                print(f"✅ Opened existing lexical index at {self.index_dir}")
            else:
                self.ix = index.create_in(self.index_dir, self.schema)
                print(f"✅ Created new lexical index at {self.index_dir}")
        except Exception as e:
            print(f"❌ Error with index: {e}")
            # Fallback: create new index
            try:
                self.ix = index.create_in(self.index_dir, self.schema)
                print(f"✅ Created fallback lexical index at {self.index_dir}")
            except Exception as e2:
                print(f"❌ Failed to create fallback index: {e2}")
                self.ix = None
    
    def _extract_symbols(self, content: str) -> Set[str]:
        """Extract identifiers/symbols from code content."""
        # Simple regex-based symbol extraction
        # This catches most identifiers in various languages
        symbol_pattern = r'\b[a-zA-Z_][a-zA-Z0-9_]*\b'
        symbols = set(re.findall(symbol_pattern, content))
        
        # Filter out common keywords and short symbols
        keywords = {
            'if', 'else', 'for', 'while', 'do', 'try', 'catch', 'finally',
            'function', 'class', 'def', 'var', 'let', 'const', 'return',
            'import', 'from', 'as', 'export', 'default', 'public', 'private',
            'protected', 'static', 'async', 'await', 'true', 'false', 'null',
            'undefined', 'this', 'self', 'super', 'new', 'delete', 'typeof',
            'instanceof', 'in', 'of', 'and', 'or', 'not', 'is', 'None',
            'True', 'False', 'with', 'yield', 'lambda', 'pass', 'break',
            'continue', 'raise', 'except', 'assert', 'global', 'nonlocal'
        }
        
        return {s for s in symbols if len(s) > 2 and s.lower() not in keywords}
    
    def _extract_comments(self, content: str) -> str:
        """Extract comments from code content."""
        comments = []
        
        # Single line comments (// and #)
        single_line_patterns = [
            r'//.*$',  # JavaScript/TypeScript
            r'#.*$',   # Python
        ]
        
        # Multi-line comments (/* */ and """ """)
        multi_line_patterns = [
            r'/\*.*?\*/',  # JavaScript/TypeScript
            r'""".*?"""',  # Python docstrings
            r"'''.*?'''",  # Python docstrings
        ]
        
        for pattern in single_line_patterns:
            comments.extend(re.findall(pattern, content, re.MULTILINE))
        
        for pattern in multi_line_patterns:
            comments.extend(re.findall(pattern, content, re.DOTALL))
        
        return ' '.join(comments)
    
    def _extract_imports(self, content: str) -> Set[str]:
        """Extract import statements from code content."""
        imports = set()
        
        # Python imports
        python_imports = re.findall(r'(?:from\s+(\S+)\s+)?import\s+([^\n]+)', content)
        for from_module, import_items in python_imports:
            if from_module:
                imports.add(from_module)
            # Split import items and clean them
            items = [item.strip().split(' as ')[0] for item in import_items.split(',')]
            imports.update(items)
        
        # JavaScript/TypeScript imports
        js_imports = re.findall(r'import\s+(?:{[^}]+}|\S+)\s+from\s+[\'"]([^\'"]+)[\'"]', content)
        imports.update(js_imports)
        
        # ES6 imports
        es6_imports = re.findall(r'import\s+[\'"]([^\'"]+)[\'"]', content)
        imports.update(es6_imports)
        
        return imports
    
    def index_chunks(self, chunks: List[CodeChunk]) -> None:
        """Index a list of code chunks."""
        if not self.ix:
            return
        
        writer = self.ix.writer()
        
        try:
            for chunk in chunks:
                # Extract additional searchable content
                symbols = self._extract_symbols(chunk.content)
                comments = self._extract_comments(chunk.content)
                imports = self._extract_imports(chunk.content)
                
                # Add document to index
                writer.add_document(
                    id=chunk.id,
                    path=chunk.path,
                    content=chunk.content,
                    ast_type=chunk.ast_type,
                    start_line=chunk.start_line,
                    end_line=chunk.end_line,
                    parent_symbol=chunk.parent_symbol or "",
                    docstring=chunk.docstring or "",
                    
                    # Additional fields
                    symbols=" ".join(symbols),
                    comments=comments,
                    imports=" ".join(imports),
                    
                    # Exact match fields
                    exact_content=chunk.content,
                    exact_symbols=" ".join(symbols),
                )
            
            writer.commit()
            print(f"Indexed {len(chunks)} code chunks")
            
        except Exception as e:
            writer.cancel()
            print(f"Error indexing chunks: {e}")
    
    def search(
        self, 
        query: str, 
        limit: int = 20,
        search_type: str = "bm25"  # "bm25", "exact", "mixed"
    ) -> List[Dict[str, Any]]:
        """Search the index using various strategies."""
        if not self.ix:
            return []
        
        results = []
        
        with self.ix.searcher(weighting=BM25F()) as searcher:
            if search_type == "exact":
                results = self._exact_search(searcher, query, limit)
            elif search_type == "bm25":
                results = self._bm25_search(searcher, query, limit)
            elif search_type == "mixed":
                # Combine exact and BM25 results
                exact_results = self._exact_search(searcher, query, limit // 2)
                bm25_results = self._bm25_search(searcher, query, limit // 2)
                
                # Merge and deduplicate
                seen_ids = set()
                for result in exact_results + bm25_results:
                    if result['id'] not in seen_ids:
                        results.append(result)
                        seen_ids.add(result['id'])
                        if len(results) >= limit:
                            break
        
        return results
    
    def _exact_search(self, searcher, query: str, limit: int) -> List[Dict[str, Any]]:
        """Perform exact string matching."""
        results = []
        
        # Search in exact content
        exact_query = Term("exact_content", query)
        exact_results = searcher.search(exact_query, limit=limit)
        
        for hit in exact_results:
            results.append({
                'id': hit['id'],
                'path': hit['path'],
                'content': hit['content'],
                'ast_type': hit['ast_type'],
                'start_line': hit['start_line'],
                'end_line': hit['end_line'],
                'parent_symbol': hit['parent_symbol'],
                'docstring': hit['docstring'],
                'score': hit.score,
                'search_type': 'exact'
            })
        
        return results
    
    def _bm25_search(self, searcher, query: str, limit: int) -> List[Dict[str, Any]]:
        """Perform BM25 search across multiple fields."""
        results = []
        
        # Create multi-field parser
        parser = MultifieldParser(
            ["content", "symbols", "comments", "docstring", "parent_symbol"],
            self.ix.schema
        )
        
        try:
            parsed_query = parser.parse(query)
            search_results = searcher.search(parsed_query, limit=limit)
            
            for hit in search_results:
                results.append({
                    'id': hit['id'],
                    'path': hit['path'],
                    'content': hit['content'],
                    'ast_type': hit['ast_type'],
                    'start_line': hit['start_line'],
                    'end_line': hit['end_line'],
                    'parent_symbol': hit['parent_symbol'],
                    'docstring': hit['docstring'],
                    'score': hit.score,
                    'search_type': 'bm25'
                })
                
        except Exception as e:
            print(f"Error in BM25 search: {e}")
        
        return results
    
    def search_by_symbol(self, symbol: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search for chunks containing a specific symbol."""
        with self.ix.searcher() as searcher:
            # Search in exact symbols field
            symbol_query = Term("exact_symbols", symbol)
            results = searcher.search(symbol_query, limit=limit)
            
            return [{
                'id': hit['id'],
                'path': hit['path'],
                'content': hit['content'],
                'ast_type': hit['ast_type'],
                'start_line': hit['start_line'],
                'end_line': hit['end_line'],
                'parent_symbol': hit['parent_symbol'],
                'docstring': hit['docstring'],
                'score': hit.score,
                'search_type': 'symbol'
            } for hit in results]
    
    def search_by_file(self, file_path: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get all chunks from a specific file."""
        with self.ix.searcher() as searcher:
            file_query = Term("path", file_path)
            results = searcher.search(file_query, limit=limit, sortedby="start_line")
            
            return [{
                'id': hit['id'],
                'path': hit['path'],
                'content': hit['content'],
                'ast_type': hit['ast_type'],
                'start_line': hit['start_line'],
                'end_line': hit['end_line'],
                'parent_symbol': hit['parent_symbol'],
                'docstring': hit['docstring'],
                'score': hit.score,
                'search_type': 'file'
            } for hit in results]
    
    def get_index_stats(self) -> Dict[str, Any]:
        """Get statistics about the index."""
        if not self.ix:
            return {}
        
        with self.ix.searcher() as searcher:
            return {
                'total_documents': searcher.doc_count(),
                'index_dir': self.index_dir,
                'schema_fields': list(self.ix.schema.names()),
            }
    
    def clear_index(self) -> None:
        """Clear the entire index."""
        if self.ix:
            writer = self.ix.writer()
            writer.commit(mergetype='CLEAR')
            print("Index cleared") 