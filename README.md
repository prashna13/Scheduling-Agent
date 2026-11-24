# Saathi Sneha Care — Scheduling Sub-Agent (v0.6.0)

LangChain-based Scheduling Sub-Agent and Streamlit Web Application for **Saathi Sneha Care** (Mumbai home healthcare visits).  
Built across Weeks 1–8, this standalone sub-agent delivers an end-to-end **Human-in-the-Loop (HITL) Booking Workflow**: natural-language availability queries, 2–3 smart slot proposals, multi-turn patient intake, persistent draft staging, a password-protected Coordinator Review Portal, clinical emergency escalation, and thread-safe Excel persistence verified by **24/24 automated pytest tests**.

> **Multi-Agent Integration Status (Week 5):** Standalone scheduling sub-agent ready for plug-and-play orchestration. Clean stateless entrypoints (`ask_agent(query, chat_history, session_id)` and `CORE_TOOLS`) are exported from `agent.py` to connect with the other two agents once the shared orchestrator is wired up.

---

## Core Capabilities

1. **Human-in-the-Loop `write_booking` Engine & Excel Persistence:**  
   The LLM never writes directly to Excel (`write_booking_tool` is excluded from `AGENT_READ_ONLY_TOOLS`). When an authorized coordinator approves a staged draft, `write_booking` acquires a `threading.RLock`, re-verifies slot availability (TOCTOU double-booking guard), generates the next sequential `Booking ID` (e.g., `BK-113`), appends the 11-column row to `Bookings Calendar` in `data/Saathi_Sneha_Care_Scheduling_Calendar_Mockup.xlsx` (preserving date formatting), clears the sheet cache, and auto-cancels any overlapping staged drafts.
2. **Multi-Turn Patient Intake & Persistent Draft Staging:**  
   Before staging a booking draft (`DRAFT-01`), the agent collects all required Excel fields (**Patient Full Name**, **Contact Number**, **Address / Area**, **Service Type**, and optional **Special Notes**). Supports single-turn or multi-turn replies, 10-digit mobile number normalization (`+91 XXXXXXXXXX`), mid-intake cancellation, per-session isolation, and JSON disk persistence (`data/staged_drafts.json`).
3. **Password-Protected Coordinator Review Portal:**  
   The Streamlit app (`app.py`) separates **Patient Chat** (Tab 1) and **Coordinator Login / Review** (Tab 2). Authenticated coordinators (`COORDINATOR_PASSWORD`, default `saathi123`) can inspect/edit drafts, approve bookings to Excel, dismiss drafts, edit `Bookings Calendar`, view read-only `Staff Availability`, and download/re-upload `.xlsx` snapshots.
4. **Intelligent 2–3 Slot Proposal Engine & Smart Alternatives:**  
   Evaluates shifts and active bookings (including single-time entries like `11am` treated as 1-hour blocks) to propose 2–3 conflict-free 1-hour slots. Filters by role, specialty (e.g., Geriatric, Palliative), and Mumbai locality. When a clinician is Off, booked, or unregistered (e.g., *Dr. John Doe*), the agent explains why and suggests available on-duty staff.
5. **3-Tier Hybrid Grounding Pipeline:**  
   Runs deterministic Excel grounding first so availability facts, intake states, and safety responses can never be hallucinated, then uses **OpenRouter (`openai/gpt-oss-120b`) → Google Gemini (`gemini-2.5-flash`) → 100% offline deterministic fallback** for warm WhatsApp-style phrasing.
6. **Clinical Emergency Bypass:**  
   Detects acute symptom cues (e.g., chest pain, stroke, breathing difficulty) and immediately bypasses scheduling to instruct calling **108 / 112**.

---

## The 4 Core Tool Interfaces

| Tool | Signature | Access | Description |
| :--- | :--- | :--- | :--- |
| `read_availability` | `(date_range: str, role: str) -> List[Dict]` | Read-only (LLM) | Returns all staff of a given role scheduled to work on the target date (excluding `"Off"` days). |
| `check_conflict` | `(staff_id: str, slot: str, date: str) -> bool` | Read-only (LLM) | Returns `True` if the slot overlaps an active booking, falls outside shift hours, is on an off-day, or is in the past. |
| `propose_slot` | `(role, specialty, date, area, slot=None) -> List[Dict]` | Read-only (LLM) | Evaluates working shifts and active bookings via `get_available_windows()` to propose 2–3 conflict-free 1-hour slots. |
| `write_booking` | `(booking_data: dict, approved_by: str) -> Dict` | Write Gate (HITL) | Human-only. Verifies coordinator ID, acquires `RLock`, re-checks conflicts, appends `BK-xxx` to Excel, clears cache, and auto-cancels overlapping drafts. |

---

## Example Interaction (End-to-End HITL Booking Flow)

### Step 1: Patient Requests a Slot (Patient Intake Gate)
* **User Query:** *"Can I book Dr. Priya Nair tomorrow from 2:00 PM to 3:00 PM?"*
* **Agent Response:** Confirms Dr. Priya Nair's availability and prompts for missing intake fields: **Patient Full Name**, **Contact Number**, **Address / Area in Mumbai**, **Service Type / Reason for Visit**, and optional **Special Notes**.

### Step 2: Patient Provides Details (Draft Staged for Coordinator)
* **User Reply:** *"Rahul Sharma, 9876543210, Ghatkopar, Geriatric consult"*
* **Agent Response:** Stages `DRAFT-01` (`Status: Pending Approval`) in `data/staged_drafts.json` without modifying Excel.

### Step 3: Coordinator Login & Approval
* The coordinator opens the **Coordinator Login** tab, signs in with their Coordinator ID (e.g., `Coordinator_Prashna`) and password, reviews/edits `DRAFT-01`, and clicks **Approve & Write to Calendar**.
* `write_booking` commits row `BK-xxx` to `Bookings Calendar` with `Status = Confirmed`, immediately blocking that slot for subsequent conflict checks.

---

## Project Structure

```text
├── app.py                                                  # Streamlit Two-Tab UI (Patient Chat & Coordinator Portal)
├── calendar_engine.py                                      # Core Excel engine, mtime cache, staging queue & 4 core tools
├── langchain_agent.py                                      # Conversational agent, intake parser, emergency bypass & LLM router
├── agent.py                                                # Stateless integration entrypoint (ask_agent & CORE_TOOLS)
├── main.py                                                 # Interactive CLI tester
├── test_engine.py                                          # Pytest suite (24 automated tests with tmp_path isolation)
├── requirements.txt                                        # Python dependencies
├── README.md                                               # Project documentation
├── .gitignore                                              # Repository exclusions
├── WK-4 Test Cases.xlsx                                    # Week 4 structured test cases (11 scenarios)
└── data/
    └── Saathi_Sneha_Care_Scheduling_Calendar_Mockup.xlsx   # Single-source-of-truth Excel calendar database
```

---

## Setup & Installation

1. **Create and activate a virtual environment:**

   ```bash
   # Windows
   python -m venv .venv
   .venv\Scripts\activate

   # macOS / Linux
   python3 -m venv .venv
   source .venv/bin/activate
   ```

2. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

3. **Optional Environment Variables (`.env`):**
   * `OPENROUTER_API_KEY` / `GOOGLE_API_KEY`: Optional LLM API keys (automatically falls back to the deterministic 4-tool engine if omitted or unavailable).
   * `COORDINATOR_PASSWORD`: Password for the Coordinator Review tab in `app.py` (defaults to `saathi123`).

---

## How to Run & Verify

### 1. Launch the Streamlit Web Application
```bash
streamlit run app.py
```

### 2. Interactive CLI Tester
```bash
python main.py
```

### 3. Run Automated Tests
Execute the full **24-test** isolated verification suite with `pytest` (never modifies production Excel or `staged_drafts.json`):

```bash
pytest test_engine.py -v
```

---

## Safety & Guardrails

1. **Zero Unsupervised Writes:** `write_booking_tool` is excluded from the LLM toolset. The agent can only stage drafts (`DRAFT-xx`); writing to Excel strictly requires an allowlisted human coordinator (`approved_by`).
2. **TOCTOU Concurrency & Auto-Cancellation:** `write_booking` acquires `threading.RLock`, re-checks conflicts right before saving, auto-cancels overlapping drafts (even across Staff ID vs. Name variants), and catches `PermissionError` if desktop Excel has the file locked.
3. **Clinical Emergency Bypass & Prompt Isolation:** Acute medical emergencies bypass scheduling and immediately escalate to **108 / 112**. User input passed to LLMs is wrapped in `<client_inquiry>` tags as untrusted data.
4. **Data & Boundary Integrity:** Blocks past dates and elapsed same-day slots, keeps `Staff Availability` strictly read-only, anchors file paths to `BASE_DIR` (CWD-independent), and rejects ambiguous staff lookups instead of silently guessing.
