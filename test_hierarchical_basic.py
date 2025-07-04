#!/usr/bin/env python3
"""
Basic test for hierarchical summarization system without API calls.

This script tests:
1. Hierarchical summarizer initialization
2. Chunk parsing 
3. Cache database setup
4. File structure analysis

It does NOT require OpenAI API key.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add the backend directory to the path
sys.path.append('backend')

from backend.app.code_analyzer import CodeAnalyzer


async def test_basic_functionality():
    """Test basic functionality without API calls."""
    
    print("🧪 Testing Basic Hierarchical Summarization Setup")
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
        return False
    
    print("✅ Hierarchical summarizer initialized")
    print(f"   Cache directory: {analyzer.hierarchical_summarizer.cache_dir}")
    print(f"   Database path: {analyzer.hierarchical_summarizer.db_path}")
    print(f"   Cheap model: {analyzer.hierarchical_summarizer.cheap_model}")
    print(f"   Powerful model: {analyzer.hierarchical_summarizer.powerful_model}")
    
    # Test database initialization
    print("\n💾 Testing database setup...")
    db_path = analyzer.hierarchical_summarizer.db_path
    if os.path.exists(db_path):
        print(f"✅ Database file exists: {db_path}")
        file_size = os.path.getsize(db_path)
        print(f"   Size: {file_size} bytes")
    else:
        print(f"✅ Database will be created at: {db_path}")
    
    # Test with the backend directory
    backend_path = Path("backend/app")
    
    if not backend_path.exists():
        print(f"❌ Test directory {backend_path} not found")
        return False
    
    print(f"\n📁 Analyzing directory: {backend_path}")
    
    # Parse files into chunks
    print("\n📝 Testing file parsing...")
    source_files = analyzer.get_source_files(backend_path)
    print(f"Found {len(source_files)} source files:")
    
    total_chunks = 0
    for i, file_path in enumerate(source_files[:5]):  # Test first 5 files
        print(f"  {i+1}. {file_path.name}")
        try:
            chunks = analyzer.parse_file(file_path)
            total_chunks += len(chunks)
            print(f"     -> {len(chunks)} chunks")
            
            # Show details of first chunk
            if chunks:
                chunk = chunks[0]
                print(f"     -> First chunk: {chunk.ast_type} at lines {chunk.start_line}-{chunk.end_line}")
                print(f"     -> Hash: {chunk.hash[:8]}...")
                if chunk.parent_symbol:
                    print(f"     -> Parent: {chunk.parent_symbol}")
                
        except Exception as e:
            print(f"     -> Error parsing: {e}")
    
    print(f"\n📊 Total chunks parsed: {total_chunks}")
    
    if total_chunks == 0:
        print("❌ No chunks were parsed")
        return False
    
    # Test cache database operations (without API calls)
    print("\n🗄️ Testing cache operations...")
    try:
        # Test that we can connect to the database
        import aiosqlite
        async with aiosqlite.connect(analyzer.hierarchical_summarizer.db_path) as db:
            # Check if tables exist
            async with db.execute("SELECT name FROM sqlite_master WHERE type='table'") as cursor:
                tables = await cursor.fetchall()
                table_names = [row[0] for row in tables]
                print(f"✅ Database tables: {table_names}")
                
                if 'chunk_summaries' in table_names and 'hierarchical_summaries' in table_names:
                    print("✅ Required tables exist")
                else:
                    print("❌ Required tables missing")
                    return False
                
            # Check if we can query the tables
            async with db.execute("SELECT COUNT(*) FROM chunk_summaries") as cursor:
                count = (await cursor.fetchone())[0]
                print(f"✅ Chunk summaries in cache: {count}")
                
            async with db.execute("SELECT COUNT(*) FROM hierarchical_summaries") as cursor:
                count = (await cursor.fetchone())[0]
                print(f"✅ Hierarchical summaries in cache: {count}")
        
    except Exception as e:
        print(f"❌ Database operations failed: {e}")
        return False
    
    # Test hash computation
    print("\n🔐 Testing hash computation...")
    if total_chunks > 0:
        # Get a sample chunk and test hash computation
        sample_file = source_files[0]
        sample_chunks = analyzer.parse_file(sample_file)
        if sample_chunks:
            chunk = sample_chunks[0]
            
            # Test that hash is computed
            print(f"✅ Chunk hash computed: {chunk.hash}")
            
            # Test hash consistency
            expected_hash_input = f"{chunk.path}:{chunk.start_line}:{chunk.end_line}"
            import hashlib
            expected_hash = hashlib.sha256(expected_hash_input.encode()).hexdigest()
            
            if chunk.hash == expected_hash:
                print("✅ Hash computation is correct")
            else:
                print(f"❌ Hash mismatch. Expected: {expected_hash}, Got: {chunk.hash}")
                return False
    
    print("\n🎉 Basic functionality test passed!")
    print("\nThe system is ready for:")
    print("✅ Hierarchical summarizer initialization")
    print("✅ File parsing with Tree-sitter")
    print("✅ Chunk extraction and hashing")
    print("✅ Cache database setup and operations")
    print("✅ All infrastructure for steps 5-8 of the original plan")
    
    return True


if __name__ == "__main__":
    print("🔍 Running basic functionality test (no API key required)")
    
    success = asyncio.run(test_basic_functionality())
    
    if success:
        print("\n✅ All basic tests passed!")
        print("\nTo test the full summarization pipeline:")
        print("1. Set OPENAI_API_KEY environment variable")
        print("2. Run: python test_hierarchical_summary.py")
        print("3. Or use the API endpoint: POST /summarize/hierarchical")
    else:
        print("\n❌ Some tests failed")
        sys.exit(1) 