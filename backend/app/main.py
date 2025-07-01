import os
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pathlib import Path
from typing import Dict, List, Any, Optional
import tempfile
import shutil
import asyncio
from dotenv import load_dotenv

from .code_analyzer import CodeAnalyzer

# Load environment variables
load_dotenv()

app = FastAPI(
    title="Halos Code Analysis API",
    description="Advanced code analysis and visualization system",
    version="1.0.0"
)

# CORS middleware for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global analyzer instance
analyzer: Optional[CodeAnalyzer] = None

@app.on_event("startup")
async def startup_event():
    """Initialize the analyzer with environment-based configuration."""
    global analyzer
    
    # Load configuration from environment
    enable_vector = os.getenv("ENABLE_VECTOR_INDEXING", "false").lower() == "true"
    enable_dependency = os.getenv("ENABLE_DEPENDENCY_GRAPH", "false").lower() == "true" 
    enable_lexical = os.getenv("ENABLE_LEXICAL_INDEXING", "true").lower() == "true"
    cache_dir = os.getenv("CACHE_DIR", "/tmp/halos_code_cache")
    
    # Check for required services
    services_status = await check_external_services()
    
    # Adjust configuration based on service availability
    if not services_status["openai"] and enable_vector:
        print("⚠️  OpenAI API key not configured - disabling vector indexing")
        enable_vector = False
    
    if not services_status["qdrant"] and enable_vector:
        print("⚠️  Qdrant not accessible - disabling vector indexing")
        enable_vector = False
        
    if not services_status["memgraph"] and enable_dependency:
        print("⚠️  Memgraph not accessible - disabling dependency graph")
        enable_dependency = False
    
    analyzer = CodeAnalyzer(
        cache_dir=cache_dir,
        enable_lexical_index=enable_lexical,
        enable_vector_index=enable_vector,
        enable_dependency_graph=enable_dependency
    )
    
    print(f"🚀 Halos Code Analysis API started")
    print(f"📊 Services status: {services_status}")
    print(f"⚙️  Configuration: Lexical={enable_lexical}, Vector={enable_vector}, Graph={enable_dependency}")

async def check_external_services() -> Dict[str, bool]:
    """Check availability of external services."""
    import aiohttp
    
    status = {
        "openai": bool(os.getenv("OPENAI_API_KEY") and os.getenv("OPENAI_API_KEY") != "your_openai_api_key_here"),
        "qdrant": False,
        "memgraph": False
    }
    
    # Check Qdrant
    try:
        qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
        qdrant_api_key = os.getenv("QDRANT_API_KEY")
        headers = {"api-key": qdrant_api_key} if qdrant_api_key else {}
        
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{qdrant_url}/collections", headers=headers, timeout=aiohttp.ClientTimeout(total=5)) as response:
                status["qdrant"] = response.status == 200
    except:
        pass
    
    # Check Memgraph
    try:
        import pymgclient
        host = os.getenv("MEMGRAPH_HOST", "localhost")
        port = int(os.getenv("MEMGRAPH_PORT", "7687"))
        username = os.getenv("MEMGRAPH_USERNAME")
        password = os.getenv("MEMGRAPH_PASSWORD")
        
        # Use SSL for cloud connections
        sslmode = pymgclient.MG_SSLMODE_REQUIRE if host != "localhost" else pymgclient.MG_SSLMODE_DISABLE
        
        connection = pymgclient.Connection(
            host=host, 
            port=port, 
            username=username, 
            password=password,
            sslmode=sslmode
        )
        connection.execute("RETURN 1")
        status["memgraph"] = True
        connection.close()
    except:
        pass
    
    return status

class AnalyzeRequest(BaseModel):
    repo_path: str

class SearchRequest(BaseModel):
    query: str
    search_type: str = "bm25"
    limit: int = 20
    score_threshold: Optional[float] = None
    filters: Optional[Dict[str, Any]] = None

class SemanticSearchRequest(BaseModel):
    query: str
    limit: int = 20
    score_threshold: float = 0.7
    filters: Optional[Dict[str, Any]] = None

class HybridSearchRequest(BaseModel):
    query: str
    limit: int = 20
    lexical_weight: float = 0.3
    semantic_weight: float = 0.7

class SimilarChunksRequest(BaseModel):
    chunk_id: str
    limit: int = 10
    score_threshold: float = 0.8

class SymbolSearchRequest(BaseModel):
    symbol: str
    limit: int = 10

class FileSearchRequest(BaseModel):
    file_path: str
    limit: int = 50

class EntryPointsRequest(BaseModel):
    limit: int = 20

class ExecutionFlowRequest(BaseModel):
    entry_points: List[str]
    depth: int = 3

class DependencyQueryRequest(BaseModel):
    node_id: str
    direction: str = "both"
    depth: int = 1

class CentralityRequest(BaseModel):
    pass

@app.get("/")
async def root():
    return {"message": "Halos Code Analysis API - Hybrid Search with AST + Lexical + Semantic"}

@app.post("/analyze")
async def analyze_repository(request: AnalyzeRequest):
    """Analyze a repository and return structured data with full indexing."""
    if not analyzer:
        raise HTTPException(status_code=500, detail="Analyzer not initialized")
    
    try:
        repo_path = Path(request.repo_path)
        if not repo_path.exists():
            raise HTTPException(status_code=404, detail="Repository path not found")
        
        result = await analyzer.analyze_repository(repo_path)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

# === LEXICAL SEARCH ENDPOINTS ===

@app.post("/search/lexical")
async def search_code(request: SearchRequest):
    """Search code using lexical indexing with BM25 or exact matching."""
    if not analyzer or not analyzer.lexical_indexer:
        raise HTTPException(status_code=503, detail="Lexical search not available")
    
    try:
        results = analyzer.search_code(
            query=request.query,
            search_type=request.search_type,
            limit=request.limit
        )
        return {
            "query": request.query,
            "search_type": request.search_type,
            "total_results": len(results),
            "results": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

@app.post("/search/symbol")
async def search_by_symbol(request: SymbolSearchRequest):
    """Search for code chunks containing a specific symbol."""
    if not analyzer:
        raise HTTPException(status_code=500, detail="Analyzer not initialized")
    
    try:
        results = analyzer.search_by_symbol(
            symbol=request.symbol,
            limit=request.limit
        )
        return {
            "symbol": request.symbol,
            "total_results": len(results),
            "results": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Symbol search failed: {str(e)}")

@app.post("/search/file")
async def search_by_file(request: FileSearchRequest):
    """Get all code chunks from a specific file."""
    if not analyzer:
        raise HTTPException(status_code=500, detail="Analyzer not initialized")
    
    try:
        results = analyzer.search_by_file(
            file_path=request.file_path,
            limit=request.limit
        )
        return {
            "file_path": request.file_path,
            "total_results": len(results),
            "results": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"File search failed: {str(e)}")

# === SEMANTIC SEARCH ENDPOINTS ===

@app.post("/search/semantic")
async def semantic_search(request: SemanticSearchRequest):
    """Search code using semantic vector similarity."""
    if not analyzer or not analyzer.vector_indexer:
        raise HTTPException(status_code=503, detail="Vector search not available - please configure OpenAI API key and Qdrant")
    
    try:
        results = await analyzer.semantic_search(
            query=request.query,
            limit=request.limit,
            score_threshold=request.score_threshold,
            filters=request.filters
        )
        return {
            "query": request.query,
            "search_type": "semantic",
            "total_results": len(results),
            "results": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Semantic search failed: {str(e)}")

@app.post("/search/hybrid")
async def hybrid_search(request: HybridSearchRequest):
    """Search code using hybrid lexical + semantic approach."""
    if not analyzer:
        raise HTTPException(status_code=500, detail="Analyzer not initialized")
    
    try:
        results = await analyzer.hybrid_search(
            query=request.query,
            limit=request.limit,
            lexical_weight=request.lexical_weight,
            semantic_weight=request.semantic_weight
        )
        return {
            "query": request.query,
            "search_type": "hybrid",
            "lexical_weight": request.lexical_weight,
            "semantic_weight": request.semantic_weight,
            "total_results": len(results),
            "results": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Hybrid search failed: {str(e)}")

@app.post("/search/similar")
async def find_similar_chunks(request: SimilarChunksRequest):
    """Find chunks semantically similar to a given chunk."""
    if not analyzer or not analyzer.vector_indexer:
        raise HTTPException(status_code=503, detail="Vector analysis not available - please configure OpenAI API key and Qdrant")
    
    try:
        results = await analyzer.find_similar_chunks(
            chunk_id=request.chunk_id,
            limit=request.limit,
            score_threshold=request.score_threshold
        )
        return {
            "chunk_id": request.chunk_id,
            "total_results": len(results),
            "results": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Similarity analysis failed: {str(e)}")

# === EXECUTION FLOW ANALYSIS ENDPOINTS ===

@app.post("/analyze/entry-points")
async def find_entry_points(request: EntryPointsRequest):
    """Find potential entry points in the codebase."""
    if not analyzer or not analyzer.vector_indexer:
        raise HTTPException(status_code=503, detail="Vector analysis not available - please configure OpenAI API key and Qdrant")
    
    try:
        results = await analyzer.find_entry_points(limit=request.limit)
        return {
            "total_entry_points": len(results),
            "entry_points": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Entry point analysis failed: {str(e)}")

@app.post("/analyze/execution-flows")
async def analyze_execution_flows(request: ExecutionFlowRequest):
    """Analyze execution flows starting from entry points."""
    if not analyzer or not analyzer.dependency_graph_builder:
        raise HTTPException(status_code=503, detail="Dependency graph analysis not available - please configure Memgraph")
    
    try:
        flows = await analyzer.analyze_execution_flows(
            entry_points=request.entry_points,
            depth=request.depth
        )
        return {
            "entry_points": request.entry_points,
            "depth": request.depth,
            "total_flows": len(flows),
            "execution_flows": flows
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Execution flow analysis failed: {str(e)}")

# === INDEX MANAGEMENT ENDPOINTS ===

@app.get("/index/stats")
async def get_index_stats():
    """Get statistics about both lexical and vector indices."""
    if not analyzer:
        raise HTTPException(status_code=500, detail="Analyzer not initialized")
    
    stats = {}
    
    if analyzer.lexical_indexer:
        try:
            stats["lexical"] = analyzer.lexical_indexer.get_stats()
        except Exception as e:
            stats["lexical"] = {"error": str(e)}
    
    if analyzer.vector_indexer:
        try:
            stats["vector"] = analyzer.vector_indexer.get_stats()
        except Exception as e:
            stats["vector"] = {"error": str(e)}
    
    if analyzer.dependency_graph_builder:
        try:
            stats["graph"] = analyzer.dependency_graph_builder.get_stats()
        except Exception as e:
            stats["graph"] = {"error": str(e)}
    
    return {"stats": stats}

@app.delete("/index/clear")
async def clear_indexes():
    """Clear all indexes."""
    if not analyzer:
        raise HTTPException(status_code=500, detail="Analyzer not initialized")
    
    cleared = []
    
    if analyzer.lexical_indexer:
        try:
            analyzer.lexical_indexer.clear_index()
            cleared.append("lexical")
        except Exception as e:
            pass
    
    if analyzer.vector_indexer:
        try:
            analyzer.vector_indexer.clear_index()
            cleared.append("vector")
        except Exception as e:
            pass
    
    if analyzer.dependency_graph_builder:
        try:
            analyzer.dependency_graph_builder.clear_graph()
            cleared.append("graph")
        except Exception as e:
            pass
    
    return {"cleared": cleared}

# === DEPENDENCY GRAPH ENDPOINTS ===

@app.post("/graph/dependencies")
async def query_dependencies(request: DependencyQueryRequest):
    """Query dependencies from the dependency graph."""
    if not analyzer or not analyzer.dependency_graph_builder:
        raise HTTPException(status_code=503, detail="Dependency graph not available - please configure Memgraph")
    
    try:
        results = analyzer.query_dependencies(
            node_id=request.node_id,
            direction=request.direction,
            depth=request.depth
        )
        return {
            "node_id": request.node_id,
            "direction": request.direction,
            "depth": request.depth,
            "total_dependencies": len(results),
            "dependencies": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Dependency query failed: {str(e)}")

@app.get("/graph/call-graph")
async def get_call_graph():
    """Get the call graph showing function/method call relationships."""
    if not analyzer or not analyzer.dependency_graph_builder:
        raise HTTPException(status_code=503, detail="Dependency graph not available - please configure Memgraph")
    
    try:
        call_graph = analyzer.get_call_graph()
        if not call_graph:
            return {"error": "Dependency graph not available"}
        
        # Convert NetworkX graph to JSON format
        nodes = []
        edges = []
        
        for node_id, node_data in call_graph.nodes(data=True):
            nodes.append({
                "id": node_id,
                "ast_type": node_data.get("ast_type", "unknown"),
                "path": node_data.get("path", ""),
                "start_line": node_data.get("start_line", 0),
                "parent_symbol": node_data.get("parent_symbol", "")
            })
        
        for source, target, edge_data in call_graph.edges(data=True):
            edges.append({
                "source": source,
                "target": target,
                "function_name": edge_data.get("function_name", ""),
                "confidence": edge_data.get("confidence", 1.0)
            })
        
        return {
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "nodes": nodes,
            "edges": edges
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Call graph query failed: {str(e)}")

@app.get("/graph/import-graph")
async def get_import_graph():
    """Get the import graph showing module import relationships."""
    if not analyzer or not analyzer.dependency_graph_builder:
        raise HTTPException(status_code=503, detail="Dependency graph not available - please configure Memgraph")
    
    try:
        import_graph = analyzer.get_import_graph()
        if not import_graph:
            return {"error": "Dependency graph not available"}
        
        # Convert NetworkX graph to JSON format
        nodes = []
        edges = []
        
        for node_id, node_data in import_graph.nodes(data=True):
            nodes.append({
                "id": node_id,
                "type": node_data.get("type", "unknown"),
                "path": node_data.get("path", ""),
                "name": node_data.get("name", "")
            })
        
        for source, target, edge_data in import_graph.edges(data=True):
            edges.append({
                "source": source,
                "target": target,
                "module": edge_data.get("module", ""),
                "confidence": edge_data.get("confidence", 1.0)
            })
        
        return {
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "nodes": nodes,
            "edges": edges
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Import graph query failed: {str(e)}")

@app.get("/graph/full-dependency-graph")
async def get_full_dependency_graph():
    """Get the complete dependency graph with all relationship types."""
    if not analyzer or not analyzer.dependency_graph_builder:
        raise HTTPException(status_code=503, detail="Dependency graph not available - please configure Memgraph")
    
    try:
        dependency_graph = analyzer.get_dependency_graph()
        if not dependency_graph:
            return {"error": "Dependency graph not available"}
        
        # Convert NetworkX graph to JSON format
        nodes = []
        edges = []
        
        for node_id, node_data in dependency_graph.nodes(data=True):
            nodes.append({
                "id": node_id,
                "type": node_data.get("type", "unknown"),
                "ast_type": node_data.get("ast_type", ""),
                "path": node_data.get("path", ""),
                "start_line": node_data.get("start_line", 0),
                "end_line": node_data.get("end_line", 0),
                "parent_symbol": node_data.get("parent_symbol", "")
            })
        
        for source, target, edge_data in dependency_graph.edges(data=True):
            edges.append({
                "source": source,
                "target": target,
                "type": edge_data.get("type", "related"),
                "confidence": edge_data.get("confidence", 1.0),
                "metadata": {k: v for k, v in edge_data.items() if k not in ["type", "confidence"]}
            })
        
        # Group edges by type for statistics
        edge_types = {}
        for edge in edges:
            edge_type = edge["type"]
            edge_types[edge_type] = edge_types.get(edge_type, 0) + 1
        
        return {
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "edge_types": edge_types,
            "nodes": nodes,
            "edges": edges
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Dependency graph query failed: {str(e)}")

@app.get("/graph/centrality")
async def get_centrality_metrics():
    """Get centrality metrics for code chunks in the call graph."""
    if not analyzer or not analyzer.dependency_graph_builder:
        raise HTTPException(status_code=503, detail="Dependency graph not available - please configure Memgraph")
    
    try:
        metrics = analyzer.get_centrality_metrics()
        if not metrics:
            return {"error": "Centrality metrics not available"}
        
        # Sort by different centrality measures
        sorted_metrics = {
            "by_betweenness": sorted(
                [(node, data["betweenness"]) for node, data in metrics.items()],
                key=lambda x: x[1], reverse=True
            )[:20],
            "by_pagerank": sorted(
                [(node, data["pagerank"]) for node, data in metrics.items()],
                key=lambda x: x[1], reverse=True
            )[:20],
            "by_in_degree": sorted(
                [(node, data["in_degree"]) for node, data in metrics.items()],
                key=lambda x: x[1], reverse=True
            )[:20],
            "by_out_degree": sorted(
                [(node, data["out_degree"]) for node, data in metrics.items()],
                key=lambda x: x[1], reverse=True
            )[:20]
        }
        
        return {
            "total_nodes_analyzed": len(metrics),
            "top_nodes": sorted_metrics,
            "all_metrics": metrics
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Centrality analysis failed: {str(e)}")

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "services": await check_external_services(),
        "analyzer_ready": analyzer is not None
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port) 