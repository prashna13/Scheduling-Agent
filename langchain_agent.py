"""
LangChain Scheduling Agent Skeleton for Saathi Sneha Care.
Week 1 Deliverable: Reads the Excel calendar mockup and answers availability queries
such as "is Dr. X available on date Y?".
"""

import os
import re
import json
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv

# Load environment variables (API keys from .env if present)
load_dotenv()

# Import core deterministic calendar logic
from calendar_engine import (
    is_doctor_available,
    read_availability,
    propose_slot,
    check_conflict
)

# LangChain Imports
try:
    from langchain_core.tools import tool
    from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
    from langchain.agents import create_tool_calling_agent, AgentExecutor
    LANGCHAIN_INSTALLED = True
except ImportError:
    LANGCHAIN_INSTALLED = False
    # Lightweight fallback decorator if langchain is not yet installed in environment
    def tool(func):
        func.is_tool = True
        return func


# ==========================================
# 🛠️ 1. LANGCHAIN TOOLS DEFINITION
# ==========================================

@tool
def check_doctor_availability_tool(
    doctor_name_or_id: str, 
    date: str, 
    time_slot: Optional[str] = None
) -> str:
    """
    Checks if a specific Doctor or Nurse is available on a given date (and optional time slot)
    by reading the Saathi Sneha Care Excel schedule.
    
    Args:
        doctor_name_or_id: Name (e.g. 'Dr. Ramesh Iyer') or ID (e.g. 'DR-01') of the staff member.
        date: The target date formatted as YYYY-MM-DD (e.g. '2026-09-28') or standard date string.
        time_slot: Optional time window to check (e.g. '10:00 AM - 11:00 AM').
    
    Returns:
        A formatted JSON string with availability status, working hours, conflicts, and reason.
    """
    res = is_doctor_available(
        doctor_name_or_id=doctor_name_or_id,
        date_val=date,
        slot_str=time_slot
    )
    return json.dumps(res, indent=2)


@tool
def read_staff_availability_tool(
    date: str, 
    role: str = "Doctor"
) -> str:
    """
    Retrieves all staff members matching a role who are scheduled to work on a specific date.
    
    Args:
        date: Target date in YYYY-MM-DD format (e.g. '2026-09-28').
        role: 'Doctor' or 'Nurse' (default: 'Doctor').
    
    Returns:
        JSON string listing staff names, specialties, service areas, and shift hours.
    """
    res = read_availability(date_range=date, role=role)
    return json.dumps(res, indent=2)


@tool
def propose_available_slots_tool(
    date: str,
    role: str = "Doctor",
    specialty: Optional[str] = None,
    area: Optional[str] = None,
    time_slot: Optional[str] = None
) -> str:
    """
    Finds and proposes conflict-free candidate staff and available time slots
    matching patient intake criteria (role, specialty, date, and geographic service area).
    
    Args:
        date: Target appointment date (YYYY-MM-DD).
        role: 'Doctor' or 'Nurse'.
        specialty: Optional medical specialty (e.g. 'Geriatric care', 'General physician').
        area: Optional neighborhood/locality (e.g. 'Andheri', 'Powai', 'Bandra').
        time_slot: Optional desired time window (e.g. '10:00 AM - 11:00 AM').
    """
    res = propose_slot(
        role=role,
        specialty=specialty,
        date=date,
        area=area,
        slot=time_slot
    )
    return json.dumps(res, indent=2)


SCHEDULE_TOOLS = [
    check_doctor_availability_tool,
    read_staff_availability_tool,
    propose_available_slots_tool
]


# ==========================================
# 🤖 2. AGENT INITIALIZATION & RUNNER
# ==========================================

SYSTEM_PROMPT = """You are the AI Scheduling Sub-Agent for Saathi Sneha Care, a home healthcare provider.
Your primary role in Week 1 is to accurately answer staff availability queries (e.g. "Is Dr. X available on date Y?") by inspecting the Excel database.

Strict Safety & Operational Rules:
1. ZERO MEDICAL ADVICE: Never provide medical diagnosis, clinical triage, or treatment guidance. If a query describes an emergency (e.g. 'my father fell'), immediately escalate to human care coordinators.
2. ACCURATE EXCEL LOOKUPS: Always use your tools (`check_doctor_availability_tool`, `read_staff_availability_tool`, `propose_available_slots_tool`) to verify shifts and bookings before stating availability.
3. CONFLICT AWARENESS: Distinguish between a staff member being marked 'Off' on a weekday versus having an existing booking conflict in the Bookings Calendar.
4. CLEAR RESPONSES: Provide concise, courteous, and precise answers including working hours and exact reason for availability or conflict.
"""

def get_langchain_agent_executor() -> Optional[Any]:
    """
    Initializes and returns a LangChain AgentExecutor if an LLM is configured.
    Supports Google Gemini, OpenAI, or Anthropic based on available environment keys.
    """
    if not LANGCHAIN_INSTALLED:
        return None
        
    llm = None
    
    # 1. Google Gemini (Preferred default)
    if os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"):
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
            llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", google_api_key=api_key, temperature=0)
        except Exception:
            pass
            
    # 2. OpenAI
    if llm is None and os.getenv("OPENAI_API_KEY"):
        try:
            from langchain_openai import ChatOpenAI
            llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        except Exception:
            pass
            
    # 3. Groq / Local / Ollama fallbacks
    if llm is None and os.getenv("GROQ_API_KEY"):
        try:
            from langchain_groq import ChatGroq
            llm = ChatGroq(model_name="llama-3.1-70b-versatile", temperature=0)
        except Exception:
            pass
            
    if llm is None:
        return None
        
    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        MessagesPlaceholder(variable_name="chat_history", optional=True),
        ("human", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])
    
    agent = create_tool_calling_agent(llm, SCHEDULE_TOOLS, prompt)
    return AgentExecutor(agent=agent, tools=SCHEDULE_TOOLS, verbose=True)


# ==========================================
# ⚡ 3. DETERMINISTIC INTENT FALLBACK ROUTER
# ==========================================

def fallback_answer_query(query: str) -> str:
    """
    Deterministic rule-based agent fallback.
    Parses availability questions directly and calls the appropriate calendar tools,
    ensuring 100% functionality even when no LLM API key is configured.
    """
    query_lower = query.lower()
    
    # Extract date (YYYY-MM-DD or standard formats)
    date_match = re.search(r'(\d{4}[-/]\d{1,2}[-/]\d{1,2})', query)
    target_date = date_match.group(1).replace('/', '-') if date_match else None
    
    # Extract time slot if mentioned (e.g. 10:00 AM - 11:00 AM or 3 PM - 4 PM)
    slot_match = re.search(r'(\d{1,2}(?::\d{2})?\s*(?:am|pm)\s*[-–—to]+\s*\d{1,2}(?::\d{2})?\s*(?:am|pm))', query, re.I)
    target_slot = slot_match.group(1) if slot_match else None
    
    # Check for doctor/nurse names
    staff_names = [
        "Dr. Ramesh Iyer", "Dr. Priya Nair", 
        "Nurse Anjali Fernandes", "Nurse Sunita Rao", "Nurse Meera Joshi",
        "DR-01", "DR-02", "NR-01", "NR-02", "NR-03"
    ]
    
    found_staff = None
    for name in staff_names:
        if name.lower() in query_lower:
            found_staff = name
            break
            
    # If specific doctor availability query
    if found_staff and target_date:
        res = is_doctor_available(doctor_name_or_id=found_staff, date_val=target_date, slot_str=target_slot)
        if res["available"]:
            slot_info = f" for slot '{target_slot}'" if target_slot else ""
            open_slots = f"\n  Available Slots: {', '.join(res.get('available_slots', []))}" if res.get('available_slots') else ""
            return f"✅ Yes, {res['name']} ({res['staff_id']}) is AVAILABLE on {res['day_of_week']}, {res['date']}{slot_info}.\n  Working Hours: {res['working_hours']}{open_slots}"
        else:
            return f"❌ No, {res.get('name', found_staff)} is NOT AVAILABLE on {target_date}.\n  Reason: {res.get('reason')}"
            
    # If general "who is available on date" query
    if target_date and ("who is available" in query_lower or "list" in query_lower or "available staff" in query_lower or not found_staff):
        role = "Nurse" if "nurse" in query_lower else "Doctor"
        staff_list = read_availability(date_range=target_date, role=role)
        if not staff_list:
            return f"No {role}s are scheduled to work on {target_date}."
        
        lines = [f"📋 {len(staff_list)} {role}(s) working on {target_date}:"]
        for s in staff_list:
            lines.append(f"  • {s['name']} ({s['staff_id']}) | Specialty: {s['specialty'] or 'General'} | Hours: {s['working_hours']} | Areas: {s['service_area']}")
        return "\n".join(lines)
        
    # Default guidance
    return (
        "LangChain Agent Skeleton Ready.\n"
        "To check availability, please ask a question containing a staff name and date, for example:\n"
        "  • 'Is Dr. Ramesh Iyer available on 2026-09-28?'\n"
        "  • 'Is Dr. Priya Nair available on 2026-09-22 from 3:00 PM to 4:00 PM?'\n"
        "  • 'Who is available on 2026-09-28?'"
    )


def ask_agent(user_query: str) -> str:
    """
    Main entry point for asking the LangChain Scheduling Agent questions.
    Uses LLM tool calling if configured; falls back gracefully to deterministic tool router.
    """
    executor = get_langchain_agent_executor()
    if executor:
        try:
            result = executor.invoke({"input": user_query})
            return result.get("output", str(result))
        except Exception as e:
            print(f"[Notice: LLM invocation failed ({e}). Using deterministic tool execution]")
            return fallback_answer_query(user_query)
    else:
        return fallback_answer_query(user_query)


# ==========================================
# 🚀 4. INTERACTIVE CLI TESTING
# ==========================================

if __name__ == "__main__":
    print("=" * 70)
    print(" 🏥 SAATHI SNEHA CARE - LANGCHAIN SCHEDULING AGENT SKELETON")
    print("=" * 70)
    print("Week 1 Deliverable: Tool-augmented agent for Excel calendar queries.")
    print("Type your availability questions naturally, or type 'exit' to quit.\n")
    
    # Preset test demonstrations
    sample_queries = [
        "Is Dr. Ramesh Iyer available on 2026-09-28?",
        "Is Dr. Ramesh Iyer available on 2026-09-27?",
        "Is Dr. Priya Nair available on 2026-09-22 between 3:00 PM and 4:00 PM?",
        "Who is available on 2026-09-28?"
    ]
    
    print("--- 🧪 Running Sample Queries ---")
    for q in sample_queries:
        print(f"\nUser: {q}")
        ans = ask_agent(q)
        print(f"Agent:\n{ans}")
        print("-" * 50)
        
    print("\n--- 💬 Interactive Mode (Type your own question) ---")
    while True:
        try:
            user_input = input("\nYou: ").strip()
            if not user_input:
                continue
            if user_input.lower() in ("exit", "quit", "q"):
                print("Exiting agent. Goodbye! 👋")
                break
            response = ask_agent(user_input)
            print(f"\nAgent:\n{response}")
        except (KeyboardInterrupt, EOFError):
            print("\nExiting agent.")
            break
