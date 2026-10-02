"""
Saathi Sneha Care — Customer Conversational Scheduling Assistant
A unified, clean conversational interface mimicking real customer messaging apps (WhatsApp / Web Chat).
Single source of truth: Excel calendar database.
"""

import os
import streamlit as st
from langchain_agent import ask_agent

# Page Configuration - Clean single-screen interface
st.set_page_config(
    page_title="Saathi Sneha Care — Assistant",
    page_icon="",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Custom Styling for Customer Messaging Experience
st.markdown("""
<style>
    /* Hide sidebar and collapse controls completely */
    [data-testid="stSidebar"] {
        display: none !important;
    }
    [data-testid="collapsedControl"] {
        display: none !important;
    }
    
    /* Container styling */
    .block-container {
        max-width: 800px;
        padding-top: 1.5rem;
        padding-bottom: 3rem;
        padding-left: 1rem;
        padding-right: 1rem;
    }
    
    /* WhatsApp/Messenger style header */
    .messenger-header {
        background: linear-gradient(135deg, #0F766E 0%, #0D9488 100%);
        color: white;
        padding: 1rem 1.4rem;
        border-radius: 12px;
        margin-bottom: 1.2rem;
        display: flex;
        align-items: center;
        justify-content: space-between;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.08);
    }
    .messenger-title {
        font-size: 1.25rem;
        font-weight: 700;
        margin: 0;
        color: white;
    }
    .messenger-status {
        font-size: 0.82rem;
        color: #CCFBF1;
        margin-top: 2px;
    }
    .online-indicator {
        display: inline-block;
        width: 8px;
        height: 8px;
        background-color: #34D399;
        border-radius: 50%;
        margin-right: 4px;
    }
    
    /* Quick prompt button chips */
    .stButton > button {
        border-radius: 18px;
        font-size: 0.85rem;
        padding: 4px 12px;
        border: 1px solid #99F6E4;
        background-color: #F0FDFA;
        color: #0F766E;
        transition: all 0.2s;
    }
    .stButton > button:hover {
        background-color: #CCFBF1;
        border-color: #0D9488;
        color: #115E59;
    }
</style>
""", unsafe_allow_html=True)

# Customer Device Header
st.markdown("""
<div class="messenger-header">
    <div>
        <div class="messenger-title">Saathi Sneha Care</div>
        <div class="messenger-status"><span class="online-indicator"></span>Online | Home Healthcare Intake & Scheduling</div>
    </div>
    <div style="font-size: 0.8rem; color: #E6FFFA; text-align: right;">
        Mumbai, IN<br>
        <span style="opacity: 0.85;">Excel Verified</span>
    </div>
</div>
""", unsafe_allow_html=True)

# Initialize Chat History
if "messages" not in st.session_state:
    st.session_state["messages"] = [
        {
            "role": "assistant",
            "content": "Hello!  Welcome to **Saathi Sneha Care**.\n\nI can help you check doctor & nurse availability for home visits , propose convenient appointment slots, and recommend alternatives if someone is unavailable.\n\nHow can I help you today?"
        }
    ]

# Interactive Quick Prompt Chips
st.caption("💡 Frequently Asked by Patients (Click to ask):")
q_col1, q_col2 = st.columns(2)
with q_col1:
    btn1 = st.button("Is Dr. Iyer free on 2026-09-28?", use_container_width=True)
    btn2 = st.button("Is Nurse Sunita Rao free on 2026-09-24?", use_container_width=True)
with q_col2:
    btn3 = st.button("Is Dr. Priya Nair free on 2026-09-23?", use_container_width=True)
    btn4 = st.button("Is any nurse free on 2026-09-21?", use_container_width=True)

selected_prompt = None
if btn1:
    selected_prompt = "Is Dr. Iyer free on 2026-09-28?"
elif btn2:
    selected_prompt = "Is Nurse Sunita Rao free on 2026-09-24?"
elif btn3:
    selected_prompt = "Is Dr. Priya Nair free on 2026-09-23?"
elif btn4:
    selected_prompt = "Is any nurse free on 2026-09-21?"

st.markdown("---")

# Render Conversation Message Thread
for msg in st.session_state["messages"]:
    avatar = "🏥" if msg["role"] == "assistant" else "👤"
    with st.chat_message(msg["role"], avatar=avatar):
        st.markdown(msg["content"])

# Customer Input Field
user_input = st.chat_input("Type your question about doctor/nurse availability or home visits...") or selected_prompt

if user_input:
    # Append & display user query
    st.session_state["messages"].append({"role": "user", "content": user_input})
    with st.chat_message("user", avatar="👤"):
        st.markdown(user_input)

    # Agent checks the Excel database single source of truth & generates natural response
    with st.chat_message("assistant", avatar="🏥"):
        with st.spinner("Checking schedule & availability..."):
            reply = ask_agent(user_query=user_input)
            st.markdown(reply)
            st.session_state["messages"].append({"role": "assistant", "content": reply})

# Subtle footer controls
st.markdown("<div style='margin-top: 2rem;'></div>", unsafe_allow_html=True)
foot_col1, foot_col2 = st.columns([4, 1])
with foot_col2:
    if st.button(" Clear Chat", use_container_width=True):
        st.session_state["messages"] = []
        st.rerun()
