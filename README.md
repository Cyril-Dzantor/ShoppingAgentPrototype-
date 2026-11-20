# Autonomous Shopping Assistant (Ghana)

Conversational shopping agent that searches live product listings and compares prices across **Jumia Ghana**, **Jiji Ghana**, and **Amazon**. Built with LangChain, Groq Cloud (`openai/gpt-oss-120b`), Serper (Google Search API), and Streamlit.

## Features

- **Live Store Search:** Queries Jumia Ghana, Jiji Ghana, and Amazon simultaneously using Google Search (via Serper).
- **SQLite Search Caching:** Caches search results locally for 12 hours (`resources/search_cache.db`) to conserve API credits.
- **Price & Store Comparison:** Normalizes listings into a clean comparison table with direct product links and local/international trade-offs.

## Setup

1. Copy `.env.example` to `.env` and provide your credentials:
   ```env
   GROQ_API_KEY=gsk_...
   SERPER_API_KEY=your_serper_key_here
   ```
   *(Get 2,500 free queries at [serper.dev](https://serper.dev/))*

2. Run the application:
   ```bash
   uv run streamlit run app.py
   ```
