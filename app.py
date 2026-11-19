"""Streamlit interface for product search and order placement in Ghana."""

import os
import streamlit as st

from src.agent import build_agent, chat

st.set_page_config(
    page_title="Product Search and Ordering",
    layout="centered",
)

SAMPLE_QUESTIONS = [
    "Find organic olive oils under GH₵ 200 with a rating of at least 4.5",
    "What are the highest-rated coffees in the catalog?",
    "Show snacks priced under GH₵ 100",
    "List available grains sorted by price",
    "Place an order for product ID 1",
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
    st.caption("Sample Queries")
    for q in SAMPLE_QUESTIONS:
        if st.button(q, use_container_width=True):
            st.session_state.pending_prompt = q
            st.rerun()


# Main layout
st.title("Product Assistant")
st.caption("Search inventory in Ghanaian Cedi (GH₵), compare ratings, and place orders.")

if not os.getenv("GROQ_API_KEY"):
    st.error("GROQ_API_KEY is not set. Please define it in your .env file.")
    st.stop()

# Render chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Handle user input (manual or selected from sidebar)
user_input = st.chat_input("Enter a product query (e.g. snacks under GH₵ 100) or order request...")
prompt = user_input or st.session_state.pop("pending_prompt", None)

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Processing request..."):
            try:
                reply = chat(get_agent(), st.session_state.messages)
            except Exception as e:
                reply = f"Error processing request: {e}"
        st.markdown(reply)

    st.session_state.messages.append({"role": "assistant", "content": reply})
