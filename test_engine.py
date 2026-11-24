import os
import pytest
from datetime import date, time, timedelta
import calendar_engine


@pytest.fixture(autouse=True)
def _isolate_staged_drafts(tmp_path, monkeypatch):
    """Ensure tests never overwrite or wipe real data/staged_drafts.json on disk."""
    isolated_path = str(tmp_path / "test_staged_drafts.json")
    monkeypatch.setattr(calendar_engine, "STAGED_DRAFTS_PATH", isolated_path)
    monkeypatch.setattr(calendar_engine, "_STAGED_DRAFTS", [])
    monkeypatch.setattr(calendar_engine, "_DRAFT_COUNTER", 0)
    yield


def _next_weekday(target_weekday: int) -> date:
    """Returns the next future date matching target_weekday (0=Mon .. 6=Sun)."""
    today = date.today()
    days_ahead = (target_weekday - today.weekday()) % 7
    return today + timedelta(days=days_ahead or 7)
from calendar_engine import (
    read_availability,
    check_conflict,
    propose_slot,
    write_booking,
    parse_date,
    parse_time_range,
    times_overlap,
    is_time_within_window,
    get_available_windows,
    load_sheet,
    get_staff_registry,
    suggest_slots_for_request,
    _SHEET_CACHE
)
from langchain_agent import (
    ask_agent,
    extract_date_from_query,
    read_availability_tool,
    check_conflict_tool,
    propose_slot_tool,
    write_booking_tool,
    CORE_TOOLS,
    AGENT_READ_ONLY_TOOLS,
    SYSTEM_PROMPT
)

# ==========================================
# 1. PARSING & HELPER TESTS
# ==========================================

def test_parse_date():
    assert parse_date("2026-09-24") == date(2026, 9, 24)
    assert parse_date("2026/09/24") == date(2026, 9, 24)
    assert parse_date("September 24, 2026") == date(2026, 9, 24)

def test_robust_time_parsing():
    r1 = parse_time_range("8:00 AM - 4:00 PM")
    assert r1 == (time(8, 0), time(16, 0))
    
    r2 = parse_time_range("8:00am-4:00pm")
    assert r2 == (time(8, 0), time(16, 0))
    
    r3 = parse_time_range("9:00 AM – 5:00 PM")
    assert r3 == (time(9, 0), time(17, 0))

def test_times_overlap():
    assert times_overlap("10:30 AM - 11:30 AM", "10:00 AM - 11:00 AM") is True
    assert times_overlap("10:30 AM - 11:30 AM", "12:00 PM - 1:00 PM") is False

def test_available_windows():
    windows = get_available_windows("9:00 AM - 5:00 PM", ["10:00 AM - 11:00 AM"])
    assert "9:00 AM - 10:00 AM" in windows
    assert "10:00 AM - 11:00 AM" not in windows
    assert "11:00 AM - 12:00 PM" in windows

def test_in_memory_cache():
    df1 = load_sheet("Staff Availability")
    df2 = load_sheet("Staff Availability")
    assert df1.equals(df2)
    assert len(_SHEET_CACHE) > 0

def test_dynamic_staff_registry():
    registry = get_staff_registry()
    assert len(registry) >= 5
    staff_ids = [s[1] for s in registry]
    assert "DR-01" in staff_ids
    assert "NR-01" in staff_ids

def test_natural_date_extraction():
    assert extract_date_from_query("Is Dr. Iyer free on 2026-09-28?") == "2026-09-28"
    assert extract_date_from_query("Is Nurse Sunita free on Sept 24?") == "2026-09-24"
    assert extract_date_from_query("Is Dr. Priya available on 23rd September 2026?") == "2026-09-23"
    assert extract_date_from_query("Any nurse on 21-09-2026?") == "2026-09-21"
    assert extract_date_from_query("Can I book Dr. Priya Nair on Tuesday, 13-Oct-2026, from 3:00 PM to 4:00 PM?") == "2026-10-13"
    assert extract_date_from_query("Is Dr. Ramesh Iyer free on Wednesday, 14-Oct-2026, from 11:00 AM to 12:00 PM?") == "2026-10-14"
    assert extract_date_from_query("Book Dr. Priya on Oct-13-2026") == "2026-10-13"

# ==========================================
# 2. TOOL 1: read_availability TESTS
# ==========================================

def test_read_availability_nurses():
    # Thursday 2026-09-24: NR-01 and NR-03 are on duty
    nurses = read_availability(date_range="2026-09-24", role="Nurse")
    assert len(nurses) > 0
    nurse_ids = [n["staff_id"] for n in nurses]
    assert "NR-01" in nurse_ids or "NR-03" in nurse_ids

def test_read_availability_off_days():
    # Wednesday 2026-09-23: Dr. Iyer (DR-01) is On (9am-1pm), Dr. Priya Nair (DR-02) is Off
    docs_wed = read_availability(date_range="2026-09-23", role="Doctor")
    doc_ids_wed = [d["staff_id"] for d in docs_wed]
    assert "DR-01" in doc_ids_wed
    assert "DR-02" not in doc_ids_wed

    # Sunday 2026-09-27: Dr. Iyer (DR-01) and Dr. Priya Nair (DR-02) are both Off
    docs_sun = read_availability(date_range="2026-09-27", role="Doctor")
    assert len(docs_sun) == 0

# ==========================================
# 3. TOOL 2: check_conflict TESTS
# ==========================================

def test_check_conflict_booking_overlap():
    # Nurse Sunita Rao (NR-02) has active booking BK-102 on Monday 2026-09-21 at 10:30 AM - 11:30 AM
    conflict_found = check_conflict(staff_id="NR-02", slot="10:30 AM - 11:30 AM", date="2026-09-21")
    assert conflict_found is True
    
    # But should be free in another slot
    no_conflict = check_conflict(staff_id="NR-02", slot="2:00 PM - 3:00 PM", date="2026-09-21")
    assert no_conflict is False

def test_check_conflict_off_day():
    # Dr. Ramesh Iyer is Off on Sunday 2026-09-27
    conflict_off = check_conflict(staff_id="DR-01", slot="10:00 AM - 11:00 AM", date="2026-09-27")
    assert conflict_off is True

# ==========================================
# 4. TOOL 3: propose_slot TESTS
# ==========================================

def test_propose_slot_returns_2_to_3_slots():
    # Check slot proposal for nurses on 2026-09-24
    cands = propose_slot(role="Nurse", date="2026-09-24")
    assert len(cands) > 0
    first_cand = cands[0]
    assert "proposed_slots" in first_cand
    assert len(first_cand["proposed_slots"]) <= 3
    assert len(first_cand["proposed_slots"]) >= 1

def test_propose_slot_with_specialty_and_area():
    cands = propose_slot(role="Nurse", specialty="General", date="2026-09-24", area="Andheri")
    for c in cands:
        assert "andheri" in c["service_area"].lower() or "mumbai" in c["service_area"].lower()

# ==========================================
# 5. TOOL 4: write_booking & STAGING TESTS
# ==========================================

def test_write_booking_validation(tmp_path):
    import shutil
    from calendar_engine import EXCEL_PATH, get_next_booking_id
    temp_excel = str(tmp_path / "test_calendar.xlsx")
    shutil.copyfile(EXCEL_PATH, temp_excel)

    # Test 1: Missing approved_by should raise ValueError
    with pytest.raises(ValueError, match="CRITICAL SECURITY ERROR"):
        write_booking(booking_data={"patient_name": "Test"}, approved_by="", excel_path=temp_excel)

    # Test 2: Valid coordinator approval generates sequential ID (e.g. BK-113) and writes to Excel
    future_tue = _next_weekday(1).strftime("%Y-%m-%d")
    expected_next_id = get_next_booking_id(excel_path=temp_excel)
    booking_payload = {
        "patient_name": "Mr. Vinod Kulkarni",
        "contact_number": "+91 90xxxxxx14",
        "date": future_tue,
        "time_slot": "2:00 PM - 3:00 PM",
        "assigned_staff": "Dr. Priya Nair",
        "staff_role": "Doctor",
        "service_type": "Geriatric consult",
        "address_area": "Ghatkopar",
        "status": "Confirmed",
        "notes": "Follow-up visit"
    }
    # Verify slot is initially conflict-free
    assert check_conflict(staff_id="DR-02", slot="2:00 PM - 3:00 PM", date=future_tue, excel_path=temp_excel) is False

    res = write_booking(booking_data=booking_payload, approved_by="Coordinator_Prashna", excel_path=temp_excel)
    assert res["status"] == "success"
    assert res["approved_by"] == "Coordinator_Prashna"
    assert res["booking_id"] == expected_next_id

    # Test 3: Immediate subsequent check_conflict call on that slot returns True (conflict found)
    assert check_conflict(staff_id="DR-02", slot="2:00 PM - 3:00 PM", date=future_tue, excel_path=temp_excel) is True

    # Test 4: TOCTOU Double-Booking Guard blocks duplicate write_booking on the same slot
    with pytest.raises(ValueError, match="CONFLICT ERROR"):
        write_booking(booking_data=booking_payload, approved_by="Coordinator_Prashna", excel_path=temp_excel)

    # Test 5: Title-Case keys from main.py CLI caller are normalized and written to Excel
    main_cli_payload = {
        "Date": future_tue,
        "Time Slot": "3:00 PM - 4:00 PM",
        "Patient Name": "Mrs. Asha Deshmukh",
        "Service Type": "Geriatric consult",
        "Assigned Staff": "Dr. Priya Nair",
        "Staff Role": "Doctor",
        "Contact Number": "+91 9820112233",
        "Address / Area": "Powai"
    }
    res_cli = write_booking(main_cli_payload, approved_by="Coordinator_Prashna", excel_path=temp_excel)
    assert res_cli["booking_id"].startswith("BK-")
    assert check_conflict(staff_id="DR-02", slot="3:00 PM - 4:00 PM", date=future_tue, excel_path=temp_excel) is True

def test_conversational_draft_staging_and_multiturn():
    import os
    from calendar_engine import get_staged_drafts, _STAGED_DRAFTS, STAGED_DRAFTS_PATH, _save_drafts_to_disk
    from langchain_agent import fallback_answer_query
    _STAGED_DRAFTS.clear()
    _save_drafts_to_disk()

    future_tue_dt = _next_weekday(1)
    future_tue_iso = future_tue_dt.strftime("%Y-%m-%d")
    future_tue_label = future_tue_dt.strftime("%d-%b-%Y")
    future_fri_dt = _next_weekday(4)
    future_fri_label = future_fri_dt.strftime("%d %B %Y")

    # Step A: Booking request WITHOUT patient details asks the patient for required Excel fields first
    q1 = f"Can I book Dr. Priya Nair on Tuesday, {future_tue_label}, from 2:00 PM to 3:00 PM?"
    reply1 = fallback_answer_query(q1)
    assert "awaiting patient intake details" in reply1.lower()
    assert "patient full name" in reply1.lower()
    assert "contact number" in reply1.lower()
    assert "address / area" in reply1.lower()
    assert "service type" in reply1.lower()
    assert len(get_staged_drafts()) == 0

    # Step B: Patient replies with lowercase name & 10-digit phone -> Normalized & staged to JSON disk
    history = [
        {"role": "user", "content": q1},
        {"role": "assistant", "content": reply1}
    ]
    reply2 = fallback_answer_query(
        "rahul sharma, 9876543210, ghatkopar, geriatric consult",
        chat_history=history
    )
    assert "prepared your appointment draft" in reply2.lower()
    assert os.path.exists(STAGED_DRAFTS_PATH)
    drafts = get_staged_drafts()
    assert len(drafts) == 1
    assert drafts[0]["patient_name"] == "Rahul Sharma"
    assert drafts[0]["contact_number"] == "+91 9876543210"
    assert drafts[0]["address_area"] == "Ghatkopar"
    assert drafts[0]["service_type"] == "geriatric consult"
    assert drafts[0]["assigned_staff"] == "Dr. Priya Nair"
    assert drafts[0]["date"] == future_tue_iso
    assert drafts[0]["time_slot"] == "2:00 PM - 3:00 PM"

    # Step C: Cancellation dismisses the actual staged draft for this session
    reply_cancel = fallback_answer_query("never mind, cancel", chat_history=history)
    assert "cancelled and removed your staged booking draft" in reply_cancel.lower()
    assert len(get_staged_drafts()) == 0

    # Step D: Availability inquiry with a specific slot on a future Friday
    # followed by comma-separated intake ("reema dahal,98413245678,bandra,checkup") stages a real draft
    q_iyer = f"is dr iyer free on {future_fri_label} 9am-10am?"
    r_iyer1 = fallback_answer_query(q_iyer, session_id="reema_sess")
    r_iyer2 = fallback_answer_query(
        "reema dahal,98413245678,bandra,checkup",
        chat_history=[{"role": "user", "content": q_iyer}, {"role": "assistant", "content": r_iyer1}],
        session_id="reema_sess"
    )
    assert "staged appointment draft" in r_iyer2.lower()
    assert len(get_staged_drafts(session_id="reema_sess")) == 1
    assert get_staged_drafts(session_id="reema_sess")[0]["patient_name"] == "Reema Dahal"

    # Step E: Asking for the same time again for another patient stages a second distinct draft
    fallback_answer_query(q_iyer, session_id="reema_sess")
    r_iyer3 = fallback_answer_query(
        "anil kapoor,9820112233,bandra,checkup",
        session_id="reema_sess"
    )
    assert "staged appointment draft" in r_iyer3.lower()
    assert len(get_staged_drafts(session_id="reema_sess")) == 2
    _STAGED_DRAFTS.clear()
    _save_drafts_to_disk()


def test_edge_cases_security_and_correctness(tmp_path, monkeypatch):
    import shutil
    from concurrent.futures import ThreadPoolExecutor
    import calendar_engine
    from calendar_engine import EXCEL_PATH, get_staged_drafts, stage_booking_draft, _STAGED_DRAFTS
    from langchain_agent import fallback_answer_query, _ACTIVE_INTAKE_STATE

    temp_excel = str(tmp_path / "edge_calendar.xlsx")
    shutil.copyfile(EXCEL_PATH, temp_excel)

    future_tue_dt = _next_weekday(1)
    future_tue = future_tue_dt.strftime("%Y-%m-%d")
    future_tue_label = future_tue_dt.strftime("%d-%b-%Y")

    valid_payload = {
        "patient_name": "Mr. Vinod Kulkarni",
        "contact_number": "+91 9012345614",
        "date": future_tue,
        "time_slot": "2:00 PM - 3:00 PM",
        "assigned_staff": "Dr. Priya Nair",
        "staff_role": "Doctor",
        "service_type": "Geriatric consult",
        "address_area": "Ghatkopar"
    }

    # 1. Unauthenticated / Unauthorized coordinator label rejected at write boundary
    with pytest.raises(ValueError, match="CRITICAL SECURITY ERROR"):
        write_booking(valid_payload, approved_by="Unverified_Caller", excel_path=temp_excel)

    # 2. Missing schedule fields rejected instead of silently skipping Excel write & returning success
    with pytest.raises(ValueError, match="MISSING SCHEDULE FIELDS"):
        write_booking({"patient_name": "Incomplete Patient"}, approved_by="Coordinator_Prashna", excel_path=temp_excel)

    # 3. Missing Excel workbook raises FileNotFoundError instead of reporting fake success
    with pytest.raises(FileNotFoundError, match="not found"):
        write_booking(valid_payload, approved_by="Coordinator_Prashna", excel_path=str(tmp_path / "nonexistent.xlsx"))

    # 4. Ambiguous staff name ("Nurse" or "Dr.") raises ValueError instead of picking first row (.iloc[0])
    with pytest.raises(ValueError, match="AMBIGUOUS STAFF IDENTIFIER"):
        check_conflict(staff_id="Nurse", slot="10:00 AM - 11:00 AM", date="2026-09-24", excel_path=temp_excel)

    # 5. Failed draft persistence raises IOError instead of silently ignoring disk failure
    bad_draft_path = str(tmp_path / "nonexistent_dir_xyz" / "sub" / "\0invalid.json")
    monkeypatch.setattr(calendar_engine, "STAGED_DRAFTS_PATH", bad_draft_path)
    with pytest.raises(IOError, match="DRAFT PERSISTENCE ERROR"):
        stage_booking_draft(valid_payload, persist_draft=True)
    monkeypatch.undo()

    # 6. Emergency clinical escalation route intercepts medical emergencies immediately
    emerg_reply = ask_agent("My father has severe chest pain and difficulty breathing right now")
    assert "URGENT MEDICAL ESCALATION" in emerg_reply
    assert "108" in emerg_reply or "112" in emerg_reply

    # 7. Explicit session state tracking (independent of assistant message copy & isolated per session)
    _STAGED_DRAFTS.clear()
    _ACTIVE_INTAKE_STATE.clear()
    fallback_answer_query(f"Can I book Dr. Priya Nair on {future_tue_label} from 2:00 PM to 3:00 PM?", session_id="patient_A")
    assert "patient_A" in _ACTIVE_INTAKE_STATE
    assert "patient_B" not in _ACTIVE_INTAKE_STATE

    # Even with empty chat_history (no prior assistant text), explicit state completes patient_A's booking
    reply_a = fallback_answer_query(
        "Rahul Sharma, 9876543210, Ghatkopar, Geriatric consult",
        chat_history=[],
        session_id="patient_A"
    )
    assert "prepared your appointment draft" in reply_a.lower()
    assert len(get_staged_drafts(session_id="patient_A")) == 1
    assert len(get_staged_drafts(session_id="patient_B")) == 0
    _STAGED_DRAFTS.clear()

    # 8. Concurrent write_booking calls: exactly 1 succeeds and 1 fails with CONFLICT ERROR
    def attempt_write(_):
        return write_booking(valid_payload, approved_by="Coordinator_Prashna", excel_path=temp_excel)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(attempt_write, i) for i in range(2)]
        outcomes = []
        for f in futures:
            try:
                outcomes.append(("ok", f.result()))
            except Exception as exc:
                outcomes.append(("err", str(exc)))

    successes = [o for o in outcomes if o[0] == "ok"]
    errors = [o for o in outcomes if o[0] == "err" and "CONFLICT ERROR" in o[1]]
    assert len(successes) == 1
    assert len(errors) == 1

# ==========================================
# 6. LANGCHAIN & CONVERSATIONAL TESTS
# ==========================================

def test_core_tools_registered():
    assert len(CORE_TOOLS) == 4
    tool_names = [getattr(t, "name", getattr(t, "__name__", str(t))) for t in CORE_TOOLS]
    assert "read_availability_tool" in tool_names
    assert "check_conflict_tool" in tool_names
    assert "propose_slot_tool" in tool_names
    assert "write_booking_tool" in tool_names

    # Week 6 HITL safety: autonomous LLM tool list must never include write_booking_tool
    ro_names = [getattr(t, "name", getattr(t, "__name__", str(t))) for t in AGENT_READ_ONLY_TOOLS]
    assert len(AGENT_READ_ONLY_TOOLS) == 3
    assert "write_booking_tool" not in ro_names
    assert "NEVER finalize" in SYSTEM_PROMPT

def test_conversational_queries():
    # 1. Ask about Dr. Iyer on working day (Monday 2026-09-28)
    ans1 = ask_agent("Is Dr. Iyer free on 2026-09-28?")
    assert "available" in ans1.lower() or "free" in ans1.lower()
    assert "Dr. Ramesh Iyer" in ans1 or "DR-01" in ans1 or "Iyer" in ans1
    
    # 2. Ask about Dr. Priya Nair on Wednesday 2026-09-23 (her Off day) -> should offer alternative Dr. Ramesh Iyer
    ans2 = ask_agent("Is Dr. Priya Nair free on 2026-09-23?")
    assert "not available" in ans2.lower() or "off" in ans2.lower()
    assert "Dr. Ramesh Iyer" in ans2 or "alternative" in ans2.lower()

    # 3. Ask about Dr. Iyer on Sunday 2026-09-27 (Off day for all doctors)
    ans3 = ask_agent("Is Dr. Iyer free on 2026-09-27?")
    assert "not available" in ans3.lower() or "off" in ans3.lower()

    # 4. Future Tuesday booking query
    future_tue_label = _next_weekday(1).strftime("%d-%b-%Y")
    ans4 = ask_agent(f"Can I book Dr. Priya Nair on Tuesday, {future_tue_label}, from 3:00 PM to 4:00 PM?")
    assert "unable to see" not in ans4.lower()
    assert "priya" in ans4.lower() or "slot" in ans4.lower() or "available" in ans4.lower()

    # 5. User screenshot query 2: Wednesday 14-Oct-2026
    ans5 = ask_agent("Is Dr. Ramesh Iyer free on Wednesday, 14-Oct-2026, from 11:00 AM to 12:00 PM?")
    assert "unable to see" not in ans5.lower()
    assert "iyer" in ans5.lower() or "available" in ans5.lower() or "slot" in ans5.lower()

    # 6. User screenshot query 3: Non-existent staff member (Dr. John Doe)
    ans6 = ask_agent("Is Dr. John Doe available on Thursday, 15-Oct-2026?")
    assert any(p in ans6.lower() for p in ["doesn't exist", "does not exist", "isn't in our system", "not in our system", "in our system"])
    assert "dr. ramesh iyer" in ans6.lower() or "dr. priya nair" in ans6.lower()

def test_conversational_with_chat_history():
    history = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Welcome to Saathi Sneha Care! How can I help?"}
    ]
    ans = ask_agent("Is Dr. Iyer free on 2026-09-28?", chat_history=history)
    assert "available" in ans.lower() or "free" in ans.lower()

# ==========================================
# 7. WEEK 3 MILESTONE: 2-3 SLOT PROPOSAL TESTS
# ==========================================

def test_week3_slot_suggestion_engine():
    """Week 3 Requirement: Agent suggests 2-3 good time slots for a request, not just yes/no."""
    # 1. Doctor slot proposals on Thursday 2026-10-15
    res_doc = suggest_slots_for_request(role="Doctor", date_val="2026-10-15")
    assert res_doc["milestone"] == "Week 3"
    assert res_doc["total_available"] >= 1
    for cand in res_doc["candidates"]:
        assert "proposed_slots" in cand
        assert 1 <= len(cand["proposed_slots"]) <= 3

    # 2. Nurse slot proposals on Thursday 2026-09-24
    res_nurse = suggest_slots_for_request(role="Nurse", date_val="2026-09-24")
    assert res_nurse["total_available"] >= 1
    for cand in res_nurse["candidates"]:
        assert "proposed_slots" in cand
        assert 1 <= len(cand["proposed_slots"]) <= 3


def test_relative_dates_and_past_date_guard(tmp_path):
    import shutil
    from calendar_engine import EXCEL_PATH, stage_booking_draft, get_staged_drafts, _STAGED_DRAFTS, _save_drafts_to_disk
    from langchain_agent import fallback_answer_query

    today = date.today()
    yesterday = today - timedelta(days=1)
    tomorrow = today + timedelta(days=1)
    day_after = today + timedelta(days=2)

    # 1. Relative date parsing in both extract_date_from_query and parse_date
    assert extract_date_from_query("what doctors are available for visit today?") == today.strftime("%Y-%m-%d")
    assert extract_date_from_query("Is any nurse free tomorrow?") == tomorrow.strftime("%Y-%m-%d")
    assert extract_date_from_query("Can I book a doctor day after tomorrow?") == day_after.strftime("%Y-%m-%d")
    assert extract_date_from_query("Book Dr. Priya Nair yesterday") == yesterday.strftime("%Y-%m-%d")
    assert parse_date("today") == today
    assert parse_date("tomorrow") == tomorrow
    assert parse_date("yesterday") == yesterday

    # 2. Natural conversational query with 'today'
    today_reply = fallback_answer_query("what doctors are available for visit today?")
    assert today.strftime("%B %d, %Y") in today_reply or "available" in today_reply.lower()

    # 3. Past dates cannot be finalized in write_booking or staged in stage_booking_draft
    temp_excel = str(tmp_path / "past_date_calendar.xlsx")
    shutil.copyfile(EXCEL_PATH, temp_excel)
    past_payload = {
        "patient_name": "Test Patient",
        "contact_number": "+91 9876543210",
        "date": yesterday.strftime("%Y-%m-%d"),
        "time_slot": "2:00 PM - 3:00 PM",
        "assigned_staff": "Dr. Priya Nair",
        "staff_role": "Doctor",
        "service_type": "Geriatric consult",
        "address_area": "Ghatkopar"
    }
    with pytest.raises(ValueError, match="PAST DATE ERROR"):
        write_booking(past_payload, approved_by="Coordinator_Prashna", excel_path=temp_excel)
    with pytest.raises(ValueError, match="PAST DATE ERROR"):
        stage_booking_draft(past_payload)

    # 4. Conversational booking request for yesterday / past date is rejected cleanly
    _STAGED_DRAFTS.clear()
    _save_drafts_to_disk()
    past_reply = ask_agent(f"Can I book Dr. Priya Nair on {yesterday.strftime('%d %B %Y')} from 2:00 PM to 3:00 PM?")
    assert "outside our booking range" in past_reply.lower()
    assert len(get_staged_drafts()) == 0


def test_auto_cancel_conflicting_drafts_on_approval(tmp_path):
    import shutil
    from calendar_engine import EXCEL_PATH, stage_booking_draft, get_staged_drafts, _STAGED_DRAFTS, _save_drafts_to_disk

    temp_excel = str(tmp_path / "conflict_cancel_calendar.xlsx")
    shutil.copyfile(EXCEL_PATH, temp_excel)
    future_tue = _next_weekday(1).strftime("%Y-%m-%d")

    _STAGED_DRAFTS.clear()
    _save_drafts_to_disk()

    # Stage 2 overlapping drafts for Dr. Priya Nair (2:00 PM - 3:00 PM) and 1 non-overlapping draft (4:00 PM - 5:00 PM)
    d1 = stage_booking_draft({
        "patient_name": "Patient One",
        "contact_number": "+91 9876543210",
        "date": future_tue,
        "time_slot": "2:00 PM - 3:00 PM",
        "assigned_staff": "Dr. Priya Nair",
        "staff_role": "Doctor",
        "service_type": "Geriatric consult",
        "address_area": "Ghatkopar",
        "session_id": "sess_1"
    })
    d2 = stage_booking_draft({
        "patient_name": "Patient Two",
        "contact_number": "+91 9820112233",
        "date": future_tue,
        "time_slot": "2:00 PM - 3:00 PM",
        "assigned_staff": "Dr. Priya Nair",
        "staff_role": "Doctor",
        "service_type": "Geriatric consult",
        "address_area": "Powai",
        "session_id": "sess_2"
    })
    d3 = stage_booking_draft({
        "patient_name": "Patient Three",
        "contact_number": "+91 9811112222",
        "date": future_tue,
        "time_slot": "4:00 PM - 5:00 PM",
        "assigned_staff": "Dr. Priya Nair",
        "staff_role": "Doctor",
        "service_type": "Geriatric consult",
        "address_area": "Bandra",
        "session_id": "sess_3"
    })
    assert len(get_staged_drafts()) == 3

    # Approve d1 using Staff ID ("DR-02") to also verify canonical staff matching
    approve_payload = dict(d1)
    approve_payload["assigned_staff"] = "DR-02"
    res = write_booking(approve_payload, approved_by="Coordinator_Prashna", excel_path=temp_excel)

    # d2 must be auto-cancelled immediately; d3 (different slot) must remain staged
    cancelled_ids = [c["draft_id"] for c in res["auto_cancelled_drafts"]]
    assert cancelled_ids == [d2["draft_id"]]
    assert res["auto_cancelled_drafts"][0]["status"] == "Cancelled"
    remaining_ids = [d["draft_id"] for d in get_staged_drafts()]
    assert remaining_ids == [d3["draft_id"]]

    _STAGED_DRAFTS.clear()
    _save_drafts_to_disk()


def test_manual_sheet_edits_and_auth(tmp_path):
    import shutil
    import pandas as pd
    from calendar_engine import EXCEL_PATH, save_sheet_edits, load_sheet

    temp_excel = str(tmp_path / "manual_edit_calendar.xlsx")
    shutil.copyfile(EXCEL_PATH, temp_excel)

    bookings_df = load_sheet("Bookings Calendar", excel_path=temp_excel)
    initial_count = len(bookings_df)

    # Unauthorized coordinator cannot save manual edits
    with pytest.raises(ValueError, match="CRITICAL SECURITY ERROR"):
        save_sheet_edits("Bookings Calendar", bookings_df, approved_by="Random_User", excel_path=temp_excel)

    # Staff Availability is strictly read-only and can never be modified even by an authorized coordinator
    staff_df = load_sheet("Staff Availability", excel_path=temp_excel)
    with pytest.raises(ValueError, match="READ-ONLY SHEET ERROR"):
        save_sheet_edits("Staff Availability", staff_df, approved_by="Coordinator_Prashna", excel_path=temp_excel)

    # Authorized coordinator edits an existing row and appends a new row
    new_row = {
        "Booking ID": "BK-999",
        "Date": _next_weekday(1).strftime("%Y-%m-%d"),
        "Time Slot": "4:00 PM - 5:00 PM",
        "Patient Name": "Manual Entry Patient",
        "Service Type": "Home visit",
        "Assigned Staff": "Dr. Priya Nair",
        "Staff Role": "Doctor",
        "Status": "Pending",
        "Contact Number": "+91 9876500000",
        "Address / Area": "Powai",
        "Notes": "Edited by hand"
    }
    edited_df = pd.concat([bookings_df, pd.DataFrame([new_row])], ignore_index=True)
    saved_count = save_sheet_edits("Bookings Calendar", edited_df, approved_by="Coordinator_Prashna", excel_path=temp_excel)
    assert saved_count == initial_count + 1

    reloaded = load_sheet("Bookings Calendar", excel_path=temp_excel)
    assert len(reloaded) == initial_count + 1
    assert "BK-999" in reloaded["Booking ID"].values


def test_review_bug_fixes(tmp_path):
    import shutil
    import openpyxl
    from calendar_engine import EXCEL_PATH, STAGED_DRAFTS_PATH

    # Bug #1: Single-time entries like "11am" (BK-111) are parsed as 1-hour slots & detected as conflicts
    assert parse_time_range("11am") == (time(11, 0), time(12, 0))
    assert times_overlap("11am", "11:00 AM - 12:00 PM") is True
    assert check_conflict(staff_id="DR-01", slot="11:00 AM - 12:00 PM", date="2026-09-24") is True

    # Bug #2: Same-day past time slots are excluded when min_start_time is provided
    windows = get_available_windows("9:00 AM - 5:00 PM", [], min_start_time=time(14, 0))
    assert "9:00 AM - 10:00 AM" not in windows
    assert "1:00 PM - 2:00 PM" not in windows
    assert "2:00 PM - 3:00 PM" in windows

    # Bug #3: Paths are anchored to absolute paths (independent of current working directory)
    assert os.path.isabs(EXCEL_PATH)
    assert os.path.isabs(STAGED_DRAFTS_PATH)

    # Bug #4: write_booking sets clean Excel date number_format matching existing rows
    temp_excel = str(tmp_path / "fmt_calendar.xlsx")
    shutil.copyfile(EXCEL_PATH, temp_excel)
    future_tue = _next_weekday(1).strftime("%Y-%m-%d")
    res = write_booking({
        "patient_name": "Format Check",
        "contact_number": "+91 9876543210",
        "date": future_tue,
        "time_slot": "2:00 PM - 3:00 PM",
        "assigned_staff": "Dr. Priya Nair",
        "staff_role": "Doctor",
        "service_type": "Geriatric consult",
        "address_area": "Ghatkopar"
    }, approved_by="Coordinator_Prashna", excel_path=temp_excel)
    wb = openpyxl.load_workbook(temp_excel)
    try:
        ws = wb["Bookings Calendar"]
        matched_fmt = None
        for r in range(6, ws.max_row + 1):
            if ws.cell(r, 1).value == res["booking_id"]:
                matched_fmt = ws.cell(r, 2).number_format
                break
        assert matched_fmt == 'ddd", "dd-mmm-yyyy'
    finally:
        wb.close()
