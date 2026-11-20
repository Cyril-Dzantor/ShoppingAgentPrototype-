"""LangChain tools for live product search across Jumia, Jiji, and Amazon."""

from typing import Optional
from langchain_core.tools import tool
from src.search_service import execute_google_search


@tool
def search_live_products(query: str, store: Optional[str] = None) -> list[dict]:
    """Search live product listings across Jumia Ghana, Jiji Ghana, and Amazon in one call.

    Args:
        query: Product name to search for (e.g. 'PS5 Slim', 'iPhone 13 128GB', 'air fryer').
        store: Optional store name to filter by ('jumia', 'jiji', or 'amazon').

    Returns a concise list of matching products with store, title, price, and direct link.
    """
    clean_query = query.strip()
    if store:
        s = store.lower()
        if "jumia" in s:
            clean_query += " site:jumia.com.gh"
        elif "jiji" in s:
            clean_query += " site:jiji.com.gh"
        elif "amazon" in s:
            clean_query += " site:amazon.com"

    return execute_google_search(clean_query)


TOOLS = [search_live_products]
