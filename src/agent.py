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
- Present the live listings in a clean markdown table:
  | Store | Product Name | Price (GH₵ / USD) | Notes / Condition | Direct Link |
- In the 'Direct Link' column, ALWAYS provide the clickable markdown link using the URL from the tool: `[View on Store](url)`. NEVER write 'N/A'.
- In the 'Price' column, display the price found by the tool (e.g. GH₵ 7,999, GH₵ 9,499).
- After the table, provide an actionable recommendation:
  * Compare the lowest price vs highest price.
  * Sanity check electronics prices: If a price for a major console or phone looks unrealistically low (e.g. GH₵ 800 for a PS5), clarify that it may be a controller, accessory, or installment rather than the full unit.
  * Contrast Jumia (brand new, official warranty, direct delivery) vs Jiji (individual/peer-to-peer deals, requires verifying condition before payment).
  * Give a clear buying verdict for the user.
- Keep responses concise, practical, and grounded strictly in the tool results."""


def build_agent():
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    llm = ChatGroq(model=MODEL_NAME, temperature=0, api_key=api_key)
    return create_agent(llm, tools=TOOLS, system_prompt=SYSTEM_PROMPT)


def chat(agent, messages: list[dict]) -> str:
    """Run the agent on recent messages to stay strictly within Groq TPM limits."""
    recent = messages[-2:] if len(messages) > 2 else messages
    result = agent.invoke({"messages": recent})
    return result["messages"][-1].content
