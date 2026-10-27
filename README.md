# Saathi Sneha Care - Scheduling Sub-Agent (Week 6)

LangChain-based Scheduling Sub-Agent and Streamlit Web Application for Saathi Sneha Care.  
This milestone delivers the complete **Week 6 Human-in-the-Loop (HITL) Booking Workflow**: multi-turn patient intake, persistent draft staging, a password-protected Coordinator Review Portal, and thread-safe Excel calendar persistence with automatic cache invalidation.

---

## Core Capabilities (Week 6 Milestone)

1. **Human-in-the-Loop `write_booking` Engine & Excel Persistence:**  
   When an authorized coordinator approves a staged draft, `write_booking` re-verifies slot availability (TOCTOU double-booking guard), generates the next sequential `Booking ID` (e.g., `BK-113`), appends the 11-column row to the `Bookings Calendar` sheet in `data/Saathi_Sneha_Care_Scheduling_Calendar_Mockup.xlsx`, invalidates the in-memory sheet cache, and dismisses any overlapping staged drafts.
2. **Multi-Turn Patient Intake & Persistent Draft Staging:**  
   Before staging a booking draft (`DRAFT-01`), the conversational engine prompts the patient for all required Excel fields (**Patient Full Name**, **Contact Number**, **Address / Area**, **Service Type**, and optional **Special Notes**). Supports single-turn or multi-turn replies, case-insensitive name/area formatting, 10-digit mobile number normalization (`+91 XXXXXXXXXX`), mid-intake cancellation, and JSON disk persistence (`data/staged_drafts.json`).
3. **Password-Protected Coordinator Review Tab:**  
   The Streamlit interface separates **Patient Chat** and **Coordinator Login / Review** into two distinct tabs. The coordinator tab is gated by `COORDINATOR_PASSWORD` (default: `saathi123`) and allows coordinators to inspect/edit draft fields, approve and write bookings to Excel, dismiss drafts, and view the live `Bookings Calendar`.
4. **Intelligent 2-3 Slot Proposal Engine:**  
   Evaluates active shifts and calendar bookings to compute and suggest 2-3 discrete, non-overlapping 1-hour appointment slots (e.g., `2:00 PM - 3:00 PM`, `3:00 PM - 4:00 PM`).
5. **Smart Alternative Recommendations & Non-Existent Staff Handling:**  
   When a requested doctor or nurse is unavailable (marked "Off" or booked) or not registered in the database (e.g., Dr. John Doe), the agent explains why and proposes available on-duty staff with their open 1-hour slots.

---

## The 4 Core Tool Interfaces

| Tool | Signature | Type | Description |
| :--- | :--- | :--- | :--- |
| `read_availability` | `(date_range: str, role: str) -> List[Dict]` | Read-only | Returns all staff of a given role scheduled to work on the target date (excluding "Off" days). |
| `check_conflict` | `(staff_id: str, slot: str, date: str) -> bool` | Read-only | Returns `True` if the requested slot overlaps an active booking or falls outside working hours. |
| `propose_slot` | `(role, specialty, date, area, slot=None) -> List[Dict]` | Read-only | Evaluates working shifts and active bookings to propose 2-3 conflict-free 1-hour time slots. |
| `write_booking` | `(booking_data: dict, approved_by: str) -> Dict` | Write Gate | Validates `approved_by`, re-checks conflicts under a thread lock, generates the next `BK-xxx` ID, appends the confirmed row to Excel, and clears the cache. |

---

## Example Interaction (Week 6 End-to-End Booking Flow)

### Step 1: Patient Requests a Slot (Patient Intake Gate)
* **User Query:** *"Can I book Dr. Priya Nair on Tuesday, 13-Oct-2026, from 2:00 PM to 3:00 PM?"*
* **Agent Response:**  
  *"Great news -- Dr. Priya Nair is available on Tuesday, October 13, 2026 for 2:00 PM - 3:00 PM. To prepare your appointment draft for our care coordinator and fill out the booking sheet, please provide the following missing details:*  
  *1. Patient Full Name*  
  *2. Contact Number*  
  *3. Address / Area in Mumbai*  
  *4. Service Type / Reason for Visit*  
  *5. Special Notes (Optional)"*

### Step 2: Patient Provides Details (Draft Staged for Coordinator)
* **User Reply:** *"Rahul Sharma, 9876543210, Ghatkopar, Geriatric consult"*
* **Agent Response:**  
  *"Thank you! I have prepared your appointment draft! Our care coordinator will review and confirm this booking momentarily. (Draft ID: DRAFT-01, Patient: Rahul Sharma, Contact: +91 9876543210, Area: Ghatkopar, Service: Geriatric consult, Assigned Staff: Dr. Priya Nair, Date: 2026-10-13, Time Slot: 2:00 PM - 3:00 PM, Status: Pending Approval)."*

### Step 3: Coordinator Login & Approval
* The coordinator opens the **Coordinator Login** tab, authenticates with their Coordinator ID (`Coordinator_Prashna`) and password, reviews `DRAFT-01`, and clicks **Approve & Write to Calendar**.
* `write_booking` commits row `BK-113` to Excel with `Status = Confirmed` and `Notes = Staged via Patient Chat | Approved by Coordinator_Prashna`, immediately blocking `2:00 PM - 3:00 PM` on `2026-10-13` for subsequent conflict checks.

---

## Project Structure

```text
├── app.py                  # Streamlit Two-Tab UI (Patient Chat & Coordinator Portal)
├── calendar_engine.py      # Core Excel engine, staging queue & 4 core tools
├── langchain_agent.py      # Conversational agent, patient intake parser & LLM router
├── agent.py                # Agent entry point
├── main.py                 # Interactive CLI tester
├── test_engine.py          # Pytest unit & integration suite (19 automated tests)
├── requirements.txt        # Python dependencies
├── README.md               # Documentation (Week 6 Milestone)
├── .gitignore              # Repository exclusions
└── data/
    └── Saathi_Sneha_Care_Scheduling_Calendar_Mockup.xlsx  # Excel calendar database
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
   * `OPENROUTER_API_KEY` / `GOOGLE_API_KEY`: Optional LLM API keys (falls back automatically to the deterministic 4-tool conversational engine).
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
Execute the full 19-test verification suite with `pytest`:

```bash
pytest test_engine.py -v
```

---

## Safety & Guardrails

1. **Zero Unsupervised Writes:** The AI agent only stages drafts (`DRAFT-xx`). Writing to the Excel database strictly requires human coordinator approval (`approved_by`) via `write_booking`.
2. **TOCTOU Double-Booking & Concurrency Protection:** `write_booking` acquires a thread lock (`threading.RLock`), re-runs `check_conflict` right before saving to Excel, and catches `PermissionError` if the `.xlsx` file is locked by desktop Excel.
3. **Zero Medical Advice / Triage:** Clinical emergencies bypass scheduling and escalate immediately to a human coordinator.
