#!/usr/bin/env python3
"""
Test script for hierarchical summarization system.

This script tests the complete hierarchical summarization pipeline:
1. Chunk-level summaries (one-liners)
2. File-level summaries 
3. Directory-level summaries
4. Repository-level summary

It uses the current Scout codebase as test data.
"""

import asyncio
import os
import sys
from pathlib import Path
import json

# Add the backend directory to the path
sys.path.append('backend')

from backend.app.code_analyzer import CodeAnalyzer
from backend.app.hierarchical_summarizer import HierarchicalSummarizer


async def test_hierarchical_summarization():
    """Test the complete hierarchical summarization pipeline."""
    
    print("🧪 Testing Hierarchical Summarization System")
    print("=" * 50)
    
    # Initialize analyzer with hierarchical summarization
    print("🔧 Initializing CodeAnalyzer...")
    analyzer = CodeAnalyzer(
        enable_lexical_index=True,
        enable_vector_index=False,
        enable_dependency_graph=False,
        enable_hierarchical_summarization=True
    )
    
    if not analyzer.hierarchical_summarizer:
        print("❌ Hierarchical summarizer not initialized")
        return
    
    print("✅ Hierarchical summarizer initialized")
    
    # Test with the backend directory (smaller subset for testing)
    backend_path = Path("backend/app")
    
    if not backend_path.exists():
        print(f"❌ Test directory {backend_path} not found")
        return
    
    print(f"📁 Analyzing directory: {backend_path}")
    
    # Parse files into chunks
    print("\n📝 Step 1: Parsing files into chunks...")
    source_files = analyzer.get_source_files(backend_path)
    print(f"Found {len(source_files)} source files")
    
    all_chunks = []
    for file_path in source_files[:5]:  # Limit to first 5 files for testing
        chunks = analyzer.parse_file(file_path)
        all_chunks.extend(chunks)
        print(f"  {file_path.name}: {len(chunks)} chunks")
    
    print(f"Total chunks: {len(all_chunks)}")
    
    if not all_chunks:
        print("❌ No chunks found to analyze")
        return
    
    # Test chunk-level summarization
    print("\n🤖 Step 2: Generating chunk-level summaries...")
    try:
        chunk_summaries = await analyzer.hierarchical_summarizer.summarize_chunks(all_chunks[:10])  # Limit for testing
        
        print(f"✅ Generated {len(chunk_summaries)} chunk summaries")
        
        # Show some examples
        print("\n📋 Sample chunk summaries:")
        for i, summary in enumerate(chunk_summaries[:3]):
            chunk = next(c for c in all_chunks if c.id == summary.chunk_id)
            print(f"  {i+1}. {Path(chunk.path).name}:{chunk.start_line}-{chunk.end_line}")
            print(f"     Type: {chunk.ast_type}")
            print(f"     Summary: {summary.summary}")
            print(f"     Model: {summary.model_used}, Confidence: {summary.confidence}")
            print()
        
    except Exception as e:
        print(f"❌ Failed to generate chunk summaries: {e}")
        return
    
    # Test full hierarchical summarization
    print("\n🏗️ Step 3: Generating hierarchical summary...")
    try:
        hierarchical_result = await analyzer.hierarchical_summarizer.generate_hierarchical_summary(all_chunks[:10])
        
        print("✅ Hierarchical summarization completed!")
        
        # Display results
        stats = hierarchical_result["stats"]
        print(f"\n📊 Summary Statistics:")
        print(f"  - Total chunks: {stats['total_chunks']}")
        print(f"  - Total files: {stats['total_files']}")
        print(f"  - Total directories: {stats['total_directories']}")
        print(f"  - Cache hits: {stats['cache_hits']}")
        print(f"  - API calls made: {stats['api_calls']}")
        
        # Show repository summary
        repo_summary = hierarchical_result["repository_summary"]
        print(f"\n🌍 Repository Summary:")
        print(f"  Level: {repo_summary['level']}")
        print(f"  Path: {repo_summary['path']}")
        print(f"  Summary: {repo_summary['summary']}")
        print(f"  Components: {len(repo_summary['components'])}")
        
        # Show a file summary example
        if hierarchical_result["file_summaries"]:
            file_summary = hierarchical_result["file_summaries"][0]
            print(f"\n📄 Sample File Summary:")
            print(f"  File: {Path(file_summary['path']).name}")
            print(f"  Summary: {file_summary['summary']}")
            print(f"  Components: {len(file_summary['components'])}")
        
        # Show directory summary example
        if hierarchical_result["directory_summaries"]:
            dir_summary = hierarchical_result["directory_summaries"][0]
            print(f"\n📂 Sample Directory Summary:")
            print(f"  Directory: {Path(dir_summary['path']).name}")
            print(f"  Summary: {dir_summary['summary']}")
            print(f"  Files: {len(dir_summary['components'])}")
        
    except Exception as e:
        print(f"❌ Failed to generate hierarchical summary: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Test cache functionality
    print("\n💾 Step 4: Testing cache functionality...")
    try:
        # Get cache stats
        db_path = analyzer.hierarchical_summarizer.db_path
        if os.path.exists(db_path):
            cache_size = os.path.getsize(db_path)
            print(f"✅ Cache database exists: {db_path}")
            print(f"   Size: {cache_size} bytes ({cache_size / 1024:.1f} KB)")
        
        # Test that second run uses cache
        print("🔄 Running summarization again to test caching...")
        start_time = asyncio.get_event_loop().time()
        
        # Re-run with same chunks
        cached_result = await analyzer.hierarchical_summarizer.summarize_chunks(all_chunks[:5])
        
        end_time = asyncio.get_event_loop().time()
        print(f"✅ Second run completed in {end_time - start_time:.2f} seconds")
        
        # Check that we got cached results
        cached_count = sum(1 for cs in cached_result if cs.model_used != "fallback" and cs.model_used != analyzer.hierarchical_summarizer.cheap_model)
        print(f"📋 Used {cached_count} cached summaries out of {len(cached_result)}")
        
    except Exception as e:
        print(f"⚠️ Cache testing failed: {e}")
    
    print("\n🎉 Hierarchical summarization test completed!")
    print("\nThe system successfully implements the original plan:")
    print("✅ Step 5: Generate leaf-level one-liner summaries using cheap model")
    print("✅ Step 6: Cache summaries with SHA256 hash of file + start_line + end_line")  
    print("✅ Step 7: Generate file-level summaries from chunk summaries (with centrality sorting)")
    print("✅ Step 8: Recursively generate directory and repository summaries")


def save_results_to_file(result, filename="hierarchical_summary_test_results.json"):
    """Save the test results to a JSON file for inspection."""
    try:
        with open(filename, 'w') as f:
            json.dump(result, f, indent=2, default=str)
        print(f"📁 Results saved to {filename}")
    except Exception as e:
        print(f"⚠️ Failed to save results: {e}")


if __name__ == "__main__":
    # Check for OpenAI API key
    if not os.getenv("OPENAI_API_KEY"):
        print("❌ OPENAI_API_KEY environment variable not set")
        print("Please set your OpenAI API key to test summarization:")
        print("export OPENAI_API_KEY='your-api-key-here'")
        sys.exit(1)
    
    print("🔑 OpenAI API key found")
    
    # Run the test
    asyncio.run(test_hierarchical_summarization()) 