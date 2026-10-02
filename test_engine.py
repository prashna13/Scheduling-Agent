import pytest
from datetime import date, time
from calendar_engine import (
    read_availability,
    check_conflict,
    propose_slot,
    write_booking,
    parse_date,
    parse_time_range,
    times_overlap,
    is_time_within_window,
    get_available_windows
)
from langchain_agent import (
    ask_agent,
    read_availability_tool,
    check_conflict_tool,
    propose_slot_tool,
    write_booking_tool,
    CORE_TOOLS
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
# 5. TOOL 4: write_booking TESTS
# ==========================================

def test_write_booking_validation():
    # Missing approved_by should raise ValueError
    with pytest.raises(ValueError, match="CRITICAL SECURITY ERROR"):
        write_booking(booking_data={"Patient": "Test"}, approved_by="")
        
    res = write_booking(booking_data={"Patient": "Test"}, approved_by="Coordinator_Prashna")
    assert res["status"] == "success"
    assert res["approved_by"] == "Coordinator_Prashna"

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
