"""
Serper.dev (Google Search API) client with SQLite caching for Jumia Ghana, Jiji, and Amazon.
"""

import hashlib
import json
import os
import sqlite3
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

CACHE_DB_PATH = os.getenv(
    "SEARCH_CACHE_DB",
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "resources", "search_cache.db")),
)
CACHE_TTL_SECONDS = 12 * 3600  # Cache identical searches for 12 hours


def _init_cache_db():
    os.makedirs(os.path.dirname(CACHE_DB_PATH), exist_ok=True)
    with sqlite3.connect(CACHE_DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS search_cache (
                query_hash TEXT PRIMARY KEY,
                query TEXT,
                results_json TEXT,
                created_at REAL
            )
        """)


def _get_cached_results(query: str) -> Optional[List[Dict[str, Any]]]:
    try:
        _init_cache_db()
        q_hash = hashlib.sha256(query.strip().lower().encode("utf-8")).hexdigest()
        now = time.time()
        with sqlite3.connect(CACHE_DB_PATH) as conn:
            row = conn.execute(
                "SELECT results_json, created_at FROM search_cache WHERE query_hash = ?",
                (q_hash,),
            ).fetchone()
            if row:
                results_json, created_at = row
                if (now - created_at) < CACHE_TTL_SECONDS:
                    items = json.loads(results_json)
                    return items[:4]
    except Exception:
        pass
    return None


def _save_cached_results(query: str, results: List[Dict[str, Any]]):
    try:
        _init_cache_db()
        q_hash = hashlib.sha256(query.strip().lower().encode("utf-8")).hexdigest()
        now = time.time()
        with sqlite3.connect(CACHE_DB_PATH) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO search_cache (query_hash, query, results_json, created_at) VALUES (?, ?, ?, ?)",
                (q_hash, query.strip().lower(), json.dumps(results[:4]), now),
            )
    except Exception:
        pass


def _detect_store(url: str) -> str:
    lower_target = url.lower()
    if "jumia.com.gh" in lower_target or "jumia" in lower_target:
        return "Jumia Ghana"
    elif "jiji.com.gh" in lower_target or "jiji" in lower_target:
        return "Jiji Ghana"
    elif "amazon.com" in lower_target or "amazon" in lower_target:
        return "Amazon"
    return "Web"


def execute_google_search(query: str, num_results: int = 4) -> List[Dict[str, Any]]:
    """Execute live Google search via Serper.dev with compact output to minimize tokens."""
    clean_query = query.strip()
    cached = _get_cached_results(clean_query)
    if cached is not None:
        return cached

    api_key = os.getenv("SERPER_API_KEY", "").strip()

    if not api_key:
        return [
            {
                "error": "SERPER_API_KEY is missing. Please add your free Serper API key to .env."
            }
        ]

    # Target Jumia Ghana, Jiji Ghana, and Amazon specifically if not already filtered
    if "site:" not in clean_query.lower():
        scoped_query = f"{clean_query} (site:jumia.com.gh OR site:jiji.com.gh OR site:amazon.com)"
    else:
        scoped_query = clean_query

    payload = json.dumps({
        "q": scoped_query,
        "gl": "gh",  # Country code for Ghana
        "hl": "en",  # English language
        "num": 4,    # Strictly top 4 to keep token payload minimal (~300 tokens)
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://google.serper.dev/search",
        data=payload,
        headers={
            "X-API-KEY": api_key,
            "Content-Type": "application/json",
            "User-Agent": "ShoppingAgent/1.0",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        try:
            parsed = json.loads(error_body)
            msg = parsed.get("message", str(e))
        except Exception:
            msg = error_body or str(e)
        print(f"\n[Serper API Error] Code {e.code}: {msg}\n")
        return [{"error": f"Search API error ({e.code}): {msg}"}]
    except Exception as e:
        print(f"\n[Serper API Error] {str(e)}\n")
        return [{"error": f"Search connection failed: {str(e)}"}]

    organic_items = data.get("organic", [])[:4]
    parsed_results = []

    for item in organic_items:
        title = item.get("title", "").strip()[:70]
        link = item.get("link", "").strip()
        snippet = item.get("snippet", "").strip()[:80]
        price_tag = item.get("price", "")

        if not price_tag and "attributes" in item:
            for k, v in item["attributes"].items():
                if "price" in k.lower():
                    price_tag = str(v)
                    break

        parsed_results.append({
            "store": _detect_store(link),
            "title": title,
            "snippet": snippet,
            "price": price_tag,
            "link": link,
        })

    if parsed_results and "error" not in parsed_results[0]:
        _save_cached_results(clean_query, parsed_results)

    return parsed_results
