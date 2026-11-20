"""LangChain tools for live product search across Jumia, Jiji, and Amazon."""

from typing import Optional
from langchain_core.tools import tool
from src.search_service import execute_google_search


@tool
def search_live_products(query: str, include_amazon: bool = False) -> list[dict]:
    """Search live products across Ghanaian stores (Jumia Ghana, Jiji Ghana) and optionally Amazon.

    Args:
        query: Product or item name (e.g. 'PS5 Slim', 'air fryer 5L', 'iPhone 13 128GB').
        include_amazon: Set to True if user explicitly requests international Amazon pricing.

    Returns a clean list of product listings with store, title, extracted price, notes, and direct URL.
    """
    return execute_google_search(query, include_amazon=include_amazon)


TOOLS = [search_live_products]
