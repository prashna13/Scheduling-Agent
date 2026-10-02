"""
Interactive test script for Saathi Sneha Care Scheduling Sub-Agent (Week 2).
Uses strictly the 4 core calendar tools:
1. read_availability
2. check_conflict
3. propose_slot
4. write_booking
"""

import sys
import json
from calendar_engine import (
    read_availability,
    check_conflict,
    propose_slot,
    write_booking,
    load_sheet
)
from langchain_agent import ask_agent

def print_banner():
    print("=" * 65)
    print(" SAATHI SNEHA CARE - SCHEDULING AGENT TESTER (WEEK 2)")
    print("=" * 65)
    print("Options:")
    print(" 1. Tool 1: Find Available Staff on a Date (read_availability)")
    print(" 2. Tool 2: Check Time Slot Conflict (check_conflict)")
    print(" 3. Tool 3: Propose 2-3 Slots & Candidates (propose_slot)")
    print(" 4. Tool 4: Stage Booking with HITL Approval (write_booking)")
    print(" 5. View Master Schedule Sheets (Staff Availability & Bookings)")
    print(" 6. Ask Conversational Agent (Natural Language / Social Media)")
    print(" 7. Run Preset Test Scenarios")
    print(" 8. Exit")
    print("=" * 65)

def ask_tool_1_read_availability():
    print("\n--- Tool 1: read_availability ---")
    date_val = input("Enter Date (YYYY-MM-DD, e.g. '2026-09-24'): ").strip()
    if not date_val:
        print("Date cannot be empty.")
        return
    role = input("Role (Nurse / Doctor) [default: Nurse]: ").strip() or "Nurse"
    
    results = read_availability(date_range=date_val, role=role)
    print(f"\n Found {len(results)} {role}(s) working on {date_val}:")
    print(json.dumps(results, indent=2))

def ask_tool_2_check_conflict():
    print("\n--- Tool 2: check_conflict ---")
    staff_id = input("Enter Staff ID or Name (e.g. 'NR-02' or 'Nurse Sunita Rao'): ").strip()
    if not staff_id:
        print("Staff identifier cannot be empty.")
        return
    date_val = input("Enter Date (YYYY-MM-DD, e.g. '2026-09-21'): ").strip()
    if not date_val:
        print("Date cannot be empty.")
        return
    slot_val = input("Enter Time Slot (e.g. '10:30 AM - 11:30 AM'): ").strip()
    if not slot_val:
        print("Slot cannot be empty.")
        return
        
    has_conflict = check_conflict(staff_id=staff_id, slot=slot_val, date=date_val)
    print(f"\n Conflict Result: {has_conflict}")
    if has_conflict:
        print(f" NOT AVAILABLE: Conflict detected or staff is off for slot {slot_val} on {date_val}.")
    else:
        print(f" AVAILABLE: No conflict found for {staff_id} during {slot_val} on {date_val}.")

def ask_tool_3_propose_slot():
    print("\n--- Tool 3: propose_slot ---")
    role = input("Role (Nurse / Doctor) [default: Nurse]: ").strip() or "Nurse"
    specialty = input("Specialty (optional, e.g. 'Elderly / palliative care'): ").strip() or None
    date_val = input("Date (YYYY-MM-DD, e.g. '2026-09-24'): ").strip()
    area = input("Area / Locality (optional, e.g. 'Bandra'): ").strip() or None
    slot_val = input("Specific Time Slot (optional, e.g. '10:00 AM - 11:00 AM' or Enter for open slots): ").strip() or None
    
    candidates = propose_slot(role=role, specialty=specialty, date=date_val, area=area, slot=slot_val)
    print(f"\n Found {len(candidates)} Candidate(s) with proposed 2-3 slots:")
    print(json.dumps(candidates, indent=2))

def ask_tool_4_write_booking():
    print("\n--- Tool 4: write_booking (HITL Validation Gate) ---")
    approved_by = input("Enter Coordinator ID for Human Approval: ").strip()
    if not approved_by:
        print("Write halted: approved_by coordinator ID is required.")
        return
        
    patient = input("Patient Name: ").strip()
    date_val = input("Date (YYYY-MM-DD): ").strip()
    slot = input("Time Slot (e.g. '10:00 AM - 11:00 AM'): ").strip()
    staff = input("Assigned Staff (e.g. 'Nurse Sunita Rao'): ").strip()
    role = input("Staff Role (Nurse / Doctor): ").strip() or "Nurse"
    service = input("Service Type (e.g. 'Wound care'): ").strip()
    contact = input("Contact Number: ").strip()
    area = input("Address / Area: ").strip()
    notes = input("Notes: ").strip()
    
    payload = {
        "Date": date_val,
        "Time Slot": slot,
        "Patient Name": patient,
        "Service Type": service,
        "Assigned Staff": staff,
        "Staff Role": role,
        "Status": "Confirmed",
        "Contact Number": contact,
        "Address / Area": area,
        "Notes": notes
    }
    
    try:
        res = write_booking(payload, approved_by=approved_by)
        print("\n SUCCESS:")
        print(json.dumps(res, indent=2))
    except Exception as e:
        print(f"\n ERROR: {e}")

def view_master_sheets():
    print("\n--- Master Sheet: Staff Availability ---")
    print(load_sheet("Staff Availability").to_string(index=False))
    print("\n--- Master Sheet: Bookings Calendar ---")
    print(load_sheet("Bookings Calendar").to_string(index=False))

def ask_nl_agent():
    print("\n--- Conversational Scheduling Agent (Social Media / WhatsApp) ---")
    q = input("Ask a question (e.g. 'Is Dr. Iyer free on 2026-09-28?'): ").strip()
    if not q:
        return
    print("\nAgent Response:")
    print(ask_agent(q))

def run_preset_tests():
    print("\n--- Running Week 2 Preset Tests ---")
    samples = [
        "Is Nurse Sunita Rao free on 2026-09-24?",
        "Is Nurse Sunita Rao free on 2026-09-21 between 10:30 AM and 11:30 AM?",
        "Is a nurse free on 2026-09-24?",
        "Is Nurse Meera Joshi free on 2026-09-27?",
        "Is Dr. Ramesh Iyer available on 2026-09-28?",
        "Is Dr. Priya Nair free on 2026-09-27?"
    ]
    for q in samples:
        print(f"\n Query: {q}")
        ans = ask_agent(q)
        print(f"Response:\n{ans}")
        print("-" * 50)

def main():
    while True:
        print_banner()
        choice = input("Select an option (1-8): ").strip()
        if choice == "1":
            ask_tool_1_read_availability()
        elif choice == "2":
            ask_tool_2_check_conflict()
        elif choice == "3":
            ask_tool_3_propose_slot()
        elif choice == "4":
            ask_tool_4_write_booking()
        elif choice == "5":
            view_master_sheets()
        elif choice == "6":
            ask_nl_agent()
        elif choice == "7":
            run_preset_tests()
        elif choice == "8":
            print("\nExiting tester. Week 2 Scheduling Agent ready.")
            break
        else:
            print("\nInvalid choice. Please select 1-8.")
        input("\nPress Enter to continue...")

if __name__ == "__main__":
    main()
