# Saathi Sneha Care – Scheduling Sub-Agent (Week 1)

LangChain-based Scheduling Sub-Agent for **Saathi Sneha Care**.  
This Week-1 deliverable reads the shared Excel calendar mockup, checks staff availability, detects booking conflicts, and proposes conflict-free slots. Writes to the Excel calendar are strictly protected behind Human-in-the-Loop (HITL) approval.

---

##  Features (Week 1)

- **Excel Database Reader:** Dynamically inspects and extracts schedules from the Excel mockup (`data/Saathi_Sneha_Care_Scheduling_Calendar_Mockup.xlsx`).
- **Shift & Availability Checking:** Maps dates to weekdays and evaluates staff shift windows against `"Off"` days.
- **Deterministic Conflict Detection:** Detects overlapping time slots with active (`Confirmed` / `Pending`) bookings while ignoring cancelled rows.
- **Slot Proposal Engine:** Proposes conflict-free staff windows filtered by role, specialty, date, service area, and requested time slots.
- **Human-in-the-Loop (HITL) Safety:** `write_booking` strictly enforces coordinator authentication (`approved_by`) before appending to the Excel sheet.
- **LangChain Tool Integration:** Exposes `@tool` wrappers with an LLM agent and a deterministic fallback router (works 100% out-of-the-box even without an API key).

---

##  Project Structure

```text
├── calendar_engine.py      # Core Excel parsing & scheduling logic (pandas + openpyxl)
├── langchain_agent.py      # LangChain tools, agent executor & fallback router
├── agent.py                # Agent entry point
├── main.py                 # Interactive CLI tester
├── test_engine.py          # Pytest unit test suite
├── requirements.txt        # Project dependencies
└── data/
    └── Saathi_Sneha_Care_Scheduling_Calendar_Mockup.xlsx  # Source Excel calendar
```

---

## ⚙️ Setup & Installation

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

3. *(Optional)* **Set up API keys for LLM reasoning:**  
   Create a `.env` file in the root folder if you want to use Google Gemini, OpenAI, or Groq:
   ```env
   GOOGLE_API_KEY=your_gemini_api_key_here
   # or OPENAI_API_KEY=your_openai_key_here
   ```
   > **Note:** The agent includes a built-in deterministic fallback router, so it runs completely out-of-the-box even without an LLM API key!

---

## How to Run

### 1. Interactive CLI Tester (Recommended)
Run the interactive menu to test doctor availability, slot proposals, and booking writes:

```bash
python main.py
```

**Available Options:**
1. Check if a Doctor/Staff is available on a specific Date & Slot
2. Propose available slots for a Role, Specialty, Date & Area
3. View all available staff for a Date & Role
4. Commit a new booking to Excel Calendar (HITL Approved)
5. Run sample preset tests
6. Exit

---

### 2. LangChain Scheduling Agent
Run the natural language Q&A agent:

```bash
python langchain_agent.py
```

**Example Queries:**
- *"Is Dr. Ramesh Iyer available on 2026-09-28?"*
- *"Is Dr. Priya Nair available on 2026-09-22 from 3:00 PM to 4:00 PM?"*
- *"Is Dr. Ramesh Iyer available on 2026-09-27?"*
- *"Who is available on 2026-09-28?"*

---

### 3. Run Unit Tests
Execute the full test suite with `pytest`:

```bash
pytest test_engine.py -v
```

---

## 🛠️ Tool Interfaces (Stable API)

These tool signatures are designed to be stable so that the underlying Excel storage can later be migrated to a production database/API without modifying agent logic:

| Tool | Signature | Type | Description |
| :--- | :--- | :--- | :--- |
| `read_availability` | `(date_range: str, role: str) -> List[Dict]` | Read-only | Returns all staff of a given role working on the target date. |
| `check_conflict` | `(staff_id: str, slot: str, date: str) -> bool` | Read-only | Returns `True` if the requested slot overlaps an active booking. |
| `propose_slot` | `(role, specialty, date, area, slot=None) -> List[Dict]` | Read-only | Returns ranked, conflict-free staff candidates and open windows. |
| `write_booking` | `(booking_data: dict, approved_by: str) -> Dict` | Write | Appends new booking row to Excel (strictly requires `approved_by`). |

---

## 🛡️ Safety & Guardrails (Week 1)

1. **Zero Unsupervised Writes:** The agent never commits rows to Excel autonomously. All write actions halt until explicit human approval (`approved_by`) is provided.
2. **Zero Medical Advice / Triage:** Hard guardrail. Any clinical diagnosis, emergency (e.g. *"patient fell"*), or medical advice request bypasses scheduling and escalates immediately to a human coordinator.
3. **Deterministic Overlap Checks:** Math-based time range comparisons prevent double-booking staff across overlapping intervals.

---

## 📝 Technical Notes

- **Excel as Database:** Uses `pandas` for dynamic header resolution and multi-sheet reading; uses `openpyxl` for safe append writes preserving formulas.
- **Decoupled Architecture:** Core calendar logic (`calendar_engine.py`) is completely independent of the LLM layer (`langchain_agent.py`), allowing easy testing and model switching.