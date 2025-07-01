# 🤝 Contributing to Halos

We love your input! We want to make contributing to Halos as easy and transparent as possible, whether it's:

- 🐛 Reporting a bug
- 💡 Discussing the current state of the code
- 🚀 Submitting a fix
- 🌟 Proposing new features
- 👥 Becoming a maintainer

## 🏗️ Development Process

We use GitHub to host code, track issues and feature requests, and accept pull requests.

### 1. Fork & Clone
```bash
# Fork the repo on GitHub, then:
git clone https://github.com/your-username/halos.git
cd halos
```

### 2. Setup Development Environment
```bash
# Backend setup
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Frontend setup
cd ../frontend
npm install

# Copy environment template
cp backend/.env.example backend/.env
# Edit backend/.env with your API keys
```

### 3. Create Feature Branch
```bash
git checkout -b feature/amazing-feature
# or
git checkout -b fix/important-bug
```

## 🎯 Pull Request Process

1. **Update Documentation**: Ensure README.md and relevant docs are updated
2. **Add Tests**: Include tests for new functionality
3. **Follow Code Style**: Run linters and formatters
4. **Small Commits**: Keep changes focused and atomic
5. **Descriptive Messages**: Use clear commit messages

### Commit Message Format
We follow [Conventional Commits](https://www.conventionalcommits.org/):

```
type(scope): description

[optional body]

[optional footer(s)]
```

**Types:**
- `feat`: New features
- `fix`: Bug fixes
- `docs`: Documentation only
- `style`: Code style (formatting, missing semicolons, etc.)
- `refactor`: Code refactoring
- `test`: Adding tests
- `chore`: Maintenance tasks

**Examples:**
```bash
feat(search): add semantic similarity search
fix(parser): handle empty files gracefully
docs(api): update endpoint documentation
test(indexer): add lexical search tests
```

## 🧪 Testing

### Backend Tests
```bash
cd backend
python -m pytest tests/ -v
python -m pytest tests/test_analyzer.py::test_parse_file -v  # Specific test
```

### Frontend Tests
```bash
cd frontend
npm test
npm run test:coverage
```

### Integration Tests
```bash
# Start backend
cd backend && python -m app.main &

# Run API tests
curl http://localhost:8000/health
curl -X POST http://localhost:8000/analyze -H "Content-Type: application/json" -d '{"repo_path": "test_data"}'
```

## 🎨 Code Style

### Python (Backend)
We use:
- **Black** for formatting
- **isort** for import sorting
- **flake8** for linting
- **mypy** for type checking

```bash
cd backend

# Format code
black .
isort .

# Check style
flake8 .
mypy .

# All in one
pre-commit run --all-files
```

### TypeScript (Frontend)
We use:
- **ESLint** for linting
- **Prettier** for formatting

```bash
cd frontend

# Format code
npm run format

# Check style
npm run lint

# Fix auto-fixable issues
npm run lint:fix
```

## 🏗️ Architecture Guidelines

### Backend Structure
```
backend/
├── app/
│   ├── main.py              # FastAPI application
│   ├── code_analyzer.py     # Core analysis logic
│   ├── lexical_indexer.py   # BM25 text search
│   ├── vector_indexer.py    # Semantic embeddings
│   ├── dependency_graph.py  # Graph analysis
│   └── ai_integration.py    # OpenAI integration
├── tests/
│   ├── test_analyzer.py
│   └── test_indexers.py
└── requirements.txt
```

### Adding New Features

#### 1. New Search Type
```python
# In code_analyzer.py
async def your_new_search(self, query: str, **kwargs) -> List[Dict]:
    """Your new search implementation."""
    pass

# In main.py
@app.post("/search/your-new-type")
async def your_new_search_endpoint(request: YourRequest):
    """API endpoint for your search."""
    pass
```

#### 2. New Language Support
```python
# Add tree-sitter grammar to requirements.txt
tree-sitter-yourlang==x.y.z

# Update LANGUAGES in code_analyzer.py
try:
    import tree_sitter_yourlang as tsyl
    languages["yourlang"] = tsyl.language()
except ImportError:
    pass

# Add file extension mapping
'.yourlang': 'yourlang'
```

#### 3. New Indexer
```python
# Create new_indexer.py
class NewIndexer:
    def __init__(self, config):
        pass
    
    def index_chunk(self, chunk: CodeChunk):
        pass
    
    def search(self, query: str) -> List[Dict]:
        pass

# Integrate in code_analyzer.py
if enable_new_indexing:
    self.new_indexer = NewIndexer(config)
```

## 🐛 Bug Reports

Great bug reports include:

1. **Summary**: Quick description
2. **Environment**: OS, Python version, dependencies
3. **Steps to Reproduce**: Detailed steps
4. **Expected vs Actual**: What should happen vs what happens
5. **Additional Context**: Screenshots, logs, etc.

**Template:**
```markdown
## Bug Description
Brief description of the issue

## Environment
- OS: macOS 13.0
- Python: 3.11.7
- Halos Version: 1.0.0

## Steps to Reproduce
1. Start backend with `python -m app.main`
2. Call API endpoint `/analyze` with...
3. See error...

## Expected Behavior
Analysis should complete successfully

## Actual Behavior
Error: IndexError: list index out of range

## Additional Context
```bash
Error logs, stack traces, etc.
```
```

## 💡 Feature Requests

Feature requests are welcome! Please:

1. **Check existing issues** to avoid duplicates
2. **Describe the problem** you're trying to solve
3. **Propose a solution** with examples
4. **Consider alternatives** you've thought about

**Template:**
```markdown
## Problem
Clear description of the problem/need

## Proposed Solution
Detailed description of your proposed solution

## Alternatives Considered
Other solutions you've considered

## Additional Context
Mock-ups, examples, related issues, etc.
```

## 📝 Documentation

### API Documentation
- Update docstrings for new endpoints
- Include request/response examples
- Document error cases

### README Updates
- Update feature lists
- Add new configuration options
- Include usage examples

### Code Comments
- Document complex algorithms
- Explain business logic
- Include TODO comments for future improvements

## 🏷️ Labels & Project Management

We use labels to categorize issues and PRs:

- `bug` - Something isn't working
- `enhancement` - New feature or request
- `documentation` - Documentation improvements
- `good first issue` - Good for newcomers
- `help wanted` - Extra attention needed
- `question` - Further information requested
- `priority:high` - High priority items
- `area:backend` - Backend-related
- `area:frontend` - Frontend-related
- `area:docs` - Documentation-related

## 🌟 Recognition

Contributors are recognized in:
- README.md contributors section
- Release notes for significant contributions
- GitHub contributor statistics

## 📞 Questions?

- 💬 **GitHub Discussions**: General questions and ideas
- 🐛 **GitHub Issues**: Bug reports and feature requests
- 📧 **Email**: For sensitive security issues

## 📋 Quick Checklist

Before submitting a PR:

- [ ] Code follows style guidelines
- [ ] Tests pass locally
- [ ] Documentation updated
- [ ] Commit messages follow convention
- [ ] PR description is clear
- [ ] Changes are backwards compatible (or breaking changes documented)

## 🙏 Thank You!

Every contribution makes Halos better. Whether you're fixing typos, adding features, or improving documentation - thank you for making the open source community a better place!

---

**Happy Coding!** 🚀 