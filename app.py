"""Streamlit interface for live product comparison across Jumia, Jiji, and Amazon."""

import os
from dotenv import load_dotenv
import streamlit as st

load_dotenv()

from src.agent import build_agent, chat

st.set_page_config(
    page_title="E-Commerce Product Search & Comparison",
    layout="centered",
)

SAMPLE_QUESTIONS = [
    "Compare prices for PS5 Slim across Jumia and Jiji",
    "Find a 43-inch 4K Smart TV under GH₵ 4,000",
    "Look for iPhone 13 128GB prices across stores",
    "Search for quality air fryers under GH₵ 1,200",
    "Best-rated noise-cancelling headphones on Amazon",
]

if "messages" not in st.session_state:
    st.session_state.messages = []

if "pending_prompt" not in st.session_state:
    st.session_state.pending_prompt = None


@st.cache_resource
def get_agent():
    return build_agent()


# Sidebar controls
with st.sidebar:
    st.subheader("Controls")
    if st.button("New conversation", use_container_width=True):
        st.session_state.messages = []
        st.session_state.pending_prompt = None
        st.rerun()

    st.divider()
    st.caption("Sample Searches")
    for q in SAMPLE_QUESTIONS:
        if st.button(q, use_container_width=True):
            st.session_state.pending_prompt = q
            st.rerun()

    st.divider()
    st.caption("Active Stores")
    st.markdown("- Jumia Ghana\n- Jiji Ghana\n- Amazon")


# Main layout
st.title("Product Comparison Assistant")
st.caption("Live product search and price comparison across Jumia Ghana, Jiji, and Amazon.")

missing_keys = []
if not os.getenv("GROQ_API_KEY"):
    missing_keys.append("GROQ_API_KEY")
if not os.getenv("SERPER_API_KEY"):
    missing_keys.append("SERPER_API_KEY")

if missing_keys:
    st.error(f"Missing required keys in .env: {', '.join(missing_keys)}. Please define them to enable search.")
    st.stop()

# Render chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Handle user input (manual or selected from sidebar)
user_input = st.chat_input("Search for any product (e.g. PS5 Slim, air fryer, iPhone 13)...")
prompt = user_input or st.session_state.pop("pending_prompt", None)

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Searching live stores & comparing deals..."):
            try:
                reply = chat(get_agent(), st.session_state.messages)
            except Exception as e:
                reply = f"Error processing request: {e}"
        st.markdown(reply)

    st.session_state.messages.append({"role": "assistant", "content": reply})
