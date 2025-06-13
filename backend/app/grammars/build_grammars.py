import os
import subprocess
from pathlib import Path

GRAMMARS = {
    'python': 'https://github.com/tree-sitter/tree-sitter-python',
    'javascript': 'https://github.com/tree-sitter/tree-sitter-javascript',
    'typescript': 'https://github.com/tree-sitter/tree-sitter-typescript',
    'go': 'https://github.com/tree-sitter/tree-sitter-go',
    'rust': 'https://github.com/tree-sitter/tree-sitter-rust',
    'java': 'https://github.com/tree-sitter/tree-sitter-java',
    'cpp': 'https://github.com/tree-sitter/tree-sitter-cpp',
}

def build_grammars():
    """Build tree-sitter grammars for supported languages."""
    grammars_dir = Path(__file__).parent
    grammars_dir.mkdir(exist_ok=True)

    for lang, repo in GRAMMARS.items():
        lang_dir = grammars_dir / lang
        if not lang_dir.exists():
            print(f"Cloning {lang} grammar...")
            subprocess.run(['git', 'clone', repo, str(lang_dir)], check=True)
        
        print(f"Building {lang} grammar...")
        subprocess.run(['tree-sitter', 'generate'], cwd=lang_dir, check=True)

    # Build the shared library
    print("Building shared library...")
    subprocess.run(['tree-sitter', 'build-wasm'], cwd=grammars_dir, check=True)

if __name__ == '__main__':
    build_grammars() 