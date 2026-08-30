import os

import streamlit as st
from dotenv import load_dotenv

st.set_page_config(page_title="Skylark BI Agent", page_icon="📊", layout="centered")

load_dotenv()

for secret_name in ("OPENAI_API_KEY", "MONDAY_API_TOKEN"):
    if not os.getenv(secret_name) and secret_name in st.secrets:
        os.environ[secret_name] = str(st.secrets[secret_name])

missing_secrets = [
    secret_name
    for secret_name in ("OPENAI_API_KEY", "MONDAY_API_TOKEN")
    if not os.getenv(secret_name)
]

if missing_secrets:
    st.error(
        "Missing required deployment secrets: "
        + ", ".join(missing_secrets)
        + ". Add them in Streamlit Cloud under Manage app > Settings > Secrets, then reboot the app."
    )
    st.stop()

from agent import chat

st.markdown(
    """
    <style>
    [data-testid="stToolbar"] {
        display: none;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("📊 Skylark Drones — BI Agent")
st.caption("Ask founder-level questions about deals and work orders. Data is fetched live from monday.com.")

if "history" not in st.session_state:
    st.session_state.history = None

if "display_messages" not in st.session_state:
    st.session_state.display_messages = []

for msg in st.session_state.display_messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

user_input = st.chat_input("Ask about pipeline, deals, work orders...")

if user_input:
    st.session_state.display_messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        with st.spinner("Checking monday.com..."):
            answer, st.session_state.history = chat(user_input, st.session_state.history)
        st.markdown(answer)

    st.session_state.display_messages.append({"role": "assistant", "content": answer})
