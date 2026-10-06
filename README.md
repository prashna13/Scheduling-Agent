# Saathi Sneha Care - Scheduling Sub-Agent (Week 2)

LangChain-based Scheduling Sub-Agent and Streamlit Web Application for **Saathi Sneha Care**.  
This deliverable implements four focused core workflows using the four primary calendar tools against the Excel mockup database (`data/Saathi_Sneha_Care_Scheduling_Calendar_Mockup.xlsx`).

---

## Core Capabilities (Week 2 Scope)

1. **Natural Conversational Client Interface:**  
   Mimics customer messaging devices (WhatsApp / Web Chat). Clients ask questions naturally about doctor & nurse availability, working hours, and bookings.
2. **Deterministic Schedule Verification (Single Source of Truth):**  
   Every client inquiry is evaluated against the Excel calendar database (`data/Saathi_Sneha_Care_Scheduling_Calendar_Mockup.xlsx`) using the 4 core calendar tools.
3. **Availability Confirmation & 2-3 Slot Proposals:**  
   When a requested doctor or nurse is free on a date, confirms availability and proposes 2-3 conflict-free appointment time slots.
4. **Alternative Staff & Slot Recommendations:**  
   When a requested doctor or nurse is unavailable (marked "Off" or booked), explains the reason and recommends available alternative staff along with their open slots.

---

## Core 4 Tool Interfaces

| Tool | Signature | Type | Description |
| :--- | :--- | :--- | :--- |
| `read_availability` | `(date_range: str, role: str) -> List[Dict]` | Read-only | Returns all staff of a given role working on the target date. |
| `check_conflict` | `(staff_id: str, slot: str, date: str) -> bool` | Read-only | Returns `True` if the requested slot overlaps an active booking or is outside working hours. |
| `propose_slot` | `(role, specialty, date, area, slot=None) -> List[Dict]` | Read-only | Ranks conflict-free candidates and generates 2-3 open slots. |
| `write_booking` | `(booking_data: dict, approved_by: str) -> Dict` | Write Gate | Validates and stages booking proposal (strictly requires `approved_by` coordinator identifier). |

---

## Project Structure

```text
├── app.py                  # Streamlit Customer Conversational Interface
├── calendar_engine.py      # Core Excel parsing, shift & conflict logic (4 tools)
├── langchain_agent.py      # LangChain agent & availability tools
├── agent.py                # Agent entry point
├── main.py                 # Interactive CLI tester
├── test_engine.py          # Pytest unit tests
├── requirements.txt        # Python dependencies
├── README.md               # Documentation
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

## How to Run

### 1. Launch the Streamlit Web Application (Recommended)
Run the web interface with visual availability cards and alternative recommendations:

```bash
streamlit run app.py
```

### 2. Interactive CLI Tester
Run the terminal-based interactive menu:

```bash
python main.py
```

### 3. LangChain Scheduling Agent
Run the natural language Q&A agent:

```bash
python langchain_agent.py
```

### 4. Run Unit Tests
Execute the full test suite with `pytest`:

```bash
pytest test_engine.py -v
```

---

## Safety & Guardrails

1. **Zero Unsupervised Writes:** The agent never commits rows to Excel autonomously. All write actions require explicit coordinator authorization (`approved_by`).
2. **Zero Medical Advice / Triage:** Hard guardrail. Any clinical emergency (e.g. "patient fell") bypasses scheduling and escalates immediately to a human coordinator.
3. **Deterministic Overlap Checks:** Math-based time range comparisons prevent double-booking staff across overlapping intervals.
