# 🎯 AI-Powered CV Screening Platform

An intelligent, automated CV screening and candidate ranking system that leverages Large Language Models (LLMs) to extract, analyze, and match candidate profiles against job requirements.

[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green.svg)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-blue.svg)](https://www.postgresql.org/)
[![Docker](https://img.shields.io/badge/Docker-Compose-green.svg)](https://www.docker.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

[📖 Architecture Guide](ARCHITECTURE.md) • [🔌 API Reference](API_DOCUMENTATION.md) • [🧪 Testing Guide](tests/README.md) • [📝 Contributing](CONTRIBUTING.md)

---

## ⚡ Quick Start

### Using Docker (Recommended)

```bash
git clone https://github.com/yourusername/CVs_project.git
cd CVs_project
docker-compose up -d

# Access endpoints
API:       http://localhost:8000
Frontend:  http://localhost:3001
API Docs:  http://localhost:8000/docs
```

### Local Development

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pre-commit install
uvicorn service.api:app --reload
```

### First Request

```bash
# Health check
curl http://localhost:8000/health

# Submit CV analysis
curl -X POST http://localhost:8000/api/v1/pipelines \
  -H "Content-Type: application/json" \
  -d '{"input_type":"cv","files":["cv.pdf"]}'

# Check results at http://localhost:8000/docs
```

---

## 📋 Documentation

| Document | Content |
|----------|---------|
| **[ARCHITECTURE.md](ARCHITECTURE.md)** | System design, data flow, components, scalability |
| **[API_DOCUMENTATION.md](API_DOCUMENTATION.md)** | REST API endpoints, request/response examples, webhooks |
| **[tests/README.md](tests/README.md)** | Testing setup, fixtures, examples, CI/CD |
| **[CONTRIBUTING.md](CONTRIBUTING.md)** | Code style, commit conventions, development workflow |
| **[CHANGELOG.md](CHANGELOG.md)** | Version history and release notes |

## 📋 Contents

- [Features](#-features)
- [System Architecture](#-system-architecture)
- [Installation Steps](#-installation-steps)
- [Configuration](#-configuration)
- [API Endpoints](#-api-endpoints)
- [Workflow Modes](#-workflow-modes)
- [Development](#-development)
- [Deployment](#-deployment)
- [Troubleshooting](#-troubleshooting)
- [Contributing](#-contributing)
- [License](#-license)

---

## ✨ Features

- **Multi-format CV Extraction** - PDF, DOCX, images with AI-powered structuring
- **Job Offer Parsing** - Extract requirements from text, images, and Excel files
- **LLM-Based Matching** - Intelligent candidate-to-job matching with scoring
- **RESTful API** - FastAPI with automatic OpenAPI/Swagger documentation
- **Modern Frontend** - React 18 + Next.js 14 with Tailwind CSS
- **Real-time Pipeline** - WebSocket updates and webhook notifications
- **Session Management** - Organized data with timestamp-based sessions
- **Automatic Archiving** - Consolidate and compress completed sessions
- **Scalable** - Docker containerized, ready for Kubernetes deployment

---

## 🏗 System Architecture

The platform consists of 4 integrated layers:

```
Frontend (React/Next.js)
    ↓ REST API Calls
API Service (FastAPI)
    ↓ Queue/Events
Processing Pipeline (Python)
    ↓ Store Results
Database (PostgreSQL)
```

**See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed system design, data flows, and scaling strategies.**

---

## 🔌 API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/v1/pipelines` | Submit CV/job extraction |
| GET | `/api/v1/jobs/{id}` | Check job status |
| GET | `/api/v1/jobs/{id}/results` | Retrieve results |
| GET | `/health` | Health check |
| GET | `/docs` | Interactive API docs |

**See [API_DOCUMENTATION.md](API_DOCUMENTATION.md) for complete reference with examples.**

### Example API Call

```bash
# Submit CVs for analysis
curl -X POST http://localhost:8000/api/v1/pipelines \
  -H "Content-Type: application/json" \
  -d '{
    "input_type": "cv",
    "files": ["path/to/cvs/"],
    "job_id": "job_123"
  }'

# Response: { "job_id": "uuid", "status": "submitted" }
```

---

## 📦 Installation Steps

### Prerequisites

- Python 3.10 or higher
- [Poppler](https://github.com/osber/poppler-windows/releases) (for PDF processing)
- [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki) (optional, for image OCR)

### Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/CVs_project.git
   cd CVs_project
   ```

2. **Create and activate a virtual environment**
   ```bash
   python -m venv .venv
   
   # Windows
   .venv\Scripts\activate
   
   # Linux/macOS
   source .venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r script/requirements.txt
   ```

4. **Install Poppler** (Windows)
   - Download from [Poppler Releases](https://github.com/osber/poppler-windows/releases)
   - Extract to `C:\Program Files\poppler`
   - Update path in `config/config_yaml.yaml` if different

5. **Install Tesseract** (Optional - for OCR)
   - Download from [Tesseract Wiki](https://github.com/UB-Mannheim/tesseract/wiki)
   - Add to system PATH

---

## ⚙️ Configuration

### Environment Setup

Create `.env` file with required API keys:

```bash
# Required
OPENROUTER_API_KEY=sk_xxx_your_api_key
DATABASE_URL=postgresql://user:password@localhost:5432/cvdb

# Optional (defaults provided)
API_PORT=8000
LOG_LEVEL=INFO
DEBUG=false
```

Get a free API key at [OpenRouter.ai](https://openrouter.ai)

### Master Configuration

See `config/config_yaml.yaml` for:
- API provider and model selection
- Processing pipeline settings
- Path definitions
- LLM prompt customization
- Retry and rate limiting configuration

**View [ARCHITECTURE.md](ARCHITECTURE.md#3-configuration) for detailed configuration reference.**

---

## 🎯 Workflow Modes

### Mode 1: CV Analysis Pipeline

Extract candidate data from CV files and match against job requirements:

```bash
curl -X POST http://localhost:8000/api/v1/pipelines \
  -H "Content-Type: application/json" \
  -d '{
    "input_type": "cv",
    "files": ["cv_folder/", "individual_cv.pdf"],
    "job_id": "job_123"
  }'
```

**Process:**
1. Parse PDF/DOCX files
2. Extract text with OCR fallback
3. Structure with LLM (name, skills, experience, education)
4. Match against job requirements
5. Generate ranked candidate list
6. Archive session

**Output:** JSON with extracted profiles and match scores

### Mode 2: Job Offer Extraction (Reuse CVs)

Match existing candidate data against new job offer:

```bash
curl -X POST http://localhost:8000/api/v1/pipelines \
  -H "Content-Type: application/json" \
  -d '{
    "input_type": "job_offer",
    "files": ["job_offer.pdf"]
  }'
```

**Process:**
1. Extract offer text (PDF, image, or Excel)
2. Find matching archived CV data
3. Score candidates against new requirements
4. Return ranked results

**Supports:**
- Text PDFs and scanned images (OCR)
- Excel job postings
- Plain text file

---

---

## 🛠 Development

### Setup

```bash
# Clone and setup
git clone https://github.com/yourusername/CVs_project.git
cd CVs_project

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install with dev dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install
```

### Running Tests

```bash
# All tests with coverage
make test

# Unit tests only
make test-unit

# Integration tests with API
make test-integration

# View coverage report
open htmlcov/index.html
```

### Code Quality

```bash
# Format code with black + isort
make format

# Run linting (flake8)
make lint

# Type checking with mypy
make type-check

# All quality checks
make quality
```

See [tests/README.md](tests/README.md) for comprehensive testing guide and [CONTRIBUTING.md](CONTRIBUTING.md) for development standards.

---

## 🐳 Deployment

### With Docker Compose

```bash
# Production mode
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# View logs
docker-compose logs -f api

# Stop services
docker-compose down
```

### Services

| Service | URL | Purpose |
|---------|-----|---------|
| API | http://localhost:8000 | FastAPI endpoints |
| Frontend | http://localhost:3001 | React UI |
| Docs | http://localhost:8000/docs | Swagger documentation |
| n8n | http://localhost:5679 | Workflow automation |

### Health Checks

```bash
# API health
curl http://localhost:8000/health

# Database
docker-compose exec postgres psql -U cvuser -d cvdb -c "SELECT 1"

# All services
docker-compose ps
```

---

## 🐛 Troubleshooting

### Common Issues

**Port already in use**
```bash
# Find and kill process
lsof -i :8000
kill -9 <PID>
```

**Database connection error**
```bash
# Ensure PostgreSQL is running
docker-compose ps postgres

# Reset database
docker-compose down -v
docker-compose up -d postgres
```

**LLM API errors**
```bash
# Check API key
echo $OPENROUTER_API_KEY

# Verify connectivity
curl https://openrouter.ai/api/v1/auth/key \
  -H "Authorization: Bearer $OPENROUTER_API_KEY"
```

**Module import errors**
```bash
# Reinstall in editable mode
pip install -e .
```

### Debugging

Enable debug logging in `.env`:
```bash
DEBUG=true
LOG_LEVEL=DEBUG
```

View logs:
```bash
# API logs
docker-compose logs -f api

# All logs
docker-compose logs -f

# Specific container
docker-compose logs -f postgres
```

---

## 🤝 Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for:
- Code style and commit conventions
- Testing requirements
- PR process
- Development setup
- Contributing guidelines

Quick checklist:
1. Fork repository
2. Create feature branch: `git checkout -b feature/amazing-feature`
3. Make changes and test: `make test`
4. Commit with message: `git commit -m "feat: add amazing feature"`
5. Push and create Pull Request

---

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

---

## 📚 Additional Resources

| Guide | Purpose |
|-------|---------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | System design and data flows |
| [API_DOCUMENTATION.md](API_DOCUMENTATION.md) | Complete API reference with cURL examples |
| [DOCKER_SETUP.md](DOCKER_SETUP.md) | Docker configuration details |
| [tests/README.md](tests/README.md) | Testing framework and examples |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Development workflow and standards |
| [CHANGELOG.md](CHANGELOG.md) | Version history and releases |

---

## ❓ FAQ

**Q: Can I use a different LLM provider?**
A: Yes! Update `LLM_MODEL` in `.env` to any OpenRouter-supported model.

**Q: How do I scale for high volume?**
A: See [ARCHITECTURE.md - Scalability](ARCHITECTURE.md#scalability) for horizontal scaling strategies.

**Q: How do I deploy to production?**
A: Use `docker-compose.prod.yml` or see Kubernetes examples in [ARCHITECTURE.md](ARCHITECTURE.md).

**Q: Where are results stored?**
A: By default in `data/final_result/` directory and PostgreSQL database.

**Q: Can I customize the CV extraction format?**
A: Yes, edit the extraction prompts in `config/prompts/` directory.

---

## 🙏 Acknowledgments

- [OpenRouter](https://openrouter.ai/) for LLM API access
- [FastAPI](https://fastapi.tiangolo.com/) for the amazing web framework
- [PostgreSQL](https://www.postgresql.org/) for reliable data storage
- [n8n](https://n8n.io/) for workflow automation

---

<p align="center">
  Made with ❤️ by the IT Road Group team
</p>

---

### 📞 Support

- **Issues:** Open a [GitHub Issue](https://github.com/yourusername/CVs_project/issues)
- **Questions:** Check [FAQ](#-faq) and [Troubleshooting](#-troubleshooting)
- **Documentation:** See [ARCHITECTURE.md](ARCHITECTURE.md) and [API_DOCUMENTATION.md](API_DOCUMENTATION.md)
- **Email:** support@itroadgroup.com

---

### 🚀 Next Steps

1. ✅ Review [Quick Start](#-quick-start)
2. ✅ Run Docker setup: `docker-compose up -d`
3. ✅ Test API: `curl http://localhost:8000/docs`
4. ✅ Submit first job: See [API_DOCUMENTATION.md](API_DOCUMENTATION.md#api-endpoints)
5. ✅ Explore code: Check [project structure](ARCHITECTURE.md#project-structure)

---

## 🛠 Development

### Commit Message Convention

- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation changes
- `refactor:` Code refactoring
- `test:` Test additions/changes

---

## 📄 License

This project is licensed owned by IT Road Group

---

## 🙏 Acknowledgments

- [OpenRouter](https://openrouter.ai/) for LLM API access
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) for image text extraction
- [pdfplumber](https://github.com/jsvine/pdfplumber) for PDF parsing

---

<p align="center">
  Made with ❤️ for HR team of IT Road Group
</p>
