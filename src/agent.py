"""Shopping agent built with LangChain and GroqCloud for live e-commerce search."""

import os
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_groq import ChatGroq

from src.tools import TOOLS

load_dotenv()

MODEL_NAME = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

SYSTEM_PROMPT = """You are a shopping assistant for consumers in Ghana, comparing live products across Jumia Ghana, Jiji Ghana, and Amazon.

- When comparing products, call `search_live_products` ONCE with the product name. It checks Jumia, Jiji, and Amazon together in that single call. Do not make multiple tool calls.
- Present product comparisons as a concise markdown table with columns:
  | Store | Product Name | Price / Estimate | Notes | Direct Link |
- When presenting links, format them as clean markdown links: `[View on Store](url)`.
- If a price is available in the results, show it. If unlisted, mention 'Check listing'.
- Highlight key store trade-offs:
  * Jumia Ghana: Brand new, local retail (GH₵).
  * Jiji Ghana: Local peer-to-peer / classifieds, verify seller (GH₵).
  * Amazon: International selection, shipping/import duties apply to Ghana.
- Keep answers concise and direct. Never invent links; only use URLs returned by the tool."""


def build_agent():
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    llm = ChatGroq(model=MODEL_NAME, temperature=0, api_key=api_key)
    return create_agent(llm, tools=TOOLS, system_prompt=SYSTEM_PROMPT)


def chat(agent, messages: list[dict]) -> str:
    """Run the agent on recent messages to stay strictly within Groq TPM limits."""
    # Keep only the last 2 messages (user prompt + immediate context) to strictly avoid TPM bloat
    recent = messages[-2:] if len(messages) > 2 else messages
    result = agent.invoke({"messages": recent})
    return result["messages"][-1].content
