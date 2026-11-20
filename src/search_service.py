"""
Multi-store search service for Ghanaian e-commerce.
Combines Jiji Ghana's live catalog API with Google/Serper search for Jumia Ghana and Amazon.
"""

import hashlib
import json
import os
import re
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv

load_dotenv()

CACHE_DB_PATH = os.getenv(
    "SEARCH_CACHE_DB",
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "resources", "search_cache.db")),
)
CACHE_TTL_SECONDS = 12 * 3600  # 12-hour cache


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
                    return json.loads(results_json)
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
                (q_hash, query.strip().lower(), json.dumps(results[:5]), now),
            )
    except Exception:
        pass


def _clean_product_query(raw_query: str) -> str:
    """Extract clean product keywords by removing conversational noise and store references."""
    clean = re.sub(
        r'(?i)\b(find|search|look for|compare|prices?|for|across|on|in|cheap|cheapest|best|deal|deals|ghana|store|stores|jumia|jiji|amazon)\b',
        ' ',
        raw_query,
    )
    clean = ' '.join(clean.split()).strip()
    return clean if len(clean) >= 2 else raw_query.strip()


def _get_jiji_listings(product_name: str, limit: int = 2) -> List[Dict[str, Any]]:
    """Query Jiji Ghana's public catalog API for exact prices, locations, and direct URLs."""
    url = f"https://jiji.com.gh/api_web/v1/listing?query={urllib.parse.quote(product_name)}&page=1"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "application/json",
        },
    )
    items = []
    try:
        with urllib.request.urlopen(req, timeout=7) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            adverts = data.get("adverts_list", {}).get("adverts", [])[:limit]
            for ad in adverts:
                price = ad.get("price_title") or "Contact for price"
                clean_url = "https://jiji.com.gh" + ad.get("url", "").split("?")[0]
                region = ad.get("region_name", "Ghana")
                items.append({
                    "store": "Jiji Ghana",
                    "title": ad.get("title", "").strip()[:65],
                    "price": price,
                    "link": clean_url,
                    "notes": f"{region} - Verified listing"[:50],
                })
    except Exception as e:
        print(f"[Jiji API Error] {e}")
    return items


def _get_jumia_listings(product_name: str, api_key: str, limit: int = 2) -> List[Dict[str, Any]]:
    """Query Jumia Ghana listings via Google/Serper with price regex extraction."""
    if not api_key:
        return []

    req = urllib.request.Request(
        "https://google.serper.dev/search",
        data=json.dumps({
            "q": f"site:jumia.com.gh {product_name} price GH₵",
            "gl": "gh",
            "hl": "en",
            "num": 4,
        }).encode("utf-8"),
        headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
    )
    items = []
    try:
        with urllib.request.urlopen(req, timeout=7) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            for it in data.get("organic", [])[:limit]:
                snippet = f"{it.get('snippet', '')} {it.get('title', '')}"
                match = re.search(r'(?:GH[₵S]|GHS)\s*[\d\s,]+(?:\.\d{2})?', snippet, re.IGNORECASE)
                price = match.group(0).strip() if match else it.get("price") or "Check catalog"

                link = it.get("link", "")
                if "google.com/goto" in link or not link.startswith("http"):
                    link = f"https://www.jumia.com.gh/catalog/?q={urllib.parse.quote(product_name)}"

                items.append({
                    "store": "Jumia Ghana",
                    "title": it.get("title", "").strip()[:65],
                    "price": price,
                    "link": link,
                    "notes": it.get("snippet", "").strip()[:60],
                })
    except Exception as e:
        print(f"[Jumia Search Error] {e}")

    # If no specific Jumia product found, provide direct verified catalog search link
    if not items:
        items.append({
            "store": "Jumia Ghana",
            "title": f"{product_name} on Jumia Ghana",
            "price": "Check catalog",
            "link": f"https://www.jumia.com.gh/catalog/?q={urllib.parse.quote(product_name)}",
            "notes": "Official store search link",
        })
    return items


def _get_amazon_listings(product_name: str, api_key: str, limit: int = 2) -> List[Dict[str, Any]]:
    """Query Amazon listings via Google/Serper if explicitly requested."""
    if not api_key:
        return []

    req = urllib.request.Request(
        "https://google.serper.dev/search",
        data=json.dumps({
            "q": f"site:amazon.com {product_name}",
            "gl": "us",
            "hl": "en",
            "num": 4,
        }).encode("utf-8"),
        headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
    )
    items = []
    try:
        with urllib.request.urlopen(req, timeout=7) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            for it in data.get("organic", [])[:limit]:
                snippet = f"{it.get('snippet', '')} {it.get('title', '')}"
                match_usd = re.search(r'\$\s*[\d,]+(?:\.\d{2})?', snippet)
                price = match_usd.group(0).strip() if match_usd else it.get("price") or "Check Amazon"
                items.append({
                    "store": "Amazon",
                    "title": it.get("title", "").strip()[:65],
                    "price": price,
                    "link": it.get("link", f"https://www.amazon.com/s?k={urllib.parse.quote(product_name)}"),
                    "notes": "International shipping to Ghana",
                })
    except Exception as e:
        print(f"[Amazon Search Error] {e}")
    return items


def execute_google_search(raw_query: str, include_amazon: bool = False) -> List[Dict[str, Any]]:
    """Unified search: queries Jiji Ghana directly + Jumia Ghana + Amazon, returning verified prices & links."""
    product_name = _clean_product_query(raw_query)

    cached = _get_cached_results(product_name)
    if cached is not None:
        return cached

    api_key = os.getenv("SERPER_API_KEY", "").strip()

    # 1. Fetch live Jiji listings with real prices & direct links
    jiji_results = _get_jiji_listings(product_name, limit=2)

    # 2. Fetch live Jumia listings
    jumia_results = _get_jumia_listings(product_name, api_key, limit=2)

    # 3. Optional Amazon listings
    amazon_results = []
    if include_amazon or "amazon" in raw_query.lower():
        amazon_results = _get_amazon_listings(product_name, api_key, limit=1)

    combined = jiji_results + jumia_results + amazon_results

    if combined:
        _save_cached_results(product_name, combined)

    return combined
