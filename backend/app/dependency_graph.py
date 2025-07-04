import os
import re
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Set, Union
from dataclasses import dataclass, asdict
import json
import tempfile
import hashlib

import networkx as nx
import mgclient
from tree_sitter import Node

from .code_analyzer import CodeChunk, FileSummary, ModuleSummary


@dataclass
class DependencyEdge:
    """Represents a dependency relationship between code elements."""
    source_id: str
    target_id: str
    edge_type: str  # import, call, defined_in, writes_to, reads_from, test_of
    metadata: Dict[str, Any]
    confidence: float = 1.0


class DependencyGraphBuilder:
    """Builds dependency graphs from code chunks and stores them in Memgraph."""
    
    def __init__(
        self, 
        memgraph_host: str = "localhost",
        memgraph_port: int = 7687,
        memgraph_username: str = "",
        memgraph_password: str = ""
    ):
        """Initialize the dependency graph builder."""
        self.memgraph_host = memgraph_host
        self.memgraph_port = memgraph_port
        self.memgraph_username = memgraph_username
        self.memgraph_password = memgraph_password
        
        # NetworkX graph for local analysis
        self.graph = nx.DiGraph()
        
        # Symbol table: symbol_name -> chunk_id
        self.symbol_table = {}
        
        # Import table: file_path -> [imported_modules]
        self.import_table = {}
        
        # Memgraph connection
        self.mg_client = None
        self._connect_memgraph()
    
    def _connect_memgraph(self):
        """Connect to Memgraph database."""
        try:
            self.mg_client = mgclient.connect(
                host=self.memgraph_host,
                port=self.memgraph_port,
                username=self.memgraph_username,
                password=self.memgraph_password
            )
            print(f"Connected to Memgraph at {self.memgraph_host}:{self.memgraph_port}")
            
            # Create indexes for performance
            self._create_indexes()
            
        except Exception as e:
            print(f"Warning: Could not connect to Memgraph: {e}")
            self.mg_client = None
    
    def _create_indexes(self):
        """Create indexes in Memgraph for better performance."""
        if not self.mg_client:
            return
        
        try:
            cursor = self.mg_client.cursor()
            
            # Create indexes
            indexes = [
                "CREATE INDEX ON :Chunk(id);",
                "CREATE INDEX ON :File(path);",
                "CREATE INDEX ON :Symbol(name);",
                "CREATE INDEX ON :Module(name);"
            ]
            
            for index_query in indexes:
                try:
                    cursor.execute(index_query)
                except Exception:
                    pass  # Index might already exist
            
            cursor.close()
            
        except Exception as e:
            print(f"Error creating indexes: {e}")
    
    def build_dependency_graph(self, chunks: List[CodeChunk], repo_path: str) -> nx.DiGraph:
        """Build comprehensive dependency graph from code chunks."""
        print(f"Building dependency graph for {len(chunks)} chunks...")
        
        # Clear existing graph
        self.graph.clear()
        self.symbol_table.clear()
        self.import_table.clear()
        
        # Step 1: Add all chunks as nodes and build symbol table
        self._add_chunk_nodes(chunks)
        
        # Step 2: Extract imports for each file
        self._extract_imports(chunks, repo_path)
        
        # Step 3: Detect function/method calls
        self._detect_calls(chunks)
        
        # Step 4: Add containment relationships
        self._add_containment_relationships(chunks)
        
        # Step 5: Detect variable reads/writes
        self._detect_variable_access(chunks)
        
        # Step 6: Detect test relationships
        self._detect_test_relationships(chunks, repo_path)
        
        # Step 7: Sync to Memgraph if available
        if self.mg_client:
            self._sync_to_memgraph()
        
        print(f"Dependency graph built: {self.graph.number_of_nodes()} nodes, {self.graph.number_of_edges()} edges")
        return self.graph
    
    def _add_chunk_nodes(self, chunks: List[CodeChunk]):
        """Add all chunks as nodes and build symbol table."""
        for chunk in chunks:
            # Add chunk node
            self.graph.add_node(
                chunk.id,
                type="chunk",
                ast_type=chunk.ast_type,
                path=chunk.path,
                start_line=chunk.start_line,
                end_line=chunk.end_line,
                parent_symbol=chunk.parent_symbol,
                content=chunk.content[:500],  # Truncated for storage
                hash=chunk.hash
            )
            
            # Build symbol table for functions/classes
            if chunk.ast_type in ['function_definition', 'method_definition', 'class_definition']:
                symbol_name = self._extract_symbol_name(chunk.content)
                if symbol_name:
                    self.symbol_table[symbol_name] = chunk.id
                    
                    # Also add qualified name if inside a class
                    if chunk.parent_symbol:
                        qualified_name = f"{chunk.parent_symbol}.{symbol_name}"
                        self.symbol_table[qualified_name] = chunk.id
    
    def _extract_symbol_name(self, content: str) -> Optional[str]:
        """Extract symbol name from chunk content."""
        # Simple regex-based extraction (could be improved with AST)
        patterns = [
            r'def\s+(\w+)\s*\(',      # Python functions
            r'class\s+(\w+)\s*[:\(]', # Python classes
            r'function\s+(\w+)\s*\(', # JavaScript functions
            r'class\s+(\w+)\s*{',     # JavaScript classes
        ]
        
        for pattern in patterns:
            match = re.search(pattern, content)
            if match:
                return match.group(1)
        
        return None
    
    def _extract_imports(self, chunks: List[CodeChunk], repo_path: str):
        """Extract import relationships."""
        for chunk in chunks:
            if 'import' in chunk.content.lower():
                imports = self._parse_imports(chunk.content, chunk.path)
                
                if imports:
                    self.import_table[chunk.path] = imports
                    
                    # Add import edges
                    for imported_module in imports:
                        target_file = self._resolve_import_path(imported_module, chunk.path, repo_path)
                        
                        if target_file:
                            edge = DependencyEdge(
                                source_id=chunk.id,
                                target_id=target_file,
                                edge_type="import",
                                metadata={
                                    "module": imported_module,
                                    "import_type": "module"
                                }
                            )
                            
                            self.graph.add_edge(
                                chunk.id,
                                target_file,
                                type="import",
                                module=imported_module,
                                confidence=0.9
                            )
    
    def _parse_imports(self, content: str, file_path: str) -> List[str]:
        """Parse import statements from code content."""
        imports = []
        
        # Python imports
        python_patterns = [
            r'from\s+([^\s]+)\s+import',  # from module import
            r'import\s+([^\s,]+)',        # import module
        ]
        
        # JavaScript/TypeScript imports
        js_patterns = [
            r'import\s+.*?\s+from\s+[\'"]([^\'"]+)[\'"]',  # import ... from 'module'
            r'import\s+[\'"]([^\'"]+)[\'"]',               # import 'module'
            r'require\([\'"]([^\'"]+)[\'"]\)',            # require('module')
        ]
        
        all_patterns = python_patterns + js_patterns
        
        for pattern in all_patterns:
            matches = re.findall(pattern, content, re.MULTILINE)
            imports.extend(matches)
        
        # Clean up imports
        cleaned_imports = []
        for imp in imports:
            # Remove relative path indicators
            cleaned = imp.replace('./', '').replace('../', '')
            if cleaned and not cleaned.startswith('.'):
                cleaned_imports.append(cleaned)
        
        return cleaned_imports
    
    def _resolve_import_path(self, module_name: str, current_file: str, repo_path: str) -> Optional[str]:
        """Resolve import to actual file path."""
        # Simple resolution - could be enhanced with proper module resolution
        base_dir = Path(current_file).parent
        
        # Try common extensions
        extensions = ['.py', '.js', '.ts', '.tsx', '.jsx']
        
        for ext in extensions:
            possible_paths = [
                base_dir / f"{module_name}{ext}",
                base_dir / module_name / f"__init__{ext}",
                Path(repo_path) / f"{module_name.replace('.', '/')}{ext}",
            ]
            
            for path in possible_paths:
                if path.exists():
                    return str(path)
        
        return None
    
    def _detect_calls(self, chunks: List[CodeChunk]):
        """Detect function/method calls between chunks."""
        for chunk in chunks:
            calls = self._extract_function_calls(chunk.content)
            
            for call in calls:
                # Look up in symbol table
                target_chunk_id = self._resolve_call_target(call, chunk)
                
                if target_chunk_id:
                    self.graph.add_edge(
                        chunk.id,
                        target_chunk_id,
                        type="call",
                        function_name=call,
                        confidence=0.8
                    )
    
    def _extract_function_calls(self, content: str) -> List[str]:
        """Extract function calls from code content."""
        calls = []
        
        # Pattern for function calls: word followed by parentheses
        call_pattern = r'(\w+(?:\.\w+)*)\s*\('
        matches = re.findall(call_pattern, content)
        
        # Filter out common keywords and built-ins
        keywords = {
            'if', 'for', 'while', 'with', 'try', 'except', 'print', 'len', 'str',
            'int', 'float', 'list', 'dict', 'set', 'tuple', 'range', 'enumerate',
            'isinstance', 'hasattr', 'getattr', 'setattr'
        }
        
        for match in matches:
            call_name = match.split('.')[-1]  # Get the method name for qualified calls
            if call_name not in keywords and len(call_name) > 1:
                calls.append(match)
        
        return calls
    
    def _resolve_call_target(self, call: str, source_chunk: CodeChunk) -> Optional[str]:
        """Resolve a function call to its target chunk."""
        # Try exact match first
        if call in self.symbol_table:
            return self.symbol_table[call]
        
        # Try method calls (obj.method -> method)
        if '.' in call:
            method_name = call.split('.')[-1]
            if method_name in self.symbol_table:
                return self.symbol_table[method_name]
        
        # Try qualified names within the same parent
        if source_chunk.parent_symbol:
            qualified_call = f"{source_chunk.parent_symbol}.{call}"
            if qualified_call in self.symbol_table:
                return self.symbol_table[qualified_call]
        
        return None
    
    def _add_containment_relationships(self, chunks: List[CodeChunk]):
        """Add defined_in relationships for chunks within files/classes."""
        # Group chunks by file
        chunks_by_file = {}
        for chunk in chunks:
            if chunk.path not in chunks_by_file:
                chunks_by_file[chunk.path] = []
            chunks_by_file[chunk.path].append(chunk)
        
        # Add file nodes and containment edges
        for file_path, file_chunks in chunks_by_file.items():
            file_id = f"file:{file_path}"
            
            # Add file node
            self.graph.add_node(
                file_id,
                type="file",
                path=file_path,
                name=Path(file_path).name
            )
            
            # Add containment edges
            for chunk in file_chunks:
                self.graph.add_edge(
                    file_id,
                    chunk.id,
                    type="contains",
                    confidence=1.0
                )
                
                # Add parent-child relationships for nested definitions
                if chunk.parent_symbol:
                    parent_chunk_id = self.symbol_table.get(chunk.parent_symbol)
                    if parent_chunk_id and parent_chunk_id != chunk.id:
                        self.graph.add_edge(
                            parent_chunk_id,
                            chunk.id,
                            type="defined_in",
                            confidence=1.0
                        )
    
    def _detect_variable_access(self, chunks: List[CodeChunk]):
        """Detect variable reads and writes."""
        for chunk in chunks:
            variables = self._extract_variables(chunk.content)
            
            for var_name, access_type in variables:
                var_id = f"var:{var_name}:{chunk.path}"
                
                # Add variable node if not exists
                if not self.graph.has_node(var_id):
                    self.graph.add_node(
                        var_id,
                        type="variable",
                        name=var_name,
                        path=chunk.path
                    )
                
                # Add access edge
                if access_type == "write":
                    self.graph.add_edge(
                        chunk.id,
                        var_id,
                        type="writes_to",
                        confidence=0.7
                    )
                else:  # read
                    self.graph.add_edge(
                        var_id,
                        chunk.id,
                        type="reads_from",
                        confidence=0.6
                    )
    
    def _extract_variables(self, content: str) -> List[Tuple[str, str]]:
        """Extract variable assignments and usages."""
        variables = []
        
        # Simple patterns for variable assignment
        assignment_patterns = [
            r'(\w+)\s*=',           # variable assignment
            r'(\w+)\s*\+=',         # increment assignment
            r'(\w+)\s*-=',          # decrement assignment
        ]
        
        for pattern in assignment_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                if len(match) > 1 and not match[0].isupper():  # Skip constants
                    variables.append((match, "write"))
        
        return variables
    
    def _detect_test_relationships(self, chunks: List[CodeChunk], repo_path: str):
        """Detect test file relationships."""
        test_patterns = [
            r'test_.*\.py$',
            r'.*_test\.py$',
            r'.*\.test\.js$',
            r'.*\.spec\.js$',
            r'.*\.test\.ts$',
            r'.*\.spec\.ts$',
        ]
        
        # Find test files
        test_files = set()
        for chunk in chunks:
            for pattern in test_patterns:
                if re.search(pattern, chunk.path):
                    test_files.add(chunk.path)
                    break
        
        # For each test file, try to find the file it tests
        for test_file in test_files:
            tested_file = self._resolve_test_target(test_file)
            if tested_file:
                test_file_id = f"file:{test_file}"
                tested_file_id = f"file:{tested_file}"
                
                if self.graph.has_node(test_file_id) and self.graph.has_node(tested_file_id):
                    self.graph.add_edge(
                        test_file_id,
                        tested_file_id,
                        type="test_of",
                        confidence=0.9
                    )
    
    def _resolve_test_target(self, test_file_path: str) -> Optional[str]:
        """Resolve test file to the file it tests."""
        # Simple heuristic: remove test prefix/suffix and try common extensions
        base_name = Path(test_file_path).stem
        
        # Remove test indicators
        if base_name.startswith('test_'):
            target_name = base_name[5:]
        elif base_name.endswith('_test'):
            target_name = base_name[:-5]
        elif base_name.endswith('.test'):
            target_name = base_name[:-5]
        elif base_name.endswith('.spec'):
            target_name = base_name[:-5]
        else:
            return None
        
        # Try to find corresponding file
        test_dir = Path(test_file_path).parent
        extensions = ['.py', '.js', '.ts', '.tsx', '.jsx']
        
        for ext in extensions:
            candidate = test_dir / f"{target_name}{ext}"
            if candidate.exists():
                return str(candidate)
        
        return None
    
    def _sync_to_memgraph(self):
        """Sync the NetworkX graph to Memgraph."""
        if not self.mg_client:
            return
        
        try:
            cursor = self.mg_client.cursor()
            
            # Clear existing data
            cursor.execute("MATCH (n) DETACH DELETE n;")
            
            # Add nodes
            for node_id, node_data in self.graph.nodes(data=True):
                labels = [node_data.get('type', 'Node')]
                
                # Build properties
                properties = {k: v for k, v in node_data.items() if k != 'type'}
                properties['id'] = node_id
                
                # Convert to Cypher-safe values
                safe_properties = {}
                for k, v in properties.items():
                    if isinstance(v, (str, int, float, bool)):
                        safe_properties[k] = v
                    else:
                        safe_properties[k] = str(v)
                
                # Create node query
                label_str = ':'.join(labels)
                props_str = ', '.join([f"{k}: ${k}" for k in safe_properties.keys()])
                query = f"CREATE (n:{label_str} {{{props_str}}});"
                
                cursor.execute(query, safe_properties)
            
            # Add edges
            for source, target, edge_data in self.graph.edges(data=True):
                edge_type = edge_data.get('type', 'RELATED')
                
                # Build edge properties
                edge_props = {k: v for k, v in edge_data.items() if k != 'type'}
                
                if edge_props:
                    props_str = ', '.join([f"{k}: ${k}" for k in edge_props.keys()])
                    query = f"""
                    MATCH (a {{id: $source}}), (b {{id: $target}})
                    CREATE (a)-[r:{edge_type} {{{props_str}}}]->(b);
                    """
                    edge_props.update({'source': source, 'target': target})
                    cursor.execute(query, edge_props)
                else:
                    query = f"""
                    MATCH (a {{id: $source}}), (b {{id: $target}})
                    CREATE (a)-[r:{edge_type}]->(b);
                    """
                    cursor.execute(query, {'source': source, 'target': target})
            
            cursor.close()
            print(f"Synced {self.graph.number_of_nodes()} nodes and {self.graph.number_of_edges()} edges to Memgraph")
            
        except Exception as e:
            print(f"Error syncing to Memgraph: {e}")
    
    def query_dependencies(self, node_id: str, direction: str = "both", depth: int = 1) -> List[Dict[str, Any]]:
        """Query dependencies from Memgraph using Cypher."""
        if not self.mg_client:
            return []
        
        try:
            cursor = self.mg_client.cursor()
            
            if direction == "outgoing":
                query = f"""
                MATCH (n {{id: $node_id}})-[r*1..{depth}]->(m)
                RETURN n, r, m
                """
            elif direction == "incoming":
                query = f"""
                MATCH (n {{id: $node_id}})<-[r*1..{depth}]-(m)
                RETURN n, r, m
                """
            else:  # both
                query = f"""
                MATCH (n {{id: $node_id}})-[r*1..{depth}]-(m)
                RETURN n, r, m
                """
            
            cursor.execute(query, {'node_id': node_id})
            results = cursor.fetchall()
            cursor.close()
            
            # Convert results to dict format
            dependencies = []
            for result in results:
                dependencies.append({
                    'source': result[0],
                    'relationship': result[1],
                    'target': result[2]
                })
            
            return dependencies
            
        except Exception as e:
            print(f"Error querying dependencies: {e}")
            return []
    
    def get_call_graph(self) -> nx.DiGraph:
        """Get a subgraph containing only call relationships."""
        call_graph = nx.DiGraph()
        
        for source, target, data in self.graph.edges(data=True):
            if data.get('type') == 'call':
                call_graph.add_edge(source, target, **data)
                
                # Add node data
                if source in self.graph.nodes:
                    call_graph.add_node(source, **self.graph.nodes[source])
                if target in self.graph.nodes:
                    call_graph.add_node(target, **self.graph.nodes[target])
        
        return call_graph
    
    def get_import_graph(self) -> nx.DiGraph:
        """Get a subgraph containing only import relationships."""
        import_graph = nx.DiGraph()
        
        for source, target, data in self.graph.edges(data=True):
            if data.get('type') == 'import':
                import_graph.add_edge(source, target, **data)
                
                # Add node data
                if source in self.graph.nodes:
                    import_graph.add_node(source, **self.graph.nodes[source])
                if target in self.graph.nodes:
                    import_graph.add_node(target, **self.graph.nodes[target])
        
        return import_graph
    
    def compute_centrality_metrics(self) -> Dict[str, Dict[str, float]]:
        """Compute centrality metrics for the call graph."""
        call_graph = self.get_call_graph()
        
        if not call_graph.nodes():
            return {}
        
        metrics = {}
        
        try:
            # Betweenness centrality
            betweenness = nx.betweenness_centrality(call_graph)
            
            # PageRank
            pagerank = nx.pagerank(call_graph)
            
            # In-degree centrality (how many things call this)
            in_degree = dict(call_graph.in_degree())
            
            # Out-degree centrality (how many things this calls)
            out_degree = dict(call_graph.out_degree())
            
            # Combine metrics
            for node in call_graph.nodes():
                metrics[node] = {
                    'betweenness': betweenness.get(node, 0),
                    'pagerank': pagerank.get(node, 0),
                    'in_degree': in_degree.get(node, 0),
                    'out_degree': out_degree.get(node, 0)
                }
        
        except Exception as e:
            print(f"Error computing centrality metrics: {e}")
        
        return metrics
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the dependency graph (for frontend compatibility)."""
        if not self.graph:
            return {
                "nodes": 0,
                "edges": 0,
                "last_updated": "Never",
                "status": "Not built"
            }
        
        try:
            return {
                "nodes": self.graph.number_of_nodes(),
                "edges": self.graph.number_of_edges(),
                "last_updated": "Recently",
                "status": "Active" if self.mg_client else "Local only"
            }
        except Exception as e:
            return {
                "nodes": 0,
                "edges": 0,
                "last_updated": "Error",
                "status": f"Error: {str(e)}"
            }
    
    def close(self):
        """Close Memgraph connection."""
        if self.mg_client:
            self.mg_client.close() 