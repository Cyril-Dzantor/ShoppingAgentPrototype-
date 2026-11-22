"""Shopping agent built with LangChain and GroqCloud for live e-commerce search in Ghana."""

import os
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_groq import ChatGroq

from src.tools import TOOLS

load_dotenv()

MODEL_NAME = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

SYSTEM_PROMPT = """You are an expert shopping assistant for consumers in Ghana, comparing live products across Jumia Ghana, Jiji Ghana, and Amazon.

- When asked about a product or price comparison, call `search_live_products` ONCE with the product name.
- The UI automatically renders interactive product cards with photos, prices, conditions, locations, and direct store links.
- In your response, provide an actionable buying recommendation and comparative analysis:
  * Highlight the lowest price and best value.
  * Contrast Jumia (brand new, official warranty, direct delivery) vs Jiji (peer-to-peer deals, requires inspecting condition in person before payment).
  * Sanity check prices: If a price for a major console or phone looks unrealistically low (e.g. GH₵ 800 for a PS5), clarify that it may be an accessory, repair part, or installment rather than the full unit.
  * Give a clear, straightforward buying verdict for the user.
- Keep your analysis concise, practical, and grounded strictly in the tool results. Do not use emoji icons."""


def build_agent():
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    llm = ChatGroq(model=MODEL_NAME, temperature=0, api_key=api_key)
    return create_agent(llm, tools=TOOLS, system_prompt=SYSTEM_PROMPT)


def chat(agent, messages: list[dict]) -> dict:
    """Run the agent on recent messages and return both the textual response and structured listings."""
    # Ensure messages passed to LangChain contain only role and content strings
    recent = []
    for m in (messages[-2:] if len(messages) > 2 else messages):
        recent.append({"role": m["role"], "content": m["content"]})

    result = agent.invoke({"messages": recent})
    reply_content = result["messages"][-1].content

    # Extract structured listings from ToolMessage if search_live_products was executed
    listings = []
    for m in result["messages"]:
        if type(m).__name__ == "ToolMessage" and getattr(m, "name", None) == "search_live_products":
            try:
                import json
                raw = json.loads(m.content) if isinstance(m.content, str) else m.content
                if isinstance(raw, list):
                    listings = raw
            except Exception:
                pass

    return {
        "content": reply_content,
        "listings": listings,
    }
