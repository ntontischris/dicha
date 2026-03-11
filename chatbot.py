# chatbot.py — Streamlit web chatbot for WooCommerce AI Agent
# Run: streamlit run chatbot.py

import streamlit as st
from pathlib import Path

import config
from agent import run_agent

st.set_page_config(page_title="WooCommerce AI Agent", page_icon="🛍️", layout="wide")
st.title("🛍️ WooCommerce AI Agent")


@st.cache_resource
def load_system_prompt() -> str:
    template = (Path(__file__).parent / "prompts" / "system_prompt.md").read_text(encoding="utf-8")
    return template.replace("{project_id}", config.PROJECT_ID)


# ── Session state init ────────────────────────────────────────────────────────

if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "system", "content": load_system_prompt()}]

if "session_usage" not in st.session_state:
    st.session_state.session_usage = {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}

# ── Sidebar: session cost tracker ─────────────────────────────────────────────

with st.sidebar:
    st.header("📊 Session Usage")
    su = st.session_state.session_usage
    col1, col2 = st.columns(2)
    col1.metric("Input tokens",  f"{su['input_tokens']:,}")
    col2.metric("Output tokens", f"{su['output_tokens']:,}")
    st.metric("Total cost", f"${su['cost_usd']:.4f}")

    if st.button("🗑️ Clear conversation"):
        st.session_state.messages = [{"role": "system", "content": load_system_prompt()}]
        st.session_state.session_usage = {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}
        st.rerun()

st.caption(f"Project: **{config.PROJECT_ID}** | Model: `{config.MODEL}`")

# ── Display conversation history (skip system message) ────────────────────────

for msg in st.session_state.messages:
    if msg["role"] in ("user", "assistant"):
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

# ── Chat input ────────────────────────────────────────────────────────────────

if prompt := st.chat_input("Ρώτησε κάτι για το WooCommerce shop..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    usage: dict = {}

    with st.chat_message("assistant"):
        full_response = st.write_stream(run_agent(st.session_state.messages, usage))

    st.session_state.messages.append({"role": "assistant", "content": full_response})

    # Update session totals
    su = st.session_state.session_usage
    su["input_tokens"]  += usage.get("input_tokens", 0)
    su["output_tokens"] += usage.get("output_tokens", 0)
    su["cost_usd"]      += usage.get("cost_usd", 0.0)

    # Per-turn cost caption
    in_tok  = usage.get("input_tokens", 0)
    out_tok = usage.get("output_tokens", 0)
    cost    = usage.get("cost_usd", 0.0)
    st.caption(f"↳ {in_tok:,} in / {out_tok:,} out — ${cost:.4f}")

    st.rerun()
