# ScrapeCrawlAI

A high-performance, BFS-based web crawler and content scraper with multi-worker architecture.

## Features

- **BFS Crawling**: Breadth-first search traversal with configurable depth limits
- **Multi-Worker Architecture**: Concurrent crawling with semaphore-based resource management
- **Multi-KB Support**: Crawl multiple Knowledge Base scopes in parallel with path isolation
- **Real-time Updates**: WebSocket-based progress tracking
- **Content Classification**: Automatic categorization (academic, faculty, research, etc.)
- **Multiple Export Formats**: JSON, Markdown, CSV, and organized ZIP exports
- **Polite Crawling**: Robots.txt compliance, rate limiting, and user-agent rotation
- **Failure Tracking**: Detailed failure classification (timeout, DNS, SSL, HTTP errors)

## Architecture

```
scrapecrawlai/
├── server/                 # FastAPI Backend (Python)
│   ├── app/
│   │   ├── main.py        # Application entry point
│   │   ├── config.py      # Centralized configuration
│   │   ├── exceptions.py  # Custom exceptions
│   │   ├── api/           # REST API endpoints
│   │   │   ├── routes.py      # Single-URL crawl endpoints
│   │   │   └── kb_routes.py   # Multi-KB crawl endpoints
│   │   ├── models/        # Pydantic data models
│   │   │   ├── crawl.py       # Core crawl models
│   │   │   ├── knowledge_base.py # KB models
│   │   │   └── output.py      # Output/export models
│   │   ├── services/      # Business logic
│   │   │   ├── job_manager.py         # Single-URL job orchestration
│   │   │   ├── multi_kb_job_manager.py # Multi-KB job orchestration
│   │   │   ├── scraper.py             # HTTP fetching & content extraction
│   │   │   ├── crawler.py             # BFS crawler engine
│   │   │   ├── kb_crawler.py          # KB-scoped crawler
│   │   │   ├── worker_pool.py         # Concurrency management
│   │   │   ├── formatter.py           # Basic output formatting
│   │   │   ├── enhanced_formatter.py  # Advanced organization
│   │   │   ├── classifier.py          # Content type classification
│   │   │   ├── exporter.py            # ZIP export generation
│   │   │   ├── websocket.py           # Real-time updates
│   │   │   ├── rate_limiter.py        # Per-domain rate limiting
│   │   │   ├── robots.py              # Robots.txt compliance
│   │   │   └── timer.py               # Timing utilities
│   │   └── utils/
│   │       └── logger.py  # Logging configuration
│   └── requirements.txt
│
├── client/                # React Frontend (TypeScript)
│   ├── src/
│   │   ├── components/    # UI components
│   │   ├── hooks/         # Custom React hooks
│   │   ├── services/      # API client
│   │   └── types/         # TypeScript definitions
│   └── package.json
│
└── data/                  # Crawl output storage
    ├── main_crawls/       # Single-URL results
    └── knowledge_bases/   # Multi-KB results
```

## Request Flow

```
Client Request
    │
    ▼
┌─────────────────┐
│   API Routes    │  routes.py / kb_routes.py
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Job Manager   │  Orchestrates crawl jobs
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Worker Pool    │  Manages concurrent workers
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Scraper Service │  HTTP requests + content extraction
└────────┬────────┘
         │
    ┌────┴────┐
    ▼         ▼
┌────────┐ ┌────────┐
│Robots  │ │ Rate   │
│Checker │ │Limiter │
└────────┘ └────────┘
         │
         ▼
┌─────────────────┐
│   Formatter     │  Output generation
└────────┬────────┘
         │
         ▼
    Response/Export
```

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+

### Backend Setup

```bash
cd server

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the server
uvicorn app.main:app --reload --port 8000
```

### Frontend Setup

```bash
cd client

# Install dependencies
npm install

# Run development server
npm run dev
```

## API Endpoints

### Single-URL Crawling

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/start-crawl` | Start a new crawl job |
| GET | `/api/status/{job_id}` | Get job status |
| GET | `/api/results/{job_id}` | Get complete results |
| GET | `/api/download/{job_id}/json` | Download as JSON |
| GET | `/api/download/{job_id}/markdown` | Download as Markdown |
| GET | `/api/export/{job_id}/organized` | Get organized results |
| GET | `/api/export/{job_id}/zip` | Download as ZIP |
| WS | `/api/ws/{job_id}` | Real-time updates |

### Multi-KB Crawling

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/kb/start-crawl` | Start multi-KB crawl |
| GET | `/api/kb/status/{job_id}` | Get overall status |
| GET | `/api/kb/status/{job_id}/kb/{kb_id}` | Get per-KB status |
| GET | `/api/kb/results/{job_id}` | Get all results |
| GET | `/api/kb/results/{job_id}/kb/{kb_id}` | Get KB-specific results |
| WS | `/api/kb/ws/{job_id}` | Real-time KB updates |

## Configuration

Configuration is centralized in `server/app/config.py`. Key settings:

```python
# HTTP settings
REQUEST_TIMEOUT = 30        # seconds
MAX_RETRIES = 3
CONNECTION_POOL_SIZE = 100

# Rate limiting
DEFAULT_DELAY = 0.25        # seconds between requests per domain
MAX_DELAY = 5.0

# Crawl limits
MIN_DEPTH = 1
MAX_DEPTH = 5
MIN_WORKERS = 2
MAX_WORKERS = 10

# Content extraction
MAX_CONTENT_LENGTH = 50000
MAX_HEADINGS = 50
```

## Crawl Modes

| Mode | Description |
|------|-------------|
| `only_crawl` | Discover URLs without scraping content |
| `only_scrape` | Extract content from discovered pages |
| `crawl_scrape` | Full crawl + scrape (default) |

## Output Organization

Results can be organized by:

- **Flat**: Simple list of all pages
- **By Subdomain**: Grouped by domain/subdomain
- **By Depth**: Grouped by crawl depth level
- **By Content Type**: Grouped by classification (academic, faculty, etc.)
- **By Status**: Grouped into success/external/error categories

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DEBUG` | Enable debug mode | `false` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `SCRAPECRAWL_REQUEST_TIMEOUT` | Request timeout (seconds) | `30` |
| `SCRAPECRAWL_DEFAULT_DELAY` | Rate limit delay (seconds) | `0.25` |

## Testing

```bash
cd server
pytest tests/
```

## Technology Stack

### Backend
- **FastAPI** - Web framework
- **Uvicorn** - ASGI server
- **aiohttp** - Async HTTP client
- **BeautifulSoup4** - HTML parsing
- **Pydantic** - Data validation

### Frontend
- **React 18** - UI framework
- **TypeScript** - Type safety
- **Vite** - Build tool
- **Axios** - HTTP client

## License

MIT License
