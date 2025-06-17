# CodeScope - AI Powered Code Knowledge Graph

CodeScope transforms static code repositories into living, explorable knowledge graphs. It helps developers understand complex codebases through interactive visualization and natural language queries.

## Features

- Interactive, multi-level code visualization
- Natural language search and querying
- AI-powered code summarization
- Real-time code analysis and graph construction
- Three-panel explorer interface

## Project Structure

```
CodeScope/
├── backend/           # Python FastAPI backend
│   ├── app/          # Application code
│   ├── tests/        # Backend tests
│   └── requirements.txt
├── frontend/         # React frontend
│   ├── src/         # Source code
│   ├── public/      # Static assets
│   └── package.json
└── docker/          # Docker configuration
```

## Setup

### Backend Setup

1. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

3. Start the backend server:
   ```bash
   uvicorn app.main:app --reload
   ```

### Frontend Setup

1. Install dependencies:
   ```bash
   cd frontend
   npm install
   ```

2. Start the development server:
   ```bash
   npm run dev
   ```

## Architecture

### Backend Components

- **Repo Ingestion**: Handles GitHub repository cloning and file processing
- **Code Parser**: Uses Tree-sitter for AST generation and analysis
- **Graph Builder**: Constructs the knowledge graph using NetworkX
- **AI Integration**: Interfaces with LLMs for code summarization
- **API Layer**: FastAPI endpoints for frontend communication

### Frontend Components

- **File Tree Panel**: Repository structure and search interface
- **Graph Visualization**: Interactive force-directed graph using D3.js
- **Inspector Panel**: Detailed code and metadata display
- **State Management**: React context for application state

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

MIT License - see LICENSE file for details 
