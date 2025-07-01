# 🚀 Halos External Services Setup Guide

This guide will help you set up the external services needed for Halos's advanced features:
- **Qdrant** - Vector database for semantic search
- **Memgraph** - Graph database for dependency analysis

## 🔍 Current System Status

Your backend is already running with **lexical search** enabled! The external services are optional but unlock powerful features:

| Service | Purpose | Status | Required For |
|---------|---------|--------|--------------|
| Lexical Index | BM25 text search | ✅ **Working** | Basic search |
| Qdrant | Vector embeddings | ⚠️ **Optional** | Semantic search |
| Memgraph | Dependency graphs | ⚠️ **Optional** | Graph analysis |

## 🐳 Option 1: Docker Setup (Recommended)

### Step 1: Fix Docker Issues

If you're experiencing Docker API errors, try these solutions:

```bash
# Option A: Restart Docker Desktop
osascript -e 'quit app "Docker"'
sleep 5
open -a Docker

# Option B: Reset Docker Desktop
# Go to Docker Desktop → Troubleshoot → Clean / Purge data
```

### Step 2: Start Services

Once Docker is working:

```bash
# Using Docker Compose (recommended)
cd /Users/dim/Desktop/Spill\ Projects/Halos
docker compose up -d

# Or using the setup script
chmod +x setup_services.sh
./setup_services.sh
```

### Step 3: Verify Services

```bash
# Check service health
curl http://localhost:6333/health    # Qdrant
curl http://localhost:7444           # Memgraph
```

## ☁️ Option 2: Cloud Services (Easiest)

If Docker continues to have issues, use cloud services:

### Qdrant Cloud
1. Sign up at [cloud.qdrant.io](https://cloud.qdrant.io/)
2. Create a free cluster
3. Get your API key and URL
4. Update `backend/.env`:
   ```bash
   QDRANT_URL=https://your-cluster.qdrant.io
   QDRANT_API_KEY=your_api_key_here
   ```

### Memgraph Cloud
1. Sign up at [memgraph.com/cloud](https://memgraph.com/cloud)
2. Create a free instance
3. Get connection details
4. Update `backend/.env`:
   ```bash
   MEMGRAPH_HOST=your-instance.memgraph.cloud
   MEMGRAPH_PORT=7687
   MEMGRAPH_USERNAME=your_username
   MEMGRAPH_PASSWORD=your_password
   ```

## 🔧 Option 3: Local Installation

### Install Qdrant Locally
```bash
# macOS with Homebrew
brew install qdrant

# Or download binary
wget https://github.com/qdrant/qdrant/releases/latest/download/qdrant-x86_64-apple-darwin.tar.gz
tar -xzf qdrant-x86_64-apple-darwin.tar.gz
./qdrant --config-path config.yaml
```

### Install Memgraph Locally
```bash
# macOS with Homebrew
brew install memgraph

# Or download from https://memgraph.com/download
```

## 🔑 OpenAI API Setup

For semantic search, you'll need an OpenAI API key:

1. Visit [platform.openai.com/api-keys](https://platform.openai.com/api-keys)
2. Create a new API key
3. Update `backend/.env`:
   ```bash
   OPENAI_API_KEY=sk-your-actual-api-key-here
   ```

## 🧪 Testing the Setup

Once services are running, test them:

```bash
# Test health endpoint
curl http://localhost:8000/health

# Analyze your backend code
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{"repo_path": "/Users/dim/Desktop/Spill Projects/Halos/backend"}'

# Test lexical search
curl -X POST http://localhost:8000/search/lexical \
  -H "Content-Type: application/json" \
  -d '{"query": "class", "limit": 5}'

# Test semantic search (requires OpenAI + Qdrant)
curl -X POST http://localhost:8000/search/semantic \
  -H "Content-Type: application/json" \
  -d '{"query": "database connection", "limit": 5}'
```

## 🎯 Feature Matrix

| Feature | Lexical Only | + Vector | + Graph |
|---------|-------------|----------|---------|
| Text search | ✅ | ✅ | ✅ |
| Symbol search | ✅ | ✅ | ✅ |
| File analysis | ✅ | ✅ | ✅ |
| Semantic search | ❌ | ✅ | ✅ |
| Similar code | ❌ | ✅ | ✅ |
| Entry points | ❌ | ✅ | ✅ |
| Dependency graph | ❌ | ❌ | ✅ |
| Call graph | ❌ | ❌ | ✅ |
| Flow analysis | ❌ | ❌ | ✅ |

## 🚨 Troubleshooting

### Docker Issues
- **Error**: "request returned 500 Internal Server Error"
  - **Solution**: Restart Docker Desktop or try cloud services

### OpenAI Issues
- **Error**: "Vector search not available"
  - **Solution**: Add valid OpenAI API key to `.env`

### Service Connection Issues
- **Error**: "Service not accessible"
  - **Solution**: Check firewall settings and port availability

### Port Conflicts
- **Error**: "Port already in use"
  - **Solution**: Stop conflicting services or change ports in configuration

## 📊 Service URLs

Once running, access these dashboards:

- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Qdrant Dashboard**: http://localhost:6333/dashboard
- **Memgraph Lab**: http://localhost:3000

## 🔄 Next Steps

1. **Enable Services**: Configure `.env` file with your API keys
2. **Restart Backend**: `cd backend && python -m app.main`
3. **Test Features**: Try semantic search and graph analysis
4. **Frontend**: Set up the React frontend for visualization

## 💡 Pro Tips

- Start with lexical search (already working!)
- Add OpenAI key for semantic features
- Use cloud services if Docker is problematic
- Check `/health` endpoint for service status
- Monitor logs for connection issues

---

**Need help?** Check the API documentation at http://localhost:8000/docs or create an issue in the repository. 