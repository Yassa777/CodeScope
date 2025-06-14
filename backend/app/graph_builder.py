import networkx as nx
from typing import Dict, List, Any, Optional
from pathlib import Path
from .code_parser import CodeParser

class GraphBuilder:
    def __init__(self):
        """Initialize the graph builder."""
        self.graph = nx.DiGraph()
        self.parser = CodeParser()

    def process_file(self, file_path: Path, relative_path: str) -> None:
        """
        Process a file and add its structure to the graph.
        
        Args:
            file_path: Path to the file
            relative_path: Relative path from repository root
        """
        # Get the appropriate parser
        parser = self.parser._get_parser_for_file(file_path)
        if not parser:
            return

        try:
            # Read and parse the file
            with open(file_path, 'rb') as f:
                source_code = f.read()
            
            tree = parser.parse(source_code)
            if not tree:
                return

            # Add file node if it doesn't exist
            file_id = relative_path
            if not self.graph.has_node(file_id):
                self.graph.add_node(
                    file_id,
                    type="file",
                    name=Path(relative_path).name,
                    path=relative_path
                )

            # Process the AST
            self._process_ast_node(tree.root_node, file_id, source_code)

        except Exception as e:
            print(f"Error processing file {file_path}: {e}")

    def _process_ast_node(self, node: Any, parent_id: str, source_code: bytes) -> None:
        """
        Process an AST node and add it to the graph.
        
        Args:
            node: Tree-sitter AST node
            parent_id: ID of the parent node
            source_code: Source code bytes
        """
        # Get node type and name
        node_type = node.type
        node_name = self._get_node_name(node, source_code)
        
        # Create node ID
        node_id = f"{parent_id}/{node_type}/{node_name}"
        
        # Add node to graph
        self.graph.add_node(
            node_id,
            type=node_type,
            name=node_name,
            start_point=(node.start_point[0], node.start_point[1]),
            end_point=(node.end_point[0], node.end_point[1])
        )
        
        # Add edge from parent
        self.graph.add_edge(parent_id, node_id, type="contains")
        
        # Process children
        for child in node.children:
            self._process_ast_node(child, node_id, source_code)

    def _get_node_name(self, node: Any, source_code: bytes) -> str:
        """Extract node name from source code."""
        if node.type in ['function_definition', 'method_definition', 'class_definition']:
            # Find the name node
            for child in node.children:
                if child.type == 'identifier':
                    start = child.start_byte
                    end = child.end_byte
                    return source_code[start:end].decode('utf-8')
        return node.type

    def build_repository_graph(self, repo_structure: Dict[str, Any]) -> nx.DiGraph:
        """
        Build a graph representing the repository structure.
        
        Args:
            repo_structure: Dictionary containing repository structure
            
        Returns:
            NetworkX directed graph
        """
        self.graph.clear()
        
        # Add repository node
        repo_id = repo_structure["id"]
        self.graph.add_node(
            repo_id,
            type="repository",
            name=repo_structure["name"],
            url=repo_structure["url"],
            branch=repo_structure["branch"]
        )
        
        # Process folders
        self._process_folders(repo_structure["folders"], repo_id)
        
        # Process files
        for file_info in repo_structure["files"]:
            self._add_file_node(file_info, repo_id)
        
        return self.graph

    def _process_folders(self, folders: Dict[str, Any], parent_id: str):
        """
        Process folder structure recursively.
        
        Args:
            folders: Dictionary containing folder structure
            parent_id: ID of the parent node
        """
        for folder_name, folder_data in folders.items():
            folder_id = f"{parent_id}/{folder_name}"
            
            # Add folder node
            self.graph.add_node(
                folder_id,
                type="folder",
                name=folder_name
            )
            
            # Add edge from parent to folder
            self.graph.add_edge(parent_id, folder_id, type="contains")
            
            # Process subfolders
            self._process_folders(folder_data["folders"], folder_id)

    def _add_file_node(self, file_info: Dict[str, Any], parent_id: str):
        """
        Add a file node to the graph.
        
        Args:
            file_info: Dictionary containing file information
            parent_id: ID of the parent node
        """
        file_id = f"{parent_id}/{file_info['path']}"
        
        # Add file node
        self.graph.add_node(
            file_id,
            type="file",
            name=Path(file_info["path"]).name,
            path=file_info["path"],
            hash=file_info["hash"],
            size=file_info["size"]
        )
        
        # Add edge from parent to file
        self.graph.add_edge(parent_id, file_id, type="contains")

    def get_graph_data(self, level: int = 1) -> Dict[str, Any]:
        """
        Get graph data in a format suitable for visualization.
        
        Args:
            level: Semantic zoom level (1: repo, 2: files, 3: code)
            
        Returns:
            Dictionary containing nodes and edges
        """
        nodes = []
        edges = []
        
        for node_id, node_data in self.graph.nodes(data=True):
            if self._should_include_node(node_id, level):
                nodes.append({
                    "id": node_id,
                    "type": node_data["type"],
                    "name": node_data.get("name", ""),
                    "data": {k: v for k, v in node_data.items() if k not in ["type", "name"]}
                })
        
        for source, target, edge_data in self.graph.edges(data=True):
            if self._should_include_edge(source, target, level):
                edges.append({
                    "source": source,
                    "target": target,
                    "type": edge_data.get("type", "related")
                })
        
        return {
            "nodes": nodes,
            "edges": edges
        }

    def _should_include_node(self, node_id: str, level: int) -> bool:
        """Determine if a node should be included at the given level."""
        parts = node_id.split("/")
        if level == 1:
            return len(parts) <= 2  # Repository and top-level folders
        elif level == 2:
            return len(parts) <= 3  # Include files
        else:
            return True  # Include everything

    def _should_include_edge(self, source: str, target: str, level: int) -> bool:
        """Determine if an edge should be included at the given level."""
        return (self._should_include_node(source, level) and
                self._should_include_node(target, level))

    def get_node_details(self, node_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a node.
        
        Args:
            node_id: ID of the node
            
        Returns:
            Dictionary containing node details or None if not found
        """
        if not self.graph.has_node(node_id):
            return None
            
        node_data = self.graph.nodes[node_id]
        return {
            "id": node_id,
            "type": node_data["type"],
            "name": node_data.get("name", ""),
            "data": {k: v for k, v in node_data.items() if k not in ["type", "name"]}
        } 