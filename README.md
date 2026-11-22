# Autonomous Shopping Assistant (Ghana)

An intelligent conversational shopping agent tailored for the Ghanaian e-commerce market. The agent searches live product listings and compares prices in real time across **Jumia Ghana**, **Jiji Ghana**, and **Amazon**, helping shoppers discover authentic products, compare prices in Ghanaian Cedi (`GH₵`), and weigh trade-offs between local physical inventory and international imports.

Built with **LangChain**, **Groq Cloud** (`openai/gpt-oss-120b`), **Serper Google Search**, and **Streamlit**.

---

## Key Features

- **Asynchronous Parallel Search Engine:** Queries Jiji Ghana, Jumia Ghana, and Amazon concurrently using `httpx` and `asyncio.gather`, cutting multi-store search latency down to ~1.8–2.0 seconds.
- **Direct Jiji Ghana REST Integration:** Directly connects to Jiji Ghana's web listing API for accurate `GH₵` prices, verified seller locations (e.g. Spintex, East Legon, Kumasi), and clean direct listing URLs without bot friction.
- **Jumia Ghana Search via Serper:** Scrapes and extracts live Jumia Ghana catalog items using localized Google Search (`gl: gh`) with regex price normalization.
- **Graceful Degradation:** Resilient search pipeline—if any store API or search engine times out or encounters network limits, the agent returns listings from the remaining stores seamlessly without crashing.
- **SQLite Search Caching:** Caches search results locally for 12 hours in `resources/search_cache.db` to save API credits and provide instant sub-millisecond responses on repeat queries.
- **Token-Budget Optimization:** Search results and prompt templates are strictly scoped and formatted to ensure consistent operation within Groq's 8,000 TPM limit on `openai/gpt-oss-120b`.
- **Clean Native Streamlit UI:** Distraction-free, responsive interface featuring structured price comparison tables, seller notes, and direct outbound merchant links.

---

## Architecture & Project Structure

```
ShoppingAgentPrototype/
├── app.py                   # Streamlit frontend & chat interface
├── updates.md               # Product roadmap and rollout tracking
├── pyproject.toml           # Project dependencies and packaging
├── compose.yaml             # Docker Compose orchestration
├── Dockerfile               # Container build definition
├── resources/
│   ├── .gitkeep             # Preserves directory in version control
│   └── search_cache.db      # Local SQLite cache for search results (auto-generated)
└── src/
    ├── __init__.py
    ├── agent.py             # LangChain agent configuration & Groq LLM binding
    ├── search_service.py    # Async parallel search engine (Jiji, Jumia, Amazon)
    ├── setup_db.py          # Database initialization & seed helper
    └── tools.py             # LangChain tool interfaces
```

---

## Getting Started

### Prerequisites

- Python 3.11 or newer (or [uv](https://github.com/astral-sh/uv))
- A **Groq Cloud API Key** ([console.groq.com](https://console.groq.com/))
- A **Serper API Key** ([serper.dev](https://serper.dev/) — 2,500 free search queries)

### 1. Installation

#### Using `uv` (Recommended)

```bash
# Clone the repository
git clone https://github.com/your-username/ShoppingAgentPrototype.git
cd ShoppingAgentPrototype

# Install dependencies into virtual environment
uv sync
```

#### Using standard `pip` and `venv`

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install .
```

### 2. Environment Variables

Create your local `.env` file from the provided example:

```bash
cp .env.example .env
```

Edit `.env` and fill in your API credentials:

```env
GROQ_API_KEY=gsk_your_groq_api_key_here
SERPER_API_KEY=your_serper_api_key_here
```

### 3. Run the Application

Launch the Streamlit web interface:

```bash
# With uv
uv run streamlit run app.py

# Or with activated venv
streamlit run app.py
```

The app will open automatically at `http://localhost:8501`.

---

## Running with Docker

You can also run the assistant inside a Docker container:

```bash
# Build and run with Docker Compose
docker compose up --build
```

Access the application in your browser at `http://localhost:8501`.

---

## Development & Roadmap

For details on ongoing improvements and upcoming features (such as interactive product card thumbnails, accessory filtering, and direct affiliate/WhatsApp checkout integration), see [updates.md](updates.md).
