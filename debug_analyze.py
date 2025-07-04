#!/usr/bin/env python3
"""
Debug script to test repository analysis directly.
"""

import sys
import asyncio
from pathlib import Path

sys.path.append('backend')

from backend.app.code_analyzer import CodeAnalyzer


async def debug_analyze():
    """Debug the repository analysis functionality."""
    
    print("🔧 Debug: Testing repository analysis directly")
    
    try:
        # Initialize analyzer
        analyzer = CodeAnalyzer(
            enable_lexical_index=True,
            enable_vector_index=False,
            enable_dependency_graph=False,
            enable_hierarchical_summarization=True
        )
        
        print("✅ Analyzer initialized")
        
        # Test path
        repo_path = Path("./backend/app")
        print(f"📁 Analyzing: {repo_path}")
        print(f"   Exists: {repo_path.exists()}")
        print(f"   Is dir: {repo_path.is_dir()}")
        
        if not repo_path.exists():
            print("❌ Path does not exist")
            return
        
        # Analyze
        result = await analyzer.analyze_repository(repo_path)
        
        print("✅ Analysis completed")
        print(f"📊 Results:")
        print(f"   Repository: {result['repository']}")
        print(f"   Total files: {result['total_files']}")
        print(f"   Total chunks: {result['total_chunks']}")
        print(f"   Hierarchical summary available: {result.get('hierarchical_summary_available', False)}")
        
        # Test components
        components = {
            "lexical_index_available": result.get('lexical_index_available', False),
            "vector_index_available": result.get('vector_index_available', False),
            "dependency_graph_available": result.get('dependency_graph_available', False),
            "hierarchical_summary_available": result.get('hierarchical_summary_available', False)
        }
        
        print(f"\n🔧 Component Status:")
        for component, status in components.items():
            print(f"   {component}: {status}")
        
        return result
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    result = asyncio.run(debug_analyze())
    if result:
        print("\n✅ Analysis successful!")
    else:
        print("\n❌ Analysis failed!") 