"""
Multi-store search service for Ghanaian e-commerce.
Uses asynchronous parallel fetching (httpx + asyncio) across Jiji Ghana, Jumia Ghana, and Amazon.
"""

import asyncio
import concurrent.futures
import hashlib
import json
import os
import re
import sqlite3
import statistics
import time
import urllib.parse
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv
import httpx

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


CORE_DEVICE_KEYWORDS = {
    "phone", "iphone", "samsung", "galaxy", "pixel", "redmi", "xiaomi", "tecno", "infinix",
    "ps5", "ps4", "playstation", "xbox", "nintendo", "switch", "console",
    "macbook", "laptop", "dell", "hp", "lenovo", "thinkpad", "asus", "acer", "ipad", "tablet",
}

ACCESSORY_WORDS = {
    "case", "cases", "cover", "covers", "glass", "screen protector", "tempered glass",
    "charger", "chargers", "charging", "cable", "cables", "stand", "stands", "cooling",
    "dock", "docking", "skin", "skins", "pouch", "pouches", "strap", "straps", "band", "bands",
    "sleeve", "sleeves", "sticker", "stickers", "shell", "shells", "silicone", "holder",
    "adapter", "adapters", "converter", "battery case", "replacement battery", "grip", "grips",
    "controller", "gamepad", "joystick", "headset", "earphone", "earphones", "earbuds",
    "screen replacement", "lcd", "housing", "camera lens",
}


def is_core_device_query(query: str) -> bool:
    """Check if the search is for a high-value core device (phone, console, laptop, etc.)."""
    words = set(re.findall(r"\b[a-z0-9]+\b", query.lower()))
    return bool(words & CORE_DEVICE_KEYWORDS)


def is_user_requesting_accessory(query: str) -> bool:
    """Check if user explicitly queried for an accessory."""
    q_lower = query.lower()
    return any(re.search(r"\b" + re.escape(w) + r"\b", q_lower) for w in ACCESSORY_WORDS)


def is_accessory_listing(title: str, query: str) -> bool:
    """Exclude listings whose titles contain accessory words when searching for core devices."""
    if not is_core_device_query(query) or is_user_requesting_accessory(query):
        return False
    t_lower = title.lower()
    pattern = r"\b(" + "|".join(re.escape(w) for w in ACCESSORY_WORDS) + r")\b"
    return bool(re.search(pattern, t_lower))


def extract_numeric_price(price_str: Any) -> Optional[float]:
    """Parse numeric price from formatted text."""
    if not price_str or "contact" in str(price_str).lower() or "check" in str(price_str).lower():
        return None
    cleaned = re.sub(r"(?i)GH[₵S]|GHS|\$", "", str(price_str)).strip()
    match = re.search(r"[\d][\d\s,\.]*", cleaned)
    if not match:
        return None
    try:
        return float(match.group(0).replace(" ", "").replace(",", ""))
    except ValueError:
        return None


def apply_anomaly_and_accessory_filtering(listings: List[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
    """Filter out accessories and flag price anomalies >60% below median."""
    filtered: List[Dict[str, Any]] = []
    for item in listings:
        title = item.get("title", "")
        if is_accessory_listing(title, query):
            print(f"[Accessory Filter] Excluded: '{title}' for query: '{query}'")
            continue
        filtered.append(item)

    # Flag price anomalies >60% below median price
    valid_prices = [extract_numeric_price(it.get("price")) for it in filtered]
    valid_prices = [p for p in valid_prices if p is not None and p > 0]

    if len(valid_prices) >= 2:
        median_price = statistics.median(valid_prices)
        threshold = median_price * 0.40  # more than 60% below median

        for item in filtered:
            num_price = extract_numeric_price(item.get("price"))
            if num_price is not None and num_price < threshold:
                drop_pct = round(((median_price - num_price) / median_price) * 100)
                item["is_anomaly"] = True
                item["anomaly_warning"] = (
                    f"Price ({item['price']}) is {drop_pct}% below market median "
                    f"(~GH₵ {median_price:,.0f}). Verify condition with seller and avoid advance payment."
                )
            else:
                item["is_anomaly"] = False
    else:
        for item in filtered:
            item["is_anomaly"] = False

    return filtered


async def _async_get_jiji_listings(client: httpx.AsyncClient, product_name: str, limit: int = 2) -> List[Dict[str, Any]]:
    """Query Jiji Ghana's public catalog API asynchronously with rich metadata and accessory filtering."""
    url = f"https://jiji.com.gh/api_web/v1/listing?query={urllib.parse.quote(product_name)}&page=1"
    items = []
    try:
        resp = await client.get(url, timeout=5.0)
        if resp.status_code == 200:
            data = resp.json()
            adverts = data.get("adverts_list", {}).get("adverts", [])
            for ad in adverts:
                title = ad.get("title", "").strip()[:65]
                if is_accessory_listing(title, product_name):
                    continue

                price = ad.get("price_title") or "Contact for price"
                clean_url = "https://jiji.com.gh" + ad.get("url", "").split("?")[0]
                region = ad.get("region_name", "Ghana")
                parent_region = ad.get("region_parent_name", "")
                location = f"{region}, {parent_region}" if parent_region and parent_region != region else region

                condition = "Used"
                for attr in ad.get("attrs", []):
                    if attr.get("name") == "Condition":
                        condition = attr.get("value", "Used")
                        break

                image_url = ad.get("image_obj", {}).get("url")
                if not image_url and ad.get("images"):
                    image_url = ad.get("images")[0].get("url")

                items.append({
                    "store": "Jiji Ghana",
                    "title": title,
                    "price": price,
                    "condition": condition,
                    "location": location,
                    "image": image_url,
                    "link": clean_url,
                    "notes": f"{region} - Verified listing"[:50],
                })
                if len(items) >= limit:
                    break
        else:
            print(f"[Jiji API Warning] HTTP {resp.status_code}")
    except Exception as e:
        print(f"[Jiji API Error] Gracefully handling: {e}")
    return items


async def _async_get_jumia_listings(client: httpx.AsyncClient, product_name: str, api_key: str, limit: int = 2) -> List[Dict[str, Any]]:
    """Query Jumia Ghana listings via Google/Serper asynchronously with price and image extraction."""
    if not api_key:
        return []

    items = []
    try:
        web_task = client.post(
            "https://google.serper.dev/search",
            json={
                "q": f"site:jumia.com.gh {product_name} price GH₵",
                "gl": "gh",
                "hl": "en",
                "num": 6,
            },
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            timeout=5.0,
        )
        img_task = client.post(
            "https://google.serper.dev/images",
            json={
                "q": f"site:jumia.com.gh {product_name}",
                "gl": "gh",
                "num": 6,
            },
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            timeout=5.0,
        )
        web_resp, img_resp = await asyncio.gather(web_task, img_task, return_exceptions=True)

        images = []
        if isinstance(img_resp, httpx.Response) and img_resp.status_code == 200:
            try:
                images = [im.get("imageUrl") for im in img_resp.json().get("images", []) if im.get("imageUrl")]
            except Exception:
                pass

        if isinstance(web_resp, httpx.Response) and web_resp.status_code == 200:
            data = web_resp.json()
            img_idx = 0
            for it in data.get("organic", []):
                title = it.get("title", "").strip()[:65]
                if is_accessory_listing(title, product_name):
                    continue

                snippet = f"{it.get('snippet', '')} {it.get('title', '')}"
                match = re.search(r'(?:GH[₵S]|GHS)\s*[\d\s,]+(?:\.\d{2})?', snippet, re.IGNORECASE)
                price = match.group(0).strip() if match else it.get("price") or "Check catalog"

                link = it.get("link", "")
                if "google.com/goto" in link or not link.startswith("http"):
                    link = f"https://www.jumia.com.gh/catalog/?q={urllib.parse.quote(product_name)}"

                image_url = images[img_idx] if img_idx < len(images) else None
                img_idx += 1

                items.append({
                    "store": "Jumia Ghana",
                    "title": title,
                    "price": price,
                    "condition": "Brand New",
                    "location": "Nationwide Delivery",
                    "image": image_url,
                    "link": link,
                    "notes": it.get("snippet", "").strip()[:60],
                })
                if len(items) >= limit:
                    break
        else:
            print(f"[Jumia Search Warning] Serper returned unexpected response: {web_resp}")
    except Exception as e:
        print(f"[Jumia Search Error] Gracefully handling: {e}")

    # Fallback to direct Jumia search catalog link if no individual item matched
    if not items:
        items.append({
            "store": "Jumia Ghana",
            "title": f"{product_name} on Jumia Ghana",
            "price": "Check catalog",
            "condition": "Brand New",
            "location": "Nationwide Delivery",
            "image": None,
            "link": f"https://www.jumia.com.gh/catalog/?q={urllib.parse.quote(product_name)}",
            "notes": "Official store search link",
        })
    return items


async def _async_get_amazon_listings(client: httpx.AsyncClient, product_name: str, api_key: str, limit: int = 1) -> List[Dict[str, Any]]:
    """Query Amazon listings via Google/Serper asynchronously if requested."""
    if not api_key:
        return []

    items = []
    try:
        resp = await client.post(
            "https://google.serper.dev/search",
            json={
                "q": f"site:amazon.com {product_name}",
                "gl": "us",
                "hl": "en",
                "num": 4,
            },
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            timeout=5.0,
        )
        if resp.status_code == 200:
            data = resp.json()
            for it in data.get("organic", []):
                title = it.get("title", "").strip()[:65]
                if is_accessory_listing(title, product_name):
                    continue
                snippet = f"{it.get('snippet', '')} {it.get('title', '')}"
                match_usd = re.search(r'\$\s*[\d,]+(?:\.\d{2})?', snippet)
                price = match_usd.group(0).strip() if match_usd else it.get("price") or "Check Amazon"
                items.append({
                    "store": "Amazon",
                    "title": title,
                    "price": price,
                    "condition": "Brand New",
                    "location": "Ships to Ghana",
                    "image": None,
                    "link": it.get("link", f"https://www.amazon.com/s?k={urllib.parse.quote(product_name)}"),
                    "notes": "International shipping to Ghana",
                })
                if len(items) >= limit:
                    break
    except Exception as e:
        print(f"[Amazon Search Error] Gracefully handling: {e}")
    return items


async def async_execute_search(raw_query: str, include_amazon: bool = False) -> List[Dict[str, Any]]:
    """Execute multi-store search asynchronously in parallel with graceful degradation."""
    product_name = _clean_product_query(raw_query)

    cached = _get_cached_results(product_name)
    if cached is not None:
        return cached

    api_key = os.getenv("SERPER_API_KEY", "").strip()

    async with httpx.AsyncClient(
        headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"},
        follow_redirects=True,
    ) as client:
        # Build parallel tasks
        tasks = [
            _async_get_jiji_listings(client, product_name, limit=2),
            _async_get_jumia_listings(client, product_name, api_key, limit=2),
        ]
        if include_amazon or "amazon" in raw_query.lower():
            tasks.append(_async_get_amazon_listings(client, product_name, api_key, limit=1))

        # Run all store searches in parallel; return_exceptions=True ensures one failure never crashes others
        results = await asyncio.gather(*tasks, return_exceptions=True)

    combined: List[Dict[str, Any]] = []
    for r in results:
        if isinstance(r, list):
            combined.extend(r)
        elif isinstance(r, Exception):
            print(f"[Parallel Search Warning] Task encountered error: {r}")

    # Apply accessory filtering and anomaly detection across all stores
    combined = apply_anomaly_and_accessory_filtering(combined, product_name)

    if combined:
        _save_cached_results(product_name, combined)

    return combined


def _run_coroutine_safely(coro):
    """Safely execute an async coroutine from synchronous code, even inside existing event loops."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    # If called from a thread where an event loop is already active, dispatch to dedicated thread pool
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


def execute_google_search(raw_query: str, include_amazon: bool = False) -> List[Dict[str, Any]]:
    """Synchronous entry point that runs async parallel search under the hood."""
    return _run_coroutine_safely(async_execute_search(raw_query, include_amazon=include_amazon))
