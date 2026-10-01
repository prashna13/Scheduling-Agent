import os
import shutil
import pytest
from datetime import date, time
import pandas as pd
from calendar_engine import (
    is_doctor_available,
    read_availability,
    check_conflict,
    write_booking,
    propose_slot,
    parse_date,
    parse_time_range,
    times_overlap,
    is_time_within_window,
    generate_next_booking_id
)
from langchain_agent import (
    ask_agent,
    check_doctor_availability_tool,
    read_staff_availability_tool,
    propose_available_slots_tool
)

def test_parse_date():
    assert parse_date("2026-09-28") == date(2026, 9, 28)
    assert parse_date("2026/09/28") == date(2026, 9, 28)
    assert parse_date("September 28, 2026") == date(2026, 9, 28)

def test_robust_time_parsing():
    r1 = parse_time_range("9:00 AM - 1:00 PM")
    assert r1 == (time(9, 0), time(13, 0))
    
    r2 = parse_time_range("9:00am-1:00pm")
    assert r2 == (time(9, 0), time(13, 0))
    
    r3 = parse_time_range("9:30 AM – 11:30 AM")
    assert r3 == (time(9, 30), time(11, 30))
    
    r4 = parse_time_range("10am to 2pm")
    assert r4 == (time(10, 0), time(14, 0))

def test_times_overlap():
    assert times_overlap("9:00 AM - 10:00 AM", "9:30 AM - 10:30 AM") is True
    assert times_overlap("9:00 AM - 10:00 AM", "10:00 AM - 11:00 AM") is False
    assert times_overlap("9:00am-10:00am", "9:30am-10:30am") is True

def test_is_time_within_window():
    assert is_time_within_window("9:00 AM - 10:00 AM", "9:00 AM - 1:00 PM") is True
    assert is_time_within_window("8:00 AM - 10:00 AM", "9:00 AM - 1:00 PM") is False

def test_doctor_off_day():
    res = is_doctor_available("Dr. Ramesh Iyer", "2026-09-27")
    assert res["available"] is False
    assert "marked 'Off'" in res["reason"] or res.get("working_hours") == "Off"

def test_doctor_available_day():
    res = is_doctor_available("Dr. Ramesh Iyer", "2026-09-28", "10:00 AM - 11:00 AM")
    assert res["available"] is True
    assert res["working_hours"] == "9:00 AM - 1:00 PM"

def test_propose_slot_not_disqualifying_partially_booked_staff():
    candidates = propose_slot(
        role="Doctor",
        specialty="Geriatric care",
        date="2026-09-22",
        area="Powai",
        slot="4:00 PM - 5:00 PM"
    )
    assert len(candidates) > 0
    assert candidates[0]["staff_id"] == "DR-02"

    general_cands = propose_slot(
        role="Doctor",
        date="2026-09-22",
        area="Powai"
    )
    assert len(general_cands) > 0
    dr_priya = next((c for c in general_cands if c["staff_id"] == "DR-02"), None)
    assert dr_priya is not None
    assert "available_slots" in dr_priya
    assert "2:00 PM - 3:00 PM" in dr_priya["available_slots"]
    assert "3:00 PM - 4:00 PM" not in dr_priya["available_slots"]
    assert "4:00 PM - 5:00 PM" in dr_priya["available_slots"]

def test_column_safety_in_read_availability():
    res = read_availability(role="Doctor")
    assert isinstance(res, list)
    for staff in res:
        assert "staff_id" in staff
        assert "specialty" in staff
        assert "service_area" in staff
        assert "notes" in staff

def test_excel_persistence_write_booking(tmp_path):
    src_excel = os.path.join("data", "Saathi_Sneha_Care_Scheduling_Calendar_Mockup.xlsx")
    test_excel = os.path.join(tmp_path, "test_calendar.xlsx")
    shutil.copyfile(src_excel, test_excel)
    
    with pytest.raises(ValueError, match="CRITICAL SECURITY ERROR"):
        write_booking({"patient": "Test"}, approved_by="", excel_path=test_excel)
        
    next_id = generate_next_booking_id(excel_path=test_excel)
    assert next_id.startswith("BK-")
    
    booking_payload = {
        "Date": "2026-09-29",
        "Time Slot": "10:00 AM - 11:00 AM",
        "Patient Name": "Test Patient",
        "Service Type": "General checkup",
        "Assigned Staff": "Dr. Ramesh Iyer",
        "Staff Role": "Doctor",
        "Status": "Confirmed",
        "Contact Number": "+91 9999999999",
        "Address / Area": "Andheri",
        "Notes": "Scheduled via unit test"
    }
    
    write_res = write_booking(booking_payload, approved_by="Coordinator_Test", excel_path=test_excel)
    assert write_res["status"] == "success"
    assert write_res["booking_id"] == next_id
    
    df_check = pd.read_excel(test_excel, sheet_name="Bookings Calendar", header=4)
    written_row = df_check[df_check["Booking ID"] == next_id]
    assert not written_row.empty
    assert written_row.iloc[0]["Patient Name"] == "Test Patient"
    assert written_row.iloc[0]["Assigned Staff"] == "Dr. Ramesh Iyer"

def test_langchain_agent_queries():
    # Test availability queries handled by the agent
    ans1 = ask_agent("Is Dr. Ramesh Iyer available on 2026-09-28?")
    assert "AVAILABLE" in ans1 or "available" in ans1.lower()
    assert "Dr. Ramesh Iyer" in ans1 or "DR-01" in ans1
    
    ans2 = ask_agent("Is Dr. Ramesh Iyer available on 2026-09-27?")
    assert "NOT AVAILABLE" in ans2 or "off" in ans2.lower()

    ans3 = ask_agent("Is Dr. Priya Nair available on 2026-09-22 from 3:00 PM to 4:00 PM?")
    assert "NOT AVAILABLE" in ans3 or "conflict" in ans3.lower()
