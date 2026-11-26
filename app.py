"""Streamlit interface for live product comparison across Jumia, Jiji, and Amazon."""

import os
import re
from dotenv import load_dotenv
import streamlit as st

load_dotenv()

from src.agent import build_agent, chat

st.set_page_config(
    page_title="E-Commerce Product Search & Comparison",
    layout="centered",
)

# Remove Streamlit default Deploy button and toolbar actions
st.markdown(
    """
    <style>
    [data-testid="stDeployButton"],
    .stDeployButton,
    [data-testid="stToolbarActions"] {
        display: none !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
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


def extract_numeric_price(price_str: str) -> float:
    """Extract float price for sorting from formatted string."""
    if not price_str or "contact" in str(price_str).lower() or "check" in str(price_str).lower():
        return float("inf")
    cleaned = re.sub(r"(?i)GH[₵S]|GHS|\$", "", str(price_str)).strip()
    match = re.search(r"[\d][\d\s,\.]*", cleaned)
    if not match:
        return float("inf")
    try:
        return float(match.group(0).replace(" ", "").replace(",", ""))
    except ValueError:
        return float("inf")


def filter_and_sort_listings(
    listings: list,
    stores: list,
    condition: str,
    sort_order: str,
) -> list:
    """Filter and sort product listings according to user selections."""
    if not listings:
        return []

    filtered = []
    for item in listings:
        # Filter by store
        if item.get("store") not in stores:
            continue

        # Filter by condition
        item_cond = item.get("condition", "").lower()
        if condition == "Brand New Only" and "new" not in item_cond:
            continue
        if condition == "Second-hand Deals" and "new" in item_cond:
            continue

        filtered.append(item)

    # Sort listings
    if sort_order != "Store Default" and filtered:
        reverse = (sort_order == "Price: High to Low")
        filtered = sorted(filtered, key=lambda x: extract_numeric_price(x.get("price")), reverse=reverse)

    return filtered


def render_product_card(item: dict):
    """Render a clean, high-utility product card with zero AI design artifacts."""
    with st.container(border=True):
        col_thumb, col_body = st.columns([1, 3])

        with col_thumb:
            image_url = item.get("image")
            if image_url:
                st.image(image_url, use_container_width=True)
            else:
                st.markdown(
                    '<div style="height: 100px; background-color: #f3f4f6; border: 1px solid #e5e7eb; '
                    'border-radius: 4px; display: flex; align-items: center; justify-content: center; '
                    'color: #9ca3af; font-size: 11px; text-align: center;">No image available</div>',
                    unsafe_allow_html=True,
                )

        with col_body:
            store = item.get("store", "Store")
            condition = item.get("condition", "Available")
            if "new" in condition.lower():
                cond_style = "color: #065f46; background-color: #ecfdf5; border: 1px solid #a7f3d0;"
            else:
                cond_style = "color: #92400e; background-color: #fef3c7; border: 1px solid #fde68a;"

            st.markdown(
                f'<div style="margin-bottom: 4px;">'
                f'<span style="font-size: 11px; font-weight: 600; text-transform: uppercase; color: #374151; '
                f'background-color: #f3f4f6; padding: 2px 6px; border: 1px solid #e5e7eb; border-radius: 3px; '
                f'margin-right: 6px;">{store}</span>'
                f'<span style="font-size: 11px; font-weight: 500; padding: 2px 6px; border-radius: 3px; '
                f'{cond_style}">{condition}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

            st.markdown(f"**{item.get('title', 'Product')}**")

            price = item.get("price", "Check price")
            st.markdown(
                f'<div style="font-size: 1.15rem; font-weight: 700; color: #111827; margin: 2px 0 4px 0;">{price}</div>',
                unsafe_allow_html=True,
            )

            location = item.get("location", "Ghana")
            notes = item.get("notes", "")
            st.caption(f"Location: {location} • {notes}")

            if item.get("is_anomaly") and item.get("anomaly_warning"):
                st.markdown(
                    f'<div style="margin: 6px 0 10px 0; padding: 6px 10px; background-color: #fffbeb; '
                    f'border: 1px solid #fde68a; border-radius: 4px; font-size: 11px; color: #92400e; line-height: 1.4;">'
                    f'<strong>PRICE ALERT:</strong> {item["anomaly_warning"]}'
                    f'</div>',
                    unsafe_allow_html=True,
                )

            link = item.get("link")
            if link and str(link).startswith("http"):
                st.link_button("View on Store", url=link, use_container_width=False)


# Sidebar controls
with st.sidebar:
    st.subheader("Controls")
    if st.button("New conversation", use_container_width=True):
        st.session_state.messages = []
        st.session_state.pending_prompt = None
        st.rerun()

    st.divider()
    st.subheader("Filter Listings")
    filter_stores = st.multiselect(
        "Stores",
        options=["Jumia Ghana", "Jiji Ghana", "Amazon"],
        default=["Jumia Ghana", "Jiji Ghana", "Amazon"],
    )
    filter_condition = st.radio(
        "Condition",
        options=["All Conditions", "Brand New Only", "Second-hand Deals"],
        index=0,
    )
    filter_sort = st.selectbox(
        "Sort by price",
        options=["Store Default", "Price: Low to High", "Price: High to Low"],
        index=0,
    )

    st.divider()
    st.caption("Sample Searches")
    for q in SAMPLE_QUESTIONS:
        if st.button(q, use_container_width=True):
            st.session_state.pending_prompt = q
            st.rerun()


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
        if message["role"] == "assistant" and message.get("listings"):
            filtered_items = filter_and_sort_listings(
                message["listings"],
                stores=filter_stores,
                condition=filter_condition,
                sort_order=filter_sort,
            )
            if filtered_items:
                st.caption(f"Displaying {len(filtered_items)} live product listings:")
                for item in filtered_items:
                    render_product_card(item)
            else:
                st.info("No listings match the selected sidebar filters.")

        if message.get("content"):
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
                res = chat(get_agent(), st.session_state.messages)
                reply_content = res.get("content", "")
                listings_data = res.get("listings", [])
            except Exception as e:
                reply_content = f"Error processing request: {e}"
                listings_data = []

        if listings_data:
            filtered_items = filter_and_sort_listings(
                listings_data,
                stores=filter_stores,
                condition=filter_condition,
                sort_order=filter_sort,
            )
            if filtered_items:
                st.caption(f"Displaying {len(filtered_items)} live product listings:")
                for item in filtered_items:
                    render_product_card(item)
            else:
                st.info("No listings match the selected sidebar filters.")

        if reply_content:
            st.markdown(reply_content)

    st.session_state.messages.append({
        "role": "assistant",
        "content": reply_content,
        "listings": listings_data,
    })
