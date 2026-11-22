1. Asynchronous Parallel Fetching [COMPLETED]:
- Async Execution (httpx + asyncio):
  - Fetches Jiji Ghana REST API, Jumia search via Serper, and Amazon in parallel.
  - Achieved search wall-clock latency of ~1.8–2.0s (down from ~4.5s sequential).
- Graceful Degradation:
  - If any store API or Serper times out or encounters network restrictions, the remaining stores return seamlessly without crashing.
  - Robust thread-safe synchronous bridging (`_run_coroutine_safely`) ensures compatibility with LangChain tools and Streamlit.

2. UI / UX: Interactive Cards (Beyond Plain Text Tables) [COMPLETED]:
- Clean Product Cards in Streamlit:
  - Real product image thumbnails extracted from Jiji's direct CDN and Jumia's product image pipeline.
  - High-utility, distraction-free card design with zero AI artifacts (no emoji icons, no color gradients, no neon borders, no glassmorphism).
  - Clear solid status tags: Store identity, Condition (Brand New vs. Second-hand Deals), and Location (Spintex, Madina, Nationwide Delivery).
  - Direct outbound "View on Store" action buttons for every listing.
- Real-Time Sidebar Filter Controls:
  - Multi-store selection: Jumia Ghana, Jiji Ghana, and Amazon.
  - Condition toggle: All Conditions | Brand New Only | Second-hand Deals.
  - Price sorting: Store Default | Price: Low to High | Price: High to Low.
  - Instant client-side filtering without re-querying the LLM or external search APIs.

3. Infrastructure, Observability & Rate Limiting:
User Authentication & Per-User Rate Limiting:
Prevent malicious users or scrapers from draining your Serper and Groq API credits.
Implement IP/user rate limiting

LLM Provider Fallback (High Availability):
If Groq hits a momentary 429/413 rate limit or outage, automatically route the turn to a secondary fallback model

LLM Tracing & Telemetry (LangSmith / Langfuse):
Track user search terms, latency, tool execution failures, and token expenditure in real-time.

4. Accessory & Anomaly Filtering:
When a user searches for a high-value item (phone, console, laptop), automatically exclude listings whose titles contain accessory words

If an item's price is more than 60% below the median price for that category (e.g. a PS5 for GH₵ 500), flag it with a warning

5. Ambiguity Resolution & Guardrails


The agent's system prompt had specific conversational logic:

Disambiguation: If a user asked to "Order the honey", but there were 4 different honey variants in stock, the agent was instructed not to guess—it stopped and asked the user to specify which product ID they wanted.

6. Monetization & Fulfillment: The Affiliate / Direct Checkout Model:
Overview & Architecture:
- The agent handles curation, comparison, and scam filtering in-chat.
- Fulfillment, payments, and logistics are delegated directly to the merchants (Jumia, Amazon) via tagged affiliate deep links.
- For peer-to-peer marketplaces (Jiji), the agent generates pre-filled WhatsApp hand-off links directly to sellers.

Why Clients in Ghana Appreciate This Model:
- Brand Safety & Trust: Eliminates scam anxiety—customers pay established retailers (Jumia / Amazon) using their existing accounts, buyer protection, and MoMo / Card methods.
- Zero Added Markup: Users pay the authentic retail price without middleman service fees.
- Official Warranty & Returns: Customers rely on official 7-day return policies and merchant warranties rather than an unproven intermediary.
- Comfort for High-Ticket Items: Buyers in Ghana prefer reviewing the final checkout screen before inputting their MoMo PIN.

Economics & Revenue Streams:
- Jumia KOL / Affiliate Program: Earns 3% to 11% commission across categories (Electronics ~3-4%, Groceries ~7-9%, Fashion ~10-11%).
- Amazon Associates: Earns 1% to 10% on international orders shipped to Ghana.
- Zero Operational Overhead: Pure software margins (~95%+ net) with zero inventory, delivery rider liability, or dispute handling.

Technical Implementation:
- Append affiliate tracking IDs (`aff_id=YOUR_ID` for Jumia, `tag=YOUR_TAG` for Amazon) dynamically in `src/search_service.py` to outgoing URLs.
- For Jiji, extract seller phone numbers and format direct WhatsApp deep links (`https://wa.me/<phone>?text=...`).


