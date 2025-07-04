import os
import logging
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pathlib import Path
from typing import Dict, List, Any, Optional
import tempfile
import shutil
import asyncio
from dotenv import load_dotenv
import aiosqlite
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from .code_analyzer import CodeAnalyzer
from .github_manager import GitHubManager
from .event_bus import EventBus, NormalizedEvent, EventType
from .rule_engine import RuleEngine, AlertContext
from .asana_manager import AsanaManager

# Load environment variables
load_dotenv()

app = FastAPI(
    title="Scout Operational Intelligence API",
    description="AI-native operational intelligence for engineering teams - GitHub + Asana + Codebase insights",
    version="0.1.0"
)

# CORS middleware for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global instances
analyzer: Optional[CodeAnalyzer] = None
github_manager: Optional[GitHubManager] = None
event_bus: Optional[EventBus] = None
rule_engine: Optional[RuleEngine] = None
asana_manager: Optional[AsanaManager] = None

@app.on_event("startup")
async def startup_event():
    """Initialize Scout with all operational intelligence components."""
    global analyzer, github_manager, event_bus, rule_engine, asana_manager
    
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
        enable_dependency_graph=enable_dependency,
        enable_hierarchical_summarization=True
    )
    
    # Initialize GitHub manager
    github_cache_dir = os.getenv("GITHUB_CACHE_DIR", "/tmp/halos_repos")
    github_manager = GitHubManager(cache_dir=github_cache_dir)
    
    # Initialize Event Bus
    event_db_path = os.getenv("EVENT_DB_PATH", "/tmp/scout_events.db")
    event_bus = EventBus(db_path=event_db_path)
    await event_bus.initialize()
    
    # Initialize Rule Engine
    rule_engine = RuleEngine(event_bus=event_bus)
    
    # Subscribe rule engine to event bus
    event_bus.subscribe(rule_engine.evaluate_event)
    
    # Initialize Asana manager
    asana_manager = AsanaManager(
        sandbox=os.getenv("ASANA_SANDBOX", "false").lower() == "true"
    )
    
    print(f"🧠 Scout Operational Intelligence API started")
    print(f"📊 Services status: {services_status}")
    print(f"⚙️  Configuration: Lexical={enable_lexical}, Vector={enable_vector}, Graph={enable_dependency}")
    print(f"📁 GitHub cache: {github_cache_dir}")
    print(f"📡 Event bus initialized at: {event_db_path}")
    print(f"📏 Rule engine with {len(rule_engine.rules) if rule_engine else 0} rules")
    print(f"📋 Asana integration: {'Configured' if asana_manager.access_token else 'Not configured'}")

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

class GitHubCloneRequest(BaseModel):
    github_url: str
    force_fresh: bool = False

class AnalyzeGitHubRequest(BaseModel):
    github_url: str
    force_fresh: bool = False

@app.get("/")
async def root():
    return {
        "message": "Scout Operational Intelligence API", 
        "description": "AI-native operational intelligence for engineering teams",
        "version": "0.1.0",
        "features": [
            "GitHub + Asana Integration",
            "Real-time Event Processing", 
            "AI-powered Weekly Narratives",
            "Codebase Intelligence"
        ]
    }

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

# === GITHUB REPOSITORY ENDPOINTS ===

@app.post("/github/clone")
async def clone_github_repository(request: GitHubCloneRequest):
    """Clone or update a GitHub repository and return repository information."""
    if not github_manager:
        raise HTTPException(status_code=500, detail="GitHub manager not initialized")
    
    try:
        result = await github_manager.clone_or_update_repo(
            github_url=request.github_url,
            force_fresh=request.force_fresh
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Clone operation failed: {str(e)}")

@app.post("/github/analyze")
async def analyze_github_repository(request: AnalyzeGitHubRequest):
    """Clone a GitHub repository and analyze it in one step."""
    if not analyzer or not github_manager:
        raise HTTPException(status_code=500, detail="Services not initialized")
    
    try:
        # First clone or update the repository
        clone_result = await github_manager.clone_or_update_repo(
            github_url=request.github_url,
            force_fresh=request.force_fresh
        )
        
        # Then analyze the cloned repository
        repo_path = Path(clone_result["local_path"])
        analysis_result = await analyzer.analyze_repository(repo_path)
        
        # Combine results
        return {
            "github_info": clone_result,
            "analysis_result": analysis_result
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"GitHub analysis failed: {str(e)}")

@app.get("/github/repositories")
async def list_cached_repositories():
    """List all cached GitHub repositories."""
    if not github_manager:
        raise HTTPException(status_code=500, detail="GitHub manager not initialized")
    
    try:
        repos = github_manager.list_cached_repos()
        return {
            "total_repositories": len(repos),
            "repositories": repos
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list repositories: {str(e)}")

@app.delete("/github/repository")
async def delete_cached_repository(github_url: str = Query(..., description="GitHub repository URL")):
    """Delete a cached GitHub repository."""
    if not github_manager:
        raise HTTPException(status_code=500, detail="GitHub manager not initialized")
    
    try:
        success = github_manager.delete_cached_repo(github_url)
        if success:
            return {"message": "Repository deleted successfully", "github_url": github_url}
        else:
            raise HTTPException(status_code=404, detail="Repository not found in cache")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete repository: {str(e)}")

@app.post("/github/cleanup")
async def cleanup_old_repositories(max_repos: int = Query(10, description="Maximum number of repositories to keep")):
    """Clean up old cached repositories, keeping only the most recent ones."""
    if not github_manager:
        raise HTTPException(status_code=500, detail="GitHub manager not initialized")
    
    try:
        removed_count = github_manager.cleanup_old_repos(max_repos)
        return {
            "message": f"Cleanup completed",
            "repositories_removed": removed_count,
            "max_repositories": max_repos
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cleanup failed: {str(e)}")

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
    """Get statistics about all indices and the dependency graph."""
    if not analyzer:
        raise HTTPException(status_code=500, detail="Analyzer not initialized")
    
    stats = {
        "lexical_index": {"document_count": 0, "last_updated": "Never", "index_size_mb": 0},
        "vector_index": {"collection_exists": False, "points_count": 0, "vectors_size_mb": 0},
        "dependency_graph": {"nodes": 0, "edges": 0, "last_updated": "Never"}
    }
    
    if analyzer.lexical_indexer:
        try:
            stats["lexical_index"] = analyzer.lexical_indexer.get_stats()
        except Exception as e:
            stats["lexical_index"]["error"] = str(e)
    
    if analyzer.vector_indexer:
        try:
            stats["vector_index"] = analyzer.vector_indexer.get_stats()
        except Exception as e:
            stats["vector_index"]["error"] = str(e)
    
    if analyzer.dependency_graph_builder:
        try:
            stats["dependency_graph"] = analyzer.dependency_graph_builder.get_stats()
        except Exception as e:
            stats["dependency_graph"]["error"] = str(e)
    
    return stats

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

# Scout Operational Intelligence Endpoints

class GitHubWebhookPayload(BaseModel):
    action: Optional[str] = None
    pull_request: Optional[Dict[str, Any]] = None
    repository: Optional[Dict[str, Any]] = None
    commits: Optional[List[Dict[str, Any]]] = None
    pusher: Optional[Dict[str, Any]] = None
    before: Optional[str] = None
    after: Optional[str] = None
    ref: Optional[str] = None

class AsanaWebhookPayload(BaseModel):
    events: List[Dict[str, Any]]

@app.post("/webhooks/github")
async def github_webhook(request: Request):
    """Handle GitHub webhook events."""
    try:
        payload = await request.json()
        event_type = request.headers.get("X-GitHub-Event", "unknown")
        
        # Process the webhook
        processed_event = await event_bus.process_github_webhook(event_type, payload)
        
        if processed_event:
            logger.info(f"Processed GitHub {event_type} event: {processed_event.id}")
            return {"status": "success", "event_id": processed_event.id}
        else:
            logger.warning(f"Ignored GitHub {event_type} event")
            return {"status": "ignored", "reason": "event_not_relevant"}
            
    except Exception as e:
        logger.error(f"Error processing GitHub webhook: {e}")
        raise HTTPException(status_code=500, detail=f"Webhook processing failed: {str(e)}")

@app.post("/webhooks/asana")
async def asana_webhook(request: Request):
    """Handle Asana webhook events."""
    try:
        payload = await request.json()
        
        # Process the webhook
        processed_event = await event_bus.process_asana_webhook(payload)
        
        if processed_event:
            logger.info(f"Processed Asana event: {processed_event.id}")
            return {"status": "success", "event_id": processed_event.id}
        else:
            logger.warning("Ignored Asana event")
            return {"status": "ignored", "reason": "event_not_relevant"}
            
    except Exception as e:
        logger.error(f"Error processing Asana webhook: {e}")
        raise HTTPException(status_code=500, detail=f"Webhook processing failed: {str(e)}")

@app.get("/events")
async def get_events(
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0),
    event_type: Optional[str] = Query(default=None),
    source: Optional[str] = Query(default=None),
    start_date: Optional[str] = Query(default=None),
    end_date: Optional[str] = Query(default=None)
):
    """Get timeline of events with optional filtering."""
    try:
        filters = {}
        if event_type:
            filters["event_type"] = event_type
        if source:
            filters["source"] = source
        if start_date:
            filters["start_date"] = start_date
        if end_date:
            filters["end_date"] = end_date
        
        events = await event_bus.get_events(limit=limit, offset=offset, filters=filters)
        total_count = await event_bus.get_event_count(filters=filters)
        
        return {
            "events": events,
            "pagination": {
                "limit": limit,
                "offset": offset,
                "total": total_count,
                "has_more": offset + len(events) < total_count
            }
        }
        
    except Exception as e:
        logger.error(f"Error retrieving events: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve events: {str(e)}")

@app.get("/rules")
async def get_rules():
    """Get rule engine status and configured rules."""
    try:
        return {
            "engine_status": "active",
            "rules": rule_engine.get_configured_rules(),
            "rule_stats": rule_engine.get_rule_stats(),
            "categories": ["pr_health", "ci_quality", "security", "task_tracking"]
        }
    except Exception as e:
        logger.error(f"Error retrieving rules: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve rules: {str(e)}")

@app.post("/rules/configure")
async def configure_rules(rule_config: Dict[str, Any]):
    """Update rule engine configuration."""
    try:
        # Update rule thresholds and settings
        updated_rules = rule_engine.update_rule_config(rule_config)
        return {
            "status": "success",
            "updated_rules": updated_rules,
            "message": f"Updated {len(updated_rules)} rules"
        }
    except Exception as e:
        logger.error(f"Error configuring rules: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to configure rules: {str(e)}")

# Code Analysis Endpoints

@app.post("/analyze/repository")
async def analyze_repository_endpoint(request: AnalyzeRequest):
    """Analyze a repository and generate hierarchical summaries."""
    try:
        repo_path = Path(request.repo_path)
        if not repo_path.exists():
            raise HTTPException(status_code=404, detail="Repository path not found")
        
        # Initialize code analyzer with hierarchical summarization enabled
        analyzer = CodeAnalyzer(
            enable_lexical_index=True,
            enable_vector_index=False,
            enable_dependency_graph=False,
            enable_hierarchical_summarization=True
        )
        
        # Analyze repository
        result = await analyzer.analyze_repository(repo_path)
        
        return {
            "status": "success",
            "analysis": result,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f"Repository analysis failed: {e}")
        logger.error(f"Traceback: {error_details}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

@app.post("/summarize/hierarchical")
async def generate_hierarchical_summary(request: AnalyzeRequest):
    """Generate hierarchical summary for a repository."""
    try:
        repo_path = Path(request.repo_path)
        if not repo_path.exists():
            raise HTTPException(status_code=404, detail="Repository path not found")
        
        # Initialize components
        analyzer = CodeAnalyzer(enable_hierarchical_summarization=True)
        
        # Parse repository into chunks
        source_files = analyzer.get_source_files(repo_path)
        all_chunks = []
        for file_path in source_files:
            chunks = analyzer.parse_file(file_path)
            all_chunks.extend(chunks)
        
        # Generate hierarchical summary
        if analyzer.hierarchical_summarizer:
            summary_result = await analyzer.hierarchical_summarizer.generate_hierarchical_summary(all_chunks)
            
            return {
                "status": "success",
                "summary": summary_result,
                "repository": str(repo_path),
                "timestamp": datetime.now().isoformat()
            }
        else:
            raise HTTPException(status_code=503, detail="Hierarchical summarization not available")
        
    except Exception as e:
        logger.error(f"Hierarchical summarization failed: {e}")
        raise HTTPException(status_code=500, detail=f"Summarization failed: {str(e)}")

@app.get("/summarize/cache/stats")
async def get_summary_cache_stats():
    """Get statistics about the summary cache."""
    try:
        analyzer = CodeAnalyzer(enable_hierarchical_summarization=True)
        
        if not analyzer.hierarchical_summarizer:
            raise HTTPException(status_code=503, detail="Hierarchical summarization not available")
        
        # Get cache statistics
        async with aiosqlite.connect(analyzer.hierarchical_summarizer.db_path) as db:
            # Count chunk summaries
            async with db.execute("SELECT COUNT(*) FROM chunk_summaries") as cursor:
                chunk_count = (await cursor.fetchone())[0]
            
            # Count hierarchical summaries  
            async with db.execute("SELECT COUNT(*) FROM hierarchical_summaries") as cursor:
                hierarchical_count = (await cursor.fetchone())[0]
            
            # Get cache size
            cache_size_bytes = os.path.getsize(analyzer.hierarchical_summarizer.db_path)
            
            return {
                "cache_stats": {
                    "chunk_summaries": chunk_count,
                    "hierarchical_summaries": hierarchical_count,
                    "cache_size_bytes": cache_size_bytes,
                    "cache_size_mb": round(cache_size_bytes / (1024 * 1024), 2),
                    "cache_path": analyzer.hierarchical_summarizer.db_path
                }
            }
            
    except Exception as e:
        logger.error(f"Error getting cache stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get cache stats: {str(e)}")

@app.delete("/summarize/cache")
async def clear_summary_cache():
    """Clear the summary cache."""
    try:
        analyzer = CodeAnalyzer(enable_hierarchical_summarization=True)
        
        if not analyzer.hierarchical_summarizer:
            raise HTTPException(status_code=503, detail="Hierarchical summarization not available")
        
        # Clear cache
        async with aiosqlite.connect(analyzer.hierarchical_summarizer.db_path) as db:
            await db.execute("DELETE FROM chunk_summaries")
            await db.execute("DELETE FROM hierarchical_summaries")
            await db.commit()
        
        return {
            "status": "success",
            "message": "Summary cache cleared"
        }
        
    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to clear cache: {str(e)}")

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    services = await check_external_services()
    
    # Add Scout-specific service checks
    scout_services = {
        "event_bus": event_bus is not None and event_bus._initialized,
        "rule_engine": rule_engine is not None,
        "asana": asana_manager is not None and asana_manager.access_token is not None
    }
    
    # Add analyzer component checks
    analyzer_components = {}
    if analyzer:
        analyzer_components = {
            "lexical_indexer": analyzer.lexical_indexer is not None,
            "vector_indexer": analyzer.vector_indexer is not None,
            "dependency_graph": analyzer.dependency_graph_builder is not None,
            "hierarchical_summarizer": analyzer.hierarchical_summarizer is not None
        }
    
    return {
        "status": "healthy",
        "services": {**services, **scout_services},
        "analyzer_ready": analyzer is not None,
        "analyzer_components": analyzer_components,
        "scout_ready": all([event_bus, rule_engine])
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port) 