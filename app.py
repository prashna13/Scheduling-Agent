"""
Saathi Sneha Care — Customer Conversational Scheduling Assistant & Coordinator Gate
A unified two-tab interface:
1. 💬 Patient Chat: WhatsApp/Web-style conversational assistant for checking availability & staging booking drafts.
2. 🛡️ Coordinator Review: Human-in-the-Loop safety gate to review staged drafts and commit approved bookings to Excel via `write_booking`.
Single source of truth: Excel calendar database.
"""

import os
import streamlit as st
from langchain_agent import ask_agent
from calendar_engine import (
    get_staged_drafts,
    dismiss_staged_draft,
    write_booking,
    load_sheet
)

# Page Configuration - Clean single-screen interface
st.set_page_config(
    page_title="Saathi Sneha Care — Assistant",
    page_icon="🏥",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Custom Styling for Customer Messaging Experience & Coordinator Tab
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
        max-width: 820px;
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
        margin-bottom: 1rem;
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
            "content": (
                "Hello! 👋 Welcome to **Saathi Sneha Care**.\n\n"
                "I can help you check doctor & nurse availability for home visits, propose convenient appointment slots, "
                "and prepare an appointment draft for our care coordinator to confirm.\n\n"
                "How can I help you today?"
            )
        }
    ]

# Fetch currently staged drafts for the Coordinator Review tab badge
staged_drafts = get_staged_drafts()
draft_count = len(staged_drafts)

# ---------------------------------------------------------------------------
# 🗂️ SEPARATE TABS: 💬 Patient Chat  |  🔐 Coordinator Login & Review
# ---------------------------------------------------------------------------
is_coord_logged_in = st.session_state.get("coord_authenticated", False)
coord_tab_label = (
    f"🛡️ Coordinator Review ({draft_count})"
    if is_coord_logged_in
    else f"🔐 Coordinator Login ({draft_count})"
)
tab_chat, tab_coord = st.tabs([
    "💬 Patient Chat",
    coord_tab_label
])

# ===========================================================================
# TAB 1: 💬 PATIENT CHAT
# ===========================================================================
with tab_chat:
    st.caption("💡 Frequently Asked by Patients (Click to ask):")
    q_col1, q_col2 = st.columns(2)
    with q_col1:
        btn1 = st.button("Is Dr. Iyer free on 2026-09-28?", use_container_width=True)
        btn2 = st.button("Is Nurse Sunita Rao free on 2026-09-24?", use_container_width=True)
    with q_col2:
        btn3 = st.button("Can I book Dr. Priya Nair on 13-Oct-2026 from 2:00 PM to 3:00 PM?", use_container_width=True)
        btn4 = st.button("Is any nurse free on 2026-09-21?", use_container_width=True)

    selected_prompt = None
    if btn1:
        selected_prompt = "Is Dr. Iyer free on 2026-09-28?"
    elif btn2:
        selected_prompt = "Is Nurse Sunita Rao free on 2026-09-24?"
    elif btn3:
        selected_prompt = "Can I book Dr. Priya Nair on 13-Oct-2026 from 2:00 PM to 3:00 PM?"
    elif btn4:
        selected_prompt = "Is any nurse free on 2026-09-21?"

    if draft_count > 0:
        st.info(
            f"📋 **{draft_count} appointment draft(s)** staged and awaiting confirmation. "
            f"Switch to the **🛡️ Coordinator Review ({draft_count})** tab above to approve and write to the calendar."
        )

    st.markdown("---")

    # Render Conversation Message Thread
    for msg in st.session_state["messages"]:
        avatar = "🏥" if msg["role"] == "assistant" else "👤"
        with st.chat_message(msg["role"], avatar=avatar):
            st.markdown(msg["content"])

    # Footer controls inside chat tab
    st.markdown("<div style='margin-top: 1rem;'></div>", unsafe_allow_html=True)
    foot_col1, foot_col2 = st.columns([4, 1])
    with foot_col2:
        if st.button("🗑️ Clear Chat", use_container_width=True):
            st.session_state["messages"] = []
            st.rerun()

# ===========================================================================
# TAB 2: 🔐 COORDINATOR LOGIN & REVIEW (Password-Protected HITL Gate)
# ===========================================================================
with tab_coord:
    expected_pw = os.getenv("COORDINATOR_PASSWORD") or os.getenv("COORDINATOR_PIN") or "saathi123"

    if not st.session_state.get("coord_authenticated", False):
        st.markdown("### 🔐 Coordinator Portal Login")
        st.markdown("Authorized care coordinators only. Enter your credentials to review and approve staged bookings.")
        with st.container(border=True):
            login_id = st.text_input(
                "Coordinator ID / Name",
                value=st.session_state.get("coord_name", "Coordinator_Prashna"),
                key="login_coord_id"
            )
            login_pw = st.text_input(
                "Coordinator Password",
                type="password",
                placeholder="Enter password (default: saathi123)",
                key="login_coord_pw"
            )
            if st.button("🔐 Login to Coordinator Portal", use_container_width=True):
                if login_id.strip() and login_pw == expected_pw:
                    st.session_state["coord_authenticated"] = True
                    st.session_state["coord_name"] = login_id.strip()
                    st.rerun()
                else:
                    st.error("❌ Invalid Coordinator ID or Password.")
    else:
        coord_name = st.session_state.get("coord_name", "Coordinator_Prashna")
        hdr_col1, hdr_col2, hdr_col3 = st.columns([3, 1, 1])
        with hdr_col1:
            st.markdown("### 🛡️ Coordinator Review & Approval Gate")
            st.caption(f"Logged in as: **`{coord_name}`** | Zero Unsupervised Writes active")
        with hdr_col2:
            if st.button("🔄 Refresh", use_container_width=True):
                st.rerun()
        with hdr_col3:
            if st.button("🚪 Logout", use_container_width=True):
                st.session_state["coord_authenticated"] = False
                st.rerun()

        # Show confirmation banner if a booking was just committed
        if st.session_state.get("last_confirmed_booking"):
            last_bk = st.session_state["last_confirmed_booking"]
            st.success(
                f"✅ **Confirmed & Written to Excel!** Booking ID **`{last_bk['booking_id']}`** for "
                f"**{last_bk['booking']['patient_name']}** with **{last_bk['booking']['assigned_staff']}** "
                f"on **{last_bk['booking']['date']} ({last_bk['booking']['time_slot']})** — "
                f"Approved by `{last_bk['approved_by']}`."
            )

        st.markdown("#### 📋 Staged Booking Drafts")
        if not staged_drafts:
            st.info("No staged booking drafts awaiting review. Ask the assistant in the **💬 Patient Chat** tab to book a slot!")
        else:
            for draft in staged_drafts:
                d_id = draft["draft_id"]
                with st.container(border=True):
                    st.markdown(f"##### ⏳ Draft `{d_id}` — **{draft['assigned_staff']}** ({draft['staff_role']})")
                    
                    col_a, col_b = st.columns(2)
                    with col_a:
                        p_name_val = st.text_input(
                            "Patient Name",
                            value=draft["patient_name"],
                            key=f"pname_{d_id}"
                        )
                        contact_val = st.text_input(
                            "Contact Number",
                            value=draft["contact_number"],
                            key=f"contact_{d_id}"
                        )
                        area_val = st.text_input(
                            "Address / Area",
                            value=draft["address_area"],
                            key=f"area_{d_id}"
                        )
                    with col_b:
                        st.markdown(f"**📅 Date:** `{draft['date']}`")
                        st.markdown(f"**⏰ Time Slot:** `{draft['time_slot']}`")
                        st.markdown(f"**🩺 Clinician:** {draft['assigned_staff']} ({draft['staff_role']})")
                        service_val = st.text_input(
                            "Service Type",
                            value=draft["service_type"],
                            key=f"srv_{d_id}"
                        )

                    act_col1, act_col2 = st.columns(2)
                    with act_col1:
                        if st.button(
                            "✅ Approve & Write to Calendar",
                            key=f"approve_{d_id}",
                            use_container_width=True
                        ):
                            try:
                                updated_draft = dict(draft)
                                updated_draft["patient_name"] = p_name_val
                                updated_draft["contact_number"] = contact_val
                                updated_draft["address_area"] = area_val
                                updated_draft["service_type"] = service_val

                                res = write_booking(
                                    booking_data=updated_draft,
                                    approved_by=coord_name
                                )
                                st.session_state["last_confirmed_booking"] = res
                                st.session_state["messages"].append({
                                    "role": "assistant",
                                    "content": (
                                        f"✅ **Coordinator Confirmation Update:** Your appointment (`{res['booking_id']}`) "
                                        f"with **{res['booking']['assigned_staff']}** on **{res['booking']['date']}** "
                                        f"at **{res['booking']['time_slot']}** has been officially approved by "
                                        f"**{res['approved_by']}** and recorded in our calendar!"
                                    )
                                })
                                st.rerun()
                            except Exception as e:
                                st.error(f"Approval failed: {e}")

                    with act_col2:
                        if st.button(
                            "❌ Dismiss Draft",
                            key=f"dismiss_{d_id}",
                            use_container_width=True
                        ):
                            dismiss_staged_draft(d_id)
                            st.rerun()

        st.markdown("---")
        with st.expander("📊 Live Bookings Calendar (Excel Single Source of Truth)", expanded=True):
            try:
                bookings_df = load_sheet("Bookings Calendar")
                st.dataframe(bookings_df.tail(10), use_container_width=True, hide_index=True)
            except Exception as e:
                st.warning(f"Could not load Bookings Calendar preview: {e}")

# ---------------------------------------------------------------------------
# 💬 GLOBAL CHAT INPUT (Processed at root level so it works seamlessly)
# ---------------------------------------------------------------------------
user_input = st.chat_input("Type your question about doctor/nurse availability or request to book a slot...") or selected_prompt

if user_input:
    st.session_state["messages"].append({"role": "user", "content": user_input})
    reply = ask_agent(
        user_query=user_input,
        chat_history=st.session_state["messages"]
    )
    st.session_state["messages"].append({"role": "assistant", "content": reply})
    st.rerun()
