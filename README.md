# Saathi Sneha Care - Scheduling Sub-Agent (Week 3)

LangChain-based Scheduling Sub-Agent and Streamlit Web Application for Saathi Sneha Care.  
This milestone delivers the Week 3 core requirement: **Intelligent 2-3 time slot proposals for patient visit requests, moving beyond simple yes/no responses.**

---

## Core Capabilities (Week 3 Milestone)

1. **Intelligent 2-3 Slot Proposal Engine:**  
   When a patient or coordinator asks about clinician availability, the agent evaluates active shifts and calendar bookings to compute and suggest 2-3 discrete, non-overlapping 1-hour appointment slots (e.g. 9:00 AM - 10:00 AM, 10:00 AM - 11:00 AM).
2. **Deterministic Schedule Verification (Single Source of Truth):**  
   Every client inquiry is evaluated against the Excel calendar database (`data/Saathi_Sneha_Care_Scheduling_Calendar_Mockup.xlsx`) using the 4 core calendar tools.
3. **Smart Alternative Recommendations with Open Slots:**  
   When a requested doctor or nurse is unavailable (marked "Off" or booked), the agent explains the reason and proposes available alternative staff with matching qualifications, including their open 1-hour slots.
4. **Natural Conversational Client Interface:**  
   Mimics customer messaging devices (WhatsApp / Web Chat). Clients ask questions naturally about doctor & nurse availability, working hours, and bookings.
5. **Non-Existent Staff Disclaimer:**  
   If an inquired clinician is not registered in the system (e.g. Dr. John Doe), the agent politely notes this and presents on-duty staff with open time slots for that day.

---

## The 4 Core Tool Interfaces

| Tool | Signature | Type | Description |
| :--- | :--- | :--- | :--- |
| `read_availability` | `(date_range: str, role: str) -> List[Dict]` | Read-only | Returns all staff of a given role working on the target date. |
| `check_conflict` | `(staff_id: str, slot: str, date: str) -> bool` | Read-only | Returns `True` if the requested slot overlaps an active booking or is outside working hours. |
| `propose_slot` | `(role, specialty, date, area, slot=None) -> List[Dict]` | Read-only | Evaluates working shifts and active bookings to generate 2-3 conflict-free 1-hour time slots. |
| `write_booking` | `(booking_data: dict, approved_by: str) -> Dict` | Write Gate | Validates and stages booking proposal (strictly requires `approved_by` coordinator identifier). |

---

## Example Interaction (Week 3 Slot Proposal)

### Scenario A: Doctor Availability with 2-3 Proposed Slots
* **User Query:** *"Is Dr. Priya Nair available on Thursday, 15-Oct-2026?"*
* **Agent Response:**  
  *"Great news! Dr. Priya Nair is available on Thursday, 15 October 2026. Her working shift is 2:00 PM - 6:00 PM (Specialty: Geriatric care, Area: Powai, Ghatkopar). Here are convenient 1-hour time slots I can propose for your visit:*  
  *• 2:00 PM - 3:00 PM*  
  *• 3:00 PM - 4:00 PM*  
  *• 4:00 PM - 5:00 PM*  
  *Would you like me to reserve one of these times for you?"*

### Scenario B: Clinician Unavailable with Alternative Slots
* **User Query:** *"Can I book Dr. Priya Nair on Wednesday, 23-Sep-2026?"*
* **Agent Response:**  
  *"Dr. Priya Nair is not available on Wednesday, 23 September 2026 (marked 'Off'). However, Dr. Ramesh Iyer is available (Shift: 9:00 AM - 1:00 PM) with open slots: 9:00 AM - 10:00 AM, 10:00 AM - 11:00 AM. Would you like to check slots with Dr. Ramesh Iyer instead?"*

---

## Project Structure

```text
├── app.py                  # Streamlit Customer Conversational Interface
├── calendar_engine.py      # Core Excel parsing, shift & conflict logic (4 tools)
├── langchain_agent.py      # LangChain agent, LLM integration & fallback router
├── agent.py                # Agent entry point
├── main.py                 # Interactive CLI tester
├── test_engine.py          # Pytest unit tests (17 automated tests)
├── requirements.txt        # Python dependencies
├── README.md               # Documentation (Week 3 Milestone)
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
Execute the full test suite with `pytest`:

```bash
pytest test_engine.py -v
```

---

## Safety & Guardrails

1. **Zero Unsupervised Writes:** The agent never commits rows to Excel autonomously. All write actions require explicit coordinator authorization (`approved_by`).
2. **Zero Medical Advice / Triage:** Hard guardrail. Clinical emergencies bypass scheduling and escalate immediately to a human coordinator.
3. **Deterministic Overlap Checks:** Math-based time range comparisons prevent double-booking staff across overlapping intervals.
