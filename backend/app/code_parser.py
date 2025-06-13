from pathlib import Path
from typing import Dict, List, Optional, Any
import tree_sitter
from tree_sitter import Language, Parser
import os

class CodeParser:
    def __init__(self):
        """Initialize the code parser with tree-sitter."""
        self.parsers = {}
        self._load_parsers()

    def _load_parsers(self):
        """Load tree-sitter parsers for supported languages."""
        grammars_dir = Path(__file__).parent / 'grammars'
        if not grammars_dir.exists():
            raise RuntimeError(
                "Tree-sitter grammars not found. Please run build_grammars.py first."
            )

        # Load each grammar
        for lang_dir in grammars_dir.iterdir():
            if lang_dir.is_dir() and (lang_dir / 'src').exists():
                try:
                    language = Language(str(lang_dir / 'src' / 'tree-sitter-grammar.so'))
                    parser = Parser()
                    parser.set_language(language)
                    self.parsers[lang_dir.name] = parser
                except Exception as e:
                    print(f"Failed to load grammar for {lang_dir.name}: {e}")

    def _get_parser_for_file(self, file_path: Path) -> Optional[Parser]:
        """Get the appropriate parser for a file based on its extension."""
        ext = file_path.suffix.lower()
        ext_to_lang = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.tsx': 'typescript',
            '.go': 'go',
            '.rs': 'rust',
            '.java': 'java',
            '.cpp': 'cpp',
            '.hpp': 'cpp',
            '.h': 'cpp',
        }
        
        lang = ext_to_lang.get(ext)
        if not lang or lang not in self.parsers:
            return None
        return self.parsers[lang]

    def parse_file(self, file_path: Path) -> Dict[str, Any]:
        """
        Parse a source file and extract its structure.
        
        Args:
            file_path: Path to the source file
            
        Returns:
            Dictionary containing the parsed structure
        """
        parser = self._get_parser_for_file(file_path)
        if not parser:
            return {
                "error": f"No parser available for {file_path.suffix} files"
            }

        with open(file_path, 'rb') as f:
            source_code = f.read()

        tree = parser.parse(source_code)
        return self._extract_structure(tree.root_node, source_code)

    def _extract_structure(self, node: tree_sitter.Node, source_code: bytes) -> Dict[str, Any]:
        """
        Extract the structure from a tree-sitter AST node.
        
        Args:
            node: The tree-sitter node to process
            source_code: The original source code
            
        Returns:
            Dictionary containing the extracted structure
        """
        result = {
            "type": node.type,
            "start_point": {"row": node.start_point[0], "column": node.start_point[1]},
            "end_point": {"row": node.end_point[0], "column": node.end_point[1]},
            "children": []
        }

        # Extract node-specific information based on type
        if node.type in ['function_definition', 'method_definition']:
            result["name"] = self._get_function_name(node, source_code)
            result["parameters"] = self._get_function_parameters(node, source_code)
            result["return_type"] = self._get_return_type(node, source_code)
        elif node.type in ['class_definition', 'class_declaration']:
            result["name"] = self._get_class_name(node, source_code)
            result["methods"] = self._get_class_methods(node, source_code)
        elif node.type in ['import_statement', 'import_declaration']:
            result["imports"] = self._get_imports(node, source_code)

        # Process child nodes
        for child in node.children:
            child_structure = self._extract_structure(child, source_code)
            if child_structure:
                result["children"].append(child_structure)

        return result

    def _get_function_name(self, node: tree_sitter.Node, source_code: bytes) -> str:
        """Extract function name from a function definition node."""
        for child in node.children:
            if child.type in ['identifier', 'name']:
                return source_code[child.start_byte:child.end_byte].decode('utf-8')
        return ""

    def _get_function_parameters(self, node: tree_sitter.Node, source_code: bytes) -> List[str]:
        """Extract parameters from a function definition node."""
        parameters = []
        for child in node.children:
            if child.type in ['parameters', 'formal_parameters']:
                for param in child.children:
                    if param.type in ['parameter', 'formal_parameter']:
                        param_name = None
                        for param_child in param.children:
                            if param_child.type in ['identifier', 'name']:
                                param_name = source_code[param_child.start_byte:param_child.end_byte].decode('utf-8')
                                break
                        if param_name:
                            parameters.append(param_name)
        return parameters

    def _get_return_type(self, node: tree_sitter.Node, source_code: bytes) -> str:
        """Extract return type from a function definition node."""
        for child in node.children:
            if child.type in ['return_type', 'type_annotation']:
                return source_code[child.start_byte:child.end_byte].decode('utf-8')
        return ""

    def _get_class_name(self, node: tree_sitter.Node, source_code: bytes) -> str:
        """Extract class name from a class definition node."""
        for child in node.children:
            if child.type in ['identifier', 'name']:
                return source_code[child.start_byte:child.end_byte].decode('utf-8')
        return ""

    def _get_class_methods(self, node: tree_sitter.Node, source_code: bytes) -> List[Dict[str, Any]]:
        """Extract methods from a class definition node."""
        methods = []
        for child in node.children:
            if child.type in ['class_body', 'body']:
                for method in child.children:
                    if method.type in ['method_definition', 'function_definition']:
                        method_structure = self._extract_structure(method, source_code)
                        if method_structure:
                            methods.append(method_structure)
        return methods

    def _get_imports(self, node: tree_sitter.Node, source_code: bytes) -> List[str]:
        """Extract imports from an import statement node."""
        imports = []
        for child in node.children:
            if child.type in ['import_path', 'source']:
                import_path = source_code[child.start_byte:child.end_byte].decode('utf-8')
                imports.append(import_path)
        return imports 