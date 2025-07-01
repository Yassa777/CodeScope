#!/bin/bash

# Halos External Services Setup Script
# This script sets up Qdrant (vector database) and Memgraph (graph database)

set -e

CURRENT_DIR="$(pwd)"
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Setting up Halos External Services${NC}"
echo "================================================"

# Function to check if Docker is running
check_docker() {
    if ! docker ps >/dev/null 2>&1; then
        echo -e "${RED}❌ Docker is not running or accessible${NC}"
        echo -e "${YELLOW}📝 Please ensure Docker Desktop is running and try again${NC}"
        echo -e "${YELLOW}   On macOS: Start Docker Desktop from Applications${NC}"
        echo -e "${YELLOW}   Or run: open -a Docker${NC}"
        echo ""
        echo -e "${BLUE}💡 Alternative: Use cloud services instead:${NC}"
        echo -e "   • Qdrant Cloud: https://cloud.qdrant.io/"
        echo -e "   • Memgraph Cloud: https://memgraph.com/cloud"
        exit 1
    fi
    echo -e "${GREEN}✅ Docker is running${NC}"
}

# Function to start Qdrant
start_qdrant() {
    echo -e "${BLUE}🔧 Starting Qdrant vector database...${NC}"
    
    # Stop existing container if running
    docker stop halos-qdrant 2>/dev/null || true
    docker rm halos-qdrant 2>/dev/null || true
    
    # Create storage directory
    mkdir -p "${CURRENT_DIR}/qdrant_storage"
    
    # Start Qdrant container
    docker run -d \
        --name halos-qdrant \
        -p 6333:6333 \
        -p 6334:6334 \
        -v "${CURRENT_DIR}/qdrant_storage:/qdrant/storage" \
        qdrant/qdrant:latest
    
    echo -e "${GREEN}✅ Qdrant started on http://localhost:6333${NC}"
    echo -e "${BLUE}   Dashboard: http://localhost:6333/dashboard${NC}"
}

# Function to start Memgraph
start_memgraph() {
    echo -e "${BLUE}🔧 Starting Memgraph graph database...${NC}"
    
    # Stop existing container if running
    docker stop halos-memgraph 2>/dev/null || true
    docker rm halos-memgraph 2>/dev/null || true
    
    # Create storage directories
    mkdir -p "${CURRENT_DIR}/memgraph_data"
    mkdir -p "${CURRENT_DIR}/memgraph_log"
    mkdir -p "${CURRENT_DIR}/memgraph_etc"
    
    # Start Memgraph container
    docker run -d \
        --name halos-memgraph \
        -p 7687:7687 \
        -p 7444:7444 \
        -p 3000:3000 \
        -v "${CURRENT_DIR}/memgraph_data:/var/lib/memgraph" \
        -v "${CURRENT_DIR}/memgraph_log:/var/log/memgraph" \
        -v "${CURRENT_DIR}/memgraph_etc:/etc/memgraph" \
        memgraph/memgraph-platform:latest
    
    echo -e "${GREEN}✅ Memgraph started on bolt://localhost:7687${NC}"
    echo -e "${BLUE}   Lab interface: http://localhost:3000${NC}"
}

# Function to verify services
verify_services() {
    echo -e "${BLUE}🔍 Verifying services...${NC}"
    
    # Wait a moment for services to start
    sleep 5
    
    # Check Qdrant
    if curl -s http://localhost:6333/health >/dev/null 2>&1; then
        echo -e "${GREEN}✅ Qdrant is healthy${NC}"
    else
        echo -e "${YELLOW}⚠️  Qdrant may still be starting up${NC}"
    fi
    
    # Check Memgraph
    if docker ps | grep -q halos-memgraph; then
        echo -e "${GREEN}✅ Memgraph container is running${NC}"
    else
        echo -e "${RED}❌ Memgraph container failed to start${NC}"
    fi
}

# Function to show next steps
show_next_steps() {
    echo ""
    echo -e "${BLUE}🎉 Setup Complete!${NC}"
    echo "================================"
    echo -e "${GREEN}Services running:${NC}"
    echo -e "  • Qdrant: http://localhost:6333"
    echo -e "  • Memgraph: bolt://localhost:7687"
    echo ""
    echo -e "${BLUE}Next steps:${NC}"
    echo -e "  1. Add your OpenAI API key to backend/.env"
    echo -e "  2. Enable vector and graph indexing in CodeAnalyzer"
    echo -e "  3. Restart the backend server"
    echo ""
    echo -e "${YELLOW}To stop services:${NC}"
    echo -e "  docker stop halos-qdrant halos-memgraph"
    echo ""
    echo -e "${YELLOW}To view logs:${NC}"
    echo -e "  docker logs halos-qdrant"
    echo -e "  docker logs halos-memgraph"
}

# Main execution
main() {
    check_docker
    start_qdrant
    start_memgraph
    verify_services
    show_next_steps
}

# Run main function
main "$@" 