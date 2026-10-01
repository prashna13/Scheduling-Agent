"""
Interactive test script for Saathi Sneha Care Scheduling Sub-Agent.
Run this script to test doctor availability and booking conflict checks interactively.
"""

import sys
import json
from calendar_engine import (
    is_doctor_available,
    read_availability,
    propose_slot,
    check_conflict,
    write_booking
)

def print_banner():
    print("=" * 60)
    print(" SAATHI SNEHA CARE - SCHEDULING AGENT INTERACTIVE TESTER")
    print("=" * 60)
    print("Options:")
    print(" 1. Check if a Doctor/Staff is available on a specific Date & Slot")
    print(" 2. Propose available slots for a Role, Specialty, Date & Area")
    print(" 3. View all available staff for a Date & Role")
    print(" 4. Commit a new booking to Excel Calendar (HITL Approved)")
    print(" 5. Run sample preset tests")
    print(" 6. Exit")
    print("=" * 60)

def ask_check_availability():
    print("\n--- Check Doctor/Staff Availability ---")
    doc_name = input("Enter Doctor/Staff Name or ID (e.g. 'Dr. Ramesh Iyer' or 'DR-01'): ").strip()
    if not doc_name:
        print("❌ Doctor name cannot be empty.")
        return
        
    date_val = input("Enter Date (YYYY-MM-DD, e.g. '2026-09-28'): ").strip()
    if not date_val:
        print("❌ Date cannot be empty.")
        return
        
    slot_val = input("Enter Time Slot (optional, e.g. '10:00 AM - 11:00 AM' or press Enter to skip): ").strip()
    if not slot_val:
        slot_val = None
        
    print("\n🔍 Querying Database...")
    result = is_doctor_available(doctor_name_or_id=doc_name, date_val=date_val, slot_str=slot_val)
    
    print("\n📋 RESULT:")
    print(json.dumps(result, indent=2))
    
    if result["available"]:
        print(f"\n✅ SUCCESS: {result['name']} IS AVAILABLE!")
    else:
        print(f"\n❌ NOT AVAILABLE: {result.get('reason')}")

def ask_propose_slots():
    print("\n--- Propose Slots for Patient Request ---")
    role = input("Role (Doctor / Nurse) [default: Doctor]: ").strip() or "Doctor"
    specialty = input("Specialty (optional, e.g. 'General physician'): ").strip()
    date_val = input("Date (YYYY-MM-DD, e.g. '2026-09-28'): ").strip()
    area = input("Area / Locality (e.g. 'Andheri'): ").strip()
    slot_val = input("Specific Time Slot (optional, e.g. '10:00 AM - 11:00 AM' or Enter to view all open slots): ").strip() or None
    
    print("\n🔍 Searching for candidates...")
    candidates = propose_slot(role=role, specialty=specialty, date=date_val, area=area, slot=slot_val)
    
    print(f"\n📋 FOUND {len(candidates)} CANDIDATE(S):")
    print(json.dumps(candidates, indent=2))

def ask_read_availability():
    print("\n--- View All Available Staff for Date & Role ---")
    date_val = input("Date (YYYY-MM-DD, e.g. '2026-09-28'): ").strip()
    role = input("Role (Doctor / Nurse) [default: Doctor]: ").strip() or "Doctor"
    
    results = read_availability(date_range=date_val, role=role)
    print(f"\n📋 {len(results)} Staff Member(s) working on {date_val}:")
    print(json.dumps(results, indent=2))

def ask_write_booking():
    print("\n--- Commit New Booking to Excel (HITL Protected) ---")
    approved_by = input("Enter Coordinator ID / Name for Human Approval: ").strip()
    if not approved_by:
        print("❌ Write halted: approved_by cannot be empty.")
        return
        
    patient = input("Patient Name: ").strip()
    date_val = input("Date (YYYY-MM-DD): ").strip()
    slot = input("Time Slot (e.g. '10:00 AM - 11:00 AM'): ").strip()
    staff = input("Assigned Staff (e.g. 'Dr. Ramesh Iyer'): ").strip()
    role = input("Staff Role (Doctor / Nurse): ").strip()
    service = input("Service Type (e.g. 'General checkup'): ").strip()
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
        print("\n✅ SUCCESS:")
        print(json.dumps(res, indent=2))
    except Exception as e:
        print(f"\n❌ ERROR: {e}")

def run_preset_tests():
    print("\n--- Running Preset Tests ---")
    samples = [
        ("Dr. Ramesh Iyer", "2026-09-28", "10:00 AM - 11:00 AM"),
        ("Dr. Ramesh Iyer", "2026-09-27", None),
        ("Dr. Priya Nair", "2026-09-22", "3:00 PM - 4:00 PM"),
        ("Dr. Priya Nair", "2026-09-22", "4:00 PM - 5:00 PM"),
        ("Nurse Sunita Rao", "2026-09-24", "9:00 AM - 10:00 AM")
    ]
    for doc, dt, sl in samples:
        print(f"\n Testing: {doc} on {dt} (Slot: {sl or 'Any'})")
        res = is_doctor_available(doc, dt, sl)
        status = "✅ AVAILABLE" if res["available"] else " CONFLICT/OFF"
        print(f"   Status: {status} | Reason: {res.get('reason')}")

def main():
    while True:
        print_banner()
        choice = input("Select an option (1-6): ").strip()
        if choice == "1":
            ask_check_availability()
        elif choice == "2":
            ask_propose_slots()
        elif choice == "3":
            ask_read_availability()
        elif choice == "4":
            ask_write_booking()
        elif choice == "5":
            run_preset_tests()
        elif choice == "6":
            print("\nExiting tester. Good luck with your internship! 👋")
            break
        else:
            print("\n❌ Invalid choice. Please select 1-6.")
        input("\nPress Enter to continue...")

if __name__ == "__main__":
    main()
