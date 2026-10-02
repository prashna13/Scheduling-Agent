"""
LangChain Scheduling Agent for Saathi Sneha Care.
Equipped strictly with the 4 core tools:
1. read_availability
2. check_conflict
3. propose_slot
4. write_booking

Model Configuration:
- Primary: openai/gpt-oss-120b:free (via OpenRouter / OpenAI API)
- Secondary: Google Gemini (gemini-1.5-flash)
- Fallback: Deterministic 4-tool conversational engine
"""

import os
import re
import json
import unicodedata
from typing import Optional, Dict, Any, List
import requests
from dotenv import load_dotenv

load_dotenv()

# Import the 4 core calendar tools
from calendar_engine import (
    read_availability,
    check_conflict,
    propose_slot,
    write_booking,
    parse_date,
    load_sheet
)

# LangChain Imports
try:
    from langchain_core.tools import tool
    from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
    from langchain.agents import create_tool_calling_agent, AgentExecutor
    LANGCHAIN_INSTALLED = True
except ImportError:
    LANGCHAIN_INSTALLED = False
    def tool(func):
        func.name = func.__name__
        func.description = func.__doc__
        func.is_tool = True
        return func


# =========================================================================
# 🛠️ THE 4 CORE TOOLS (REGISTERED FOR AGENT)
# =========================================================================

@tool
def read_availability_tool(date_range: str, role: str = "Nurse") -> str:
    """
    TOOL 1: Reads the Staff Availability sheet and returns all staff matching the role
    who are scheduled to work on the given date (excluding 'Off' days).
    
    Args:
        date_range: Target date formatted as YYYY-MM-DD (e.g. '2026-09-24').
        role: 'Nurse' or 'Doctor' (default: 'Nurse').
    """
    res = read_availability(date_range=date_range, role=role)
    return json.dumps(res, indent=2)


@tool
def check_conflict_tool(staff_id: str, slot: str, date: str) -> str:
    """
    TOOL 2: Checks whether a proposed time slot conflicts with an active booking in the
    Bookings Calendar or falls outside the staff member's working hours.
    
    Args:
        staff_id: Staff ID (e.g. 'NR-01', 'DR-01') or Staff Name.
        slot: Proposed time slot (e.g. '10:00 AM - 11:00 AM').
        date: Target date formatted as YYYY-MM-DD.
    
    Returns:
        JSON string indicating {"conflict": True/False, "available": True/False}.
    """
    has_conflict = check_conflict(staff_id=staff_id, slot=slot, date=date)
    return json.dumps({
        "staff_id": staff_id,
        "date": date,
        "slot": slot,
        "has_conflict": has_conflict,
        "available": not has_conflict
    }, indent=2)


@tool
def propose_slot_tool(
    role: str = "Nurse",
    specialty: Optional[str] = None,
    date: Optional[str] = None,
    area: Optional[str] = None,
    slot: Optional[str] = None
) -> str:
    """
    TOOL 3: Evaluates staff shifts and booking conflicts to propose the top 2-3
    conflict-free candidate staff members and available time windows.
    
    Args:
        role: 'Nurse' or 'Doctor'.
        specialty: Optional specialty (e.g. 'Geriatric care', 'Elderly / palliative care').
        date: Target appointment date (YYYY-MM-DD).
        area: Optional neighborhood/locality (e.g. 'Bandra', 'Powai', 'Andheri').
        slot: Optional desired time slot.
    """
    res = propose_slot(
        role=role,
        specialty=specialty,
        date=date,
        area=area,
        slot=slot
    )
    return json.dumps(res, indent=2)


@tool
def write_booking_tool(booking_data: dict, approved_by: str) -> str:
    """
    TOOL 4: Human-in-the-loop coordinator approval gate.
    Validates the booking draft and requires a non-empty approved_by coordinator ID.
    """
    res = write_booking(booking_data=booking_data, approved_by=approved_by)
    return json.dumps(res, indent=2)


CORE_TOOLS = [
    read_availability_tool,
    check_conflict_tool,
    propose_slot_tool,
    write_booking_tool
]


# =========================================================================
# 🤖 MODEL PROMPT & CONFIGURATION
# =========================================================================

SYSTEM_PROMPT = """You are the friendly, professional AI Care Coordinator for Saathi Sneha Care in Mumbai.
You communicate conversationally with clients and coordinators to check doctor and nurse availability for home healthcare visits.

You have access to exactly 4 core tools:
1. `read_availability_tool`: Look up staff on duty for a date.
2. `check_conflict_tool`: Check if a staff member has a time slot conflict or is off.
3. `propose_slot_tool`: Propose 2-3 conflict-free time slots for available staff.
4. `write_booking_tool`: Stage an approved booking (requires coordinator approved_by).
"""

LLM_CONVERSATIONAL_PROMPT = """You are the friendly, professional AI Care Coordinator for Saathi Sneha Care in Mumbai communicating with patients and families over WhatsApp and social messaging.

Rules:
1. Ground your response strictly on the verified schedule information provided.
2. If staff is available, greet warmly, confirm their availability on that day, and propose the 2-3 time slots.
3. If staff is unavailable (marked Off or booked), explain why and offer the alternative staff members and their available slots.
4. Always speak directly to the patient in full, natural, empathetic sentences. Never mention tool names, function names, or internal code.
5. ZERO MEDICAL ADVICE: Never diagnose or provide medical treatments."""

PRIMARY_MODEL = os.getenv("PRIMARY_MODEL", "openai/gpt-oss-120b")
SECONDARY_MODEL = os.getenv("SECONDARY_MODEL", "gemini-2.5-flash")


def call_openrouter_api(query: str, api_key: str, model_name: str = PRIMARY_MODEL) -> Optional[str]:
    """Direct API caller for OpenRouter openai/gpt-oss-120b grounded by 4 core tools."""
    url = os.getenv("OPENAI_BASE_URL", "https://openrouter.ai/api/v1/chat/completions")
    if not url.endswith("/chat/completions"):
        url = url.rstrip("/") + "/chat/completions"
        
    headers = {
        "Authorization": f"Bearer {api_key.strip()}",
        "HTTP-Referer": "https://saathisnehacare.org",
        "X-Title": "Saathi Sneha Care Scheduling Agent",
        "Content-Type": "application/json"
    }
    
    # Ground LLM with verified 4-tool deterministic calculation
    grounded_eval = fallback_answer_query(query)
    
    messages = [
        {"role": "system", "content": f"{LLM_CONVERSATIONAL_PROMPT}\n\nVerified Real-Time Calendar Schedule Info:\n{grounded_eval}"},
        {"role": "user", "content": f"Write the patient response for this inquiry: '{query}'"}
    ]
    
    payload = {
        "model": model_name,
        "messages": messages,
        "temperature": 0.3
    }
    
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=12)
        if resp.status_code == 200:
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            if content and not content.strip().lower().startswith("we need to call") and not content.strip().lower().startswith("we will call"):
                return unicodedata.normalize("NFKC", content)
    except Exception:
        pass
    return None


def call_gemini_api(query: str, api_key: str, model_name: str = SECONDARY_MODEL) -> Optional[str]:
    """Direct REST API caller for Google Gemini grounded by 4 core tools."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key.strip()}"
    headers = {"Content-Type": "application/json"}
    
    grounded_eval = fallback_answer_query(query)
    
    prompt_text = (
        f"{LLM_CONVERSATIONAL_PROMPT}\n\n"
        f"Verified Real-Time Calendar Schedule Info:\n{grounded_eval}\n\n"
        f"Patient Query: {query}\n"
        f"Write the final direct conversational response to the patient."
    )
    
    payload = {
        "contents": [{"parts": [{"text": prompt_text}]}],
        "generationConfig": {"temperature": 0.3}
    }
    
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=12)
        if resp.status_code == 200:
            data = resp.json()
            candidates = data.get("candidates", [])
            if candidates:
                content = candidates[0]["content"]["parts"][0]["text"]
                if content and not content.strip().lower().startswith("we need to call") and not content.strip().lower().startswith("we will call"):
                    return unicodedata.normalize("NFKC", content)
    except Exception:
        pass
    return None


def get_langchain_agent_executor(api_key_override: Optional[str] = None) -> Optional[Any]:
    """
    Initializes primary LLM (OpenRouter / OpenAI gpt-oss-120b:free) or secondary (Google Gemini).
    """
    if not LANGCHAIN_INSTALLED:
        return None
        
    llm = None
    
    # 1. PRIMARY: OpenRouter / OpenAI (openai/gpt-oss-120b:free)
    openrouter_key = api_key_override or os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
    if openrouter_key:
        base_url = os.getenv("OPENAI_BASE_URL", "https://openrouter.ai/api/v1")
        try:
            from langchain_openai import ChatOpenAI
            llm = ChatOpenAI(
                model=PRIMARY_MODEL,
                openai_api_key=openrouter_key,
                openai_api_base=base_url,
                temperature=0.3
            )
        except Exception:
            pass

    # 2. SECONDARY: Google Gemini
    if llm is None:
        gemini_key = api_key_override or os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if gemini_key:
            try:
                from langchain_google_genai import ChatGoogleGenerativeAI
                llm = ChatGoogleGenerativeAI(
                    model=SECONDARY_MODEL,
                    google_api_key=gemini_key,
                    temperature=0.3
                )
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
    
    agent = create_tool_calling_agent(llm, CORE_TOOLS, prompt)
    return AgentExecutor(agent=agent, tools=CORE_TOOLS, verbose=False)


# =========================================================================
# 💬 CONVERSATIONAL FALLBACK ROUTER (4 CORE TOOLS)
# =========================================================================

def fallback_answer_query(query: str) -> str:
    """
    Deterministic conversational engine powered strictly by the 4 core tools:
    `read_availability`, `check_conflict`, `propose_slot`, `write_booking`.
    """
    query_lower = query.lower()
    
    # Extract date
    date_match = re.search(r'(\d{4}[-/]\d{1,2}[-/]\d{1,2})', query)
    target_date = date_match.group(1).replace('/', '-') if date_match else None
    
    # Extract slot
    slot_match = re.search(r'(\d{1,2}(?::\d{2})?\s*(?:am|pm)\s*[-–—to]+\s*\d{1,2}(?::\d{2})?\s*(?:am|pm))', query, re.I)
    target_slot = slot_match.group(1) if slot_match else None
    
    # Identify role
    role = "Nurse" if "nurse" in query_lower or "nr-" in query_lower else "Doctor"
    
    # Identify requested staff
    staff_registry = [
        ("Nurse Anjali Fernandes", "NR-01", "Nurse"),
        ("Nurse Sunita Rao", "NR-02", "Nurse"),
        ("Nurse Meera Joshi", "NR-03", "Nurse"),
        ("Dr. Ramesh Iyer", "DR-01", "Doctor"),
        ("Dr. Priya Nair", "DR-02", "Doctor")
    ]
    
    target_staff = None
    for name, s_id, s_role in staff_registry:
        last_name = name.split()[-1].lower()
        if (name.lower() in query_lower or s_id.lower() in query_lower or last_name in query_lower):
            target_staff = (name, s_id, s_role)
            role = s_role
            break

    # SCENARIO 1: Checking specific staff on date
    if target_staff and target_date:
        s_name, s_id, s_role = target_staff
        
        # Tool 1: Check availability
        staff_on_duty = read_availability(date_range=target_date, role=s_role)
        is_on_duty = any(s["staff_id"] == s_id for s in staff_on_duty)
        
        # Tool 2: Check conflict
        has_conflict = check_conflict(staff_id=s_id, slot=target_slot or "10:00 AM - 11:00 AM", date=target_date) if target_slot else check_conflict(staff_id=s_id, slot="", date=target_date)
        
        # Tool 3: Propose slots
        cands = propose_slot(role=s_role, date=target_date, slot=target_slot)
        matching_cand = next((c for c in cands if c["staff_id"] == s_id), None)
        
        parsed_d = parse_date(target_date)
        date_friendly = parsed_d.strftime("%A, %B %d, %Y") if parsed_d else target_date
        
        if is_on_duty and matching_cand:
            slots = matching_cand.get("proposed_slots", [])
            slots_str = "\n".join([f"  • {s}" for s in slots]) if slots else f"  • {matching_cand['working_hours']}"
            
            return (
                f"Hello! 👋 Great news — **{s_name}** is **available** on **{date_friendly}**.\n\n"
                f"Their working shift for that day is **{matching_cand['working_hours']}** (Specialty: {matching_cand.get('specialty', 'General')}, Area: {matching_cand.get('service_area', 'Mumbai')}).\n\n"
                f"Here are 2–3 convenient time slots I can propose for your visit:\n"
                f"{slots_str}\n\n"
                f"Would you like me to reserve one of these times for you? 😊"
            )
        else:
            # Offer alternatives using Tool 3 (propose_slot)
            alt_cands = [c for c in cands if c["staff_id"] != s_id]
            alt_text = ""
            if alt_cands:
                alt_lines = [f"  • **{a['name']}** ({a['specialty']}) — Shift: {a['working_hours']}" for a in alt_cands[:2]]
                alt_text = f"\n\nHowever, we have other available {s_role.lower()}s on {date_friendly}:\n" + "\n".join(alt_lines) + "\n\nWould you like to check slots with one of them instead?"
            else:
                alt_text = f"\n\nWould you like me to check an alternate date for {s_name}?"
                
            reason = f"marked 'Off' on {date_friendly}" if not is_on_duty else f"booked or conflicting for the requested time"
            return (
                f"Hello! I checked the schedule, but unfortunately **{s_name}** is **not available** on **{date_friendly}** ({reason})."
                f"{alt_text}"
            )

    # SCENARIO 2: General "Is a nurse / doctor free on date"
    if target_date:
        cands = propose_slot(role=role, date=target_date, slot=target_slot)
        parsed_d = parse_date(target_date)
        date_friendly = parsed_d.strftime("%A, %B %d, %Y") if parsed_d else target_date
        
        if cands:
            lines = [f"• **{c['name']}** ({c['specialty']}) — Shift: {c['working_hours']} | Proposed Slots: {', '.join(c['proposed_slots'][:2])}" for c in cands]
            return (
                f"Hello! 😊 Yes, we have **{len(cands)} {role.lower()}(s)** available on **{date_friendly}**:\n\n"
                + "\n".join(lines) +
                f"\n\nWould you like to book a visit with one of them?"
            )
        else:
            return (
                f"Hello! We currently don't have any {role.lower()}s available on **{date_friendly}**.\n\n"
                f"Could we check another date for you?"
            )

    return (
        "Hello! 👋 Welcome to **Saathi Sneha Care**.\n\n"
        "I can help you check staff availability and propose home visit slots in Mumbai.\n\n"
        "Try asking me:\n"
        "• *'Is Dr. Iyer free on 2026-09-28?'*\n"
        "• *'Is Nurse Sunita available on 2026-09-24?'*\n"
        "• *'Is any nurse free on 2026-09-23?'*"
    )


def ask_agent(user_query: str, api_key_override: Optional[str] = None) -> str:
    """
    Main query entry point:
    1. Attempts Primary LLM: openai/gpt-oss-120b via OpenRouter
    2. Attempts Secondary LLM: Google Gemini (gemini-2.5-flash)
    3. Attempts LangChain Tool-Calling Agent
    4. Falls back to deterministic 4-tool conversational engine
    """
    # 1. Primary LLM: OpenRouter (openai/gpt-oss-120b)
    openrouter_key = api_key_override or os.getenv("OPENROUTER_API_KEY") or (os.getenv("OPENAI_API_KEY") if "sk-or" in (os.getenv("OPENAI_API_KEY") or "") else None)
    if openrouter_key:
        direct_resp = call_openrouter_api(user_query, openrouter_key, PRIMARY_MODEL)
        if direct_resp and direct_resp.strip():
            return direct_resp

    # 2. Secondary LLM: Google Gemini
    gemini_key = api_key_override or os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if gemini_key and "sk-or" not in (gemini_key or ""):
        gemini_resp = call_gemini_api(user_query, gemini_key, SECONDARY_MODEL)
        if gemini_resp and gemini_resp.strip():
            return gemini_resp

    # 3. LangChain Agent
    executor = get_langchain_agent_executor(api_key_override=api_key_override)
    if executor:
        try:
            result = executor.invoke({"input": user_query})
            return result.get("output", str(result))
        except Exception:
            return fallback_answer_query(user_query)

    # 4. Deterministic 4-tool engine
    return fallback_answer_query(user_query)
