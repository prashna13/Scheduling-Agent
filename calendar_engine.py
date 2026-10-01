# Week 1: Excel is the source of truth (pandas + openpyxl).
# The tool interfaces above are intentionally stable so this backend
# can later be swapped for a real calendar/DB without changing the agent.
import os
import re
from datetime import datetime, date, time, timedelta
from typing import List, Dict, Any, Optional, Tuple, Union
import pandas as pd
import openpyxl

EXCEL_PATH = os.path.join("data", "Saathi_Sneha_Care_Scheduling_Calendar_Mockup.xlsx")


def load_sheet(sheet_name: str, excel_path: str = EXCEL_PATH) -> pd.DataFrame:
    """
    Safely loads a specified sheet from the Excel mockup.
    Dynamically locates the header row containing key column names.
    """
    if not os.path.exists(excel_path):
        raise FileNotFoundError(f"Database file not found at {excel_path}")
    
    raw_df = pd.read_excel(excel_path, sheet_name=sheet_name, header=None)
    
    header_idx = None
    target_key = "Staff ID" if sheet_name == "Staff Availability" else "Booking ID"
    
    for idx, row in raw_df.iterrows():
        row_values = [str(val).strip() for val in row.values if pd.notna(val)]
        if target_key in row_values:
            header_idx = idx
            break
            
    if header_idx is None:
        header_idx = 4  # Default fallback header row index for mockup
        
    df = pd.read_excel(excel_path, sheet_name=sheet_name, header=header_idx)
    if target_key in df.columns:
        df = df.dropna(subset=[target_key]).copy()
    return df


def parse_date(date_val: Union[str, datetime, date]) -> Optional[date]:
    """Parses various date input types into a standard datetime.date object."""
    if isinstance(date_val, date) and not isinstance(date_val, datetime):
        return date_val
    if isinstance(date_val, datetime):
        return date_val.date()
    if pd.isna(date_val) or not date_val:
        return None
    
    date_str = str(date_val).strip()
    formats = (
        "%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%d/%m/%Y", 
        "%B %d, %Y", "%b %d, %Y", "%Y-%m-%d %H:%M:%S"
    )
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            pass
    try:
        return pd.to_datetime(date_str).date()
    except Exception:
        return None


def parse_single_time(t_str: str) -> Optional[time]:
    """
    Resilient single time string parser.
    Handles '9:00 AM', '9:00am', '9am', '9 AM', '14:00', '2:00 PM', etc.
    """
    if not isinstance(t_str, str) or not t_str.strip():
        return None
    
    s = t_str.strip().upper()
    # Normalize space between digits and AM/PM (e.g., '9:00AM' -> '9:00 AM', '9AM' -> '9 AM')
    s = re.sub(r'(\d+)(AM|PM)', r'\1 \2', s)
    s = re.sub(r'\s+', ' ', s)
    
    formats = [
        "%I:%M %p",
        "%I %p",
        "%H:%M",
        "%H:%M:%S",
        "%I:%M:%S %p"
    ]
    for fmt in formats:
        try:
            return datetime.strptime(s, fmt).time()
        except ValueError:
            pass
    return None


def parse_time_range(time_str: str) -> Optional[Tuple[time, time]]:
    """
    Resilient time range parser.
    Handles '9:00 AM - 1:00 PM', '9:00am–1:00pm', '9:00 AM - 12:00 PM', '10am to 2pm', etc.
    """
    if not isinstance(time_str, str) or not time_str.strip():
        return None
    
    # Normalize separator dashes and 'to'
    normalized = time_str.replace('–', '-').replace('—', '-').replace('–', '-')
    normalized = re.sub(r'\s+to\s+', '-', normalized, flags=re.IGNORECASE)
    
    if '-' not in normalized:
        return None
        
    parts = normalized.split('-', 1)
    t1 = parse_single_time(parts[0])
    t2 = parse_single_time(parts[1])
    
    if t1 and t2:
        return (t1, t2)
    return None


def times_overlap(range1_str: str, range2_str: str) -> bool:
    """Returns True if two time range strings overlap."""
    r1 = parse_time_range(range1_str)
    r2 = parse_time_range(range2_str)
    if not r1 or not r2:
        return False
    return max(r1[0], r2[0]) < min(r1[1], r2[1])


def is_time_within_window(slot_str: str, window_str: str) -> bool:
    """Returns True if slot_str falls completely inside window_str."""
    s = parse_time_range(slot_str)
    w = parse_time_range(window_str)
    if not s or not w:
        return False
    return s[0] >= w[0] and s[1] <= w[1]


def format_time_slot(t1: time, t2: time) -> str:
    """Formats two time objects into standard '9:00 AM - 10:00 AM' string format."""
    s1 = datetime.combine(date.today(), t1).strftime("%I:%M %p").lstrip("0")
    s2 = datetime.combine(date.today(), t2).strftime("%I:%M %p").lstrip("0")
    return f"{s1} - {s2}"


def get_available_windows(working_hours_str: str, booked_slots: List[str], slot_duration_minutes: int = 60) -> List[str]:
    """
    Calculates discrete non-overlapping available time slots during a shift window.
    """
    shift = parse_time_range(working_hours_str)
    if not shift:
        return []
    
    start_dt = datetime.combine(date.today(), shift[0])
    end_dt = datetime.combine(date.today(), shift[1])
    
    curr = start_dt
    available_slots = []
    
    while curr + timedelta(minutes=slot_duration_minutes) <= end_dt:
        slot_end = curr + timedelta(minutes=slot_duration_minutes)
        cand_slot_str = format_time_slot(curr.time(), slot_end.time())
        
        # Check against all booked slots
        conflict = False
        for b_slot in booked_slots:
            if times_overlap(cand_slot_str, b_slot):
                conflict = True
                break
                
        if not conflict:
            available_slots.append(cand_slot_str)
            
        curr += timedelta(minutes=slot_duration_minutes)
        
    return available_slots


def is_doctor_available(
    doctor_name_or_id: str, 
    date_val: Union[str, datetime, date], 
    slot_str: Optional[str] = None
) -> Dict[str, Any]:
    """
    Checks if a specific Doctor/Staff member is available on date_val (and optional slot_str).
    Checks:
    1. Base shift schedule in 'Staff Availability' tab for that weekday.
    2. Active bookings in 'Bookings Calendar' tab for date_val and time slot overlap.
    """
    target_date = parse_date(date_val)
    if not target_date:
        return {
            "available": False,
            "reason": f"Invalid date provided: '{date_val}'"
        }
    
    day_name = target_date.strftime("%a")  # 'Mon', 'Tue', etc.
    
    # 1. Load Staff Availability
    avail_df = load_sheet("Staff Availability")
    
    # Safe string conversion for matching
    staff_id_col = avail_df['Staff ID'].astype(str).str.strip().str.lower() if 'Staff ID' in avail_df.columns else pd.Series([])
    name_col = avail_df['Name'].astype(str).str.strip().str.lower() if 'Name' in avail_df.columns else pd.Series([])
    target_clean = doctor_name_or_id.strip().lower()
    
    matched_staff = avail_df[
        (staff_id_col == target_clean) |
        (name_col == target_clean) |
        (name_col.str.contains(target_clean, regex=False))
    ]
    
    if matched_staff.empty:
        return {
            "available": False,
            "reason": f"Doctor/Staff member '{doctor_name_or_id}' not found in database."
        }
        
    staff_row = matched_staff.iloc[0]
    staff_id = staff_row.get('Staff ID', 'N/A')
    staff_name = staff_row.get('Name', 'N/A')
    
    if day_name not in staff_row:
        return {
            "available": False,
            "reason": f"Column for day '{day_name}' not found in Staff Availability sheet."
        }
        
    day_schedule = str(staff_row[day_name]).strip()
    
    if pd.isna(staff_row[day_name]) or day_schedule.lower() == 'off':
        return {
            "available": False,
            "staff_id": staff_id,
            "name": staff_name,
            "date": str(target_date),
            "day_of_week": day_name,
            "working_hours": "Off",
            "reason": f"{staff_name} ({staff_id}) is marked 'Off' on {day_name} ({target_date})."
        }
        
    # 2. Check slot bounds if slot_str is given
    if slot_str and not is_time_within_window(slot_str, day_schedule):
        return {
            "available": False,
            "staff_id": staff_id,
            "name": staff_name,
            "date": str(target_date),
            "day_of_week": day_name,
            "working_hours": day_schedule,
            "requested_slot": slot_str,
            "reason": f"Requested slot '{slot_str}' is outside working hours '{day_schedule}' on {day_name}."
        }
        
    # 3. Check Bookings Calendar for conflicts on target_date
    bookings_df = load_sheet("Bookings Calendar")
    bookings_df['ParsedDate'] = bookings_df['Date'].apply(parse_date)
    
    assigned_col = bookings_df['Assigned Staff'].astype(str).str.strip().str.lower() if 'Assigned Staff' in bookings_df.columns else pd.Series([])
    status_col = bookings_df['Status'].astype(str).str.strip().str.lower() if 'Status' in bookings_df.columns else pd.Series([])
    
    day_bookings = bookings_df[
        (bookings_df['ParsedDate'] == target_date) &
        (status_col != 'cancelled') &
        (
            (assigned_col == str(staff_name).strip().lower()) |
            (assigned_col == str(staff_id).strip().lower())
        )
    ]
    
    conflicts = []
    booked_slots = []
    for _, booking in day_bookings.iterrows():
        b_slot = str(booking.get('Time Slot', '')).strip()
        b_id = booking.get('Booking ID', 'N/A')
        b_status = booking.get('Status', 'Confirmed')
        booked_slots.append(b_slot)
        
        if slot_str:
            if times_overlap(slot_str, b_slot):
                conflicts.append({
                    "booking_id": b_id,
                    "slot": b_slot,
                    "status": b_status,
                    "patient": booking.get('Patient Name', 'Unknown')
                })
        else:
            conflicts.append({
                "booking_id": b_id,
                "slot": b_slot,
                "status": b_status,
                "patient": booking.get('Patient Name', 'Unknown')
            })
            
    if slot_str and conflicts:
        return {
            "available": False,
            "staff_id": staff_id,
            "name": staff_name,
            "date": str(target_date),
            "day_of_week": day_name,
            "working_hours": day_schedule,
            "requested_slot": slot_str,
            "conflicts": conflicts,
            "reason": f"Conflict detected for {staff_name} on {target_date} with existing booking(s): {conflicts[0]['booking_id']} ({conflicts[0]['slot']})."
        }
    
    open_slots = get_available_windows(day_schedule, booked_slots)
    
    return {
        "available": True,
        "staff_id": staff_id,
        "name": staff_name,
        "date": str(target_date),
        "day_of_week": day_name,
        "working_hours": day_schedule,
        "requested_slot": slot_str,
        "available_slots": open_slots,
        "active_bookings_count": len(day_bookings),
        "reason": f"{staff_name} ({staff_id}) is available on {day_name}, {target_date}."
    }


def read_availability(date_range: Optional[str] = None, role: str = "Doctor") -> List[Dict[str, Any]]:
    """
    Read-only tool. Parses weekday columns and returns available staff windows for role.
    Uses safe dictionary lookups to prevent KeyError crashes on optional columns.
    """
    df = load_sheet("Staff Availability")
    
    if 'Role' in df.columns:
        role_filtered = df[df['Role'].astype(str).str.lower() == role.lower()]
    else:
        role_filtered = df
    
    target_date = parse_date(date_range) if date_range else None
    day_name = target_date.strftime("%a") if target_date else None
    
    available_staff = []
    for _, row in role_filtered.iterrows():
        hours = row.get(day_name, "N/A") if (day_name and day_name in row) else "N/A"
        if day_name and (pd.isna(hours) or str(hours).strip().lower() == 'off'):
            continue
            
        staff_member = {
            "staff_id": row.get('Staff ID', ''),
            "name": row.get('Name', ''),
            "role": row.get('Role', role),
            "specialty": row.get('Specialty', '') if pd.notna(row.get('Specialty')) else '',
            "service_area": row.get('Service Area', '') if pd.notna(row.get('Service Area')) else '',
            "contact_number": row.get('Contact Number', '') if pd.notna(row.get('Contact Number')) else '',
            "notes": row.get('Notes', '') if pd.notna(row.get('Notes')) else '',
            "working_hours": hours if hours != "N/A" else "Available"
        }
        available_staff.append(staff_member)
        
    return available_staff


def check_conflict(staff_id: str, slot: str, date: str) -> bool:
    """
    Read-only tool. Returns True if the slot overlaps an existing active booking for that staff member.
    Excludes Cancelled bookings.
    """
    res = is_doctor_available(doctor_name_or_id=staff_id, date_val=date, slot_str=slot)
    return not res["available"]


def propose_slot(
    role: str = "Doctor", 
    specialty: Optional[str] = None, 
    date: Optional[str] = None, 
    area: Optional[str] = None,
    slot: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Read-only tool. Ranks candidate staff who match role, specialty, date, and area without conflicts.
    Refactored to evaluate specific slot requests or calculate open available time windows,
    ensuring staff members with non-overlapping bookings are not incorrectly disqualified.
    """
    avail_list = read_availability(date_range=date, role=role)
    candidates = []
    
    for staff in avail_list:
        # 1. Filter by specialty if specified
        if specialty and specialty.strip():
            staff_spec = str(staff.get('specialty', '')).strip().lower()
            req_spec = specialty.strip().lower()
            if req_spec not in staff_spec and staff_spec not in req_spec:
                continue
                
        # 2. Filter by service area if specified
        if area and area.strip():
            staff_areas = [a.strip().lower() for a in str(staff.get('service_area', '')).split(',')]
            req_area = area.strip().lower()
            if req_area not in staff_areas and not any(req_area in a for a in staff_areas):
                continue
                
        # 3. Check availability and conflicts on the specified date
        if date:
            avail_check = is_doctor_available(
                doctor_name_or_id=staff['staff_id'], 
                date_val=date, 
                slot_str=slot
            )
            
            if not avail_check["available"]:
                continue
                
            staff_copy = dict(staff)
            staff_copy["date"] = date
            if slot:
                staff_copy["proposed_slot"] = slot
            else:
                staff_copy["available_slots"] = avail_check.get("available_slots", [])
                
            candidates.append(staff_copy)
        else:
            candidates.append(staff)
            
    return candidates


def generate_next_booking_id(excel_path: str = EXCEL_PATH) -> str:
    """Finds the highest BK-XXX booking ID in the Bookings Calendar and returns the next sequential ID."""
    df = load_sheet("Bookings Calendar", excel_path=excel_path)
    max_id = 100
    if 'Booking ID' in df.columns:
        for val in df['Booking ID'].dropna():
            match = re.search(r'BK-(\d+)', str(val), re.IGNORECASE)
            if match:
                num = int(match.group(1))
                if num > max_id:
                    max_id = num
    return f"BK-{max_id + 1}"


def write_booking(
    booking_data: Dict[str, Any], 
    approved_by: str, 
    excel_path: str = EXCEL_PATH
) -> Dict[str, Any]:
    """
    Write-action tool. Strictly locked behind HITL approval (approved_by cannot be empty/inferred).
    Appends the booking row into the 'Bookings Calendar' sheet in the Excel file, persisting across runs.
    """
    if not approved_by or not isinstance(approved_by, str) or not approved_by.strip():
        raise ValueError("CRITICAL SECURITY ERROR: write_booking requires an explicit 'approved_by' identifier.")
        
    if not os.path.exists(excel_path):
        raise FileNotFoundError(f"Database file not found at {excel_path}")
        
    wb = openpyxl.load_workbook(excel_path)
    if "Bookings Calendar" not in wb.sheetnames:
        raise ValueError("Worksheet 'Bookings Calendar' not found in workbook.")
        
    ws = wb["Bookings Calendar"]
    
    # Locate header row index
    header_row_idx = None
    headers = {}
    for r in range(1, 15):
        row_vals = [ws.cell(row=r, column=c).value for c in range(1, ws.max_column + 1)]
        if "Booking ID" in [str(v).strip() for v in row_vals if v is not None]:
            header_row_idx = r
            for c in range(1, ws.max_column + 1):
                h_name = ws.cell(row=r, column=c).value
                if h_name:
                    headers[str(h_name).strip()] = c
            break
            
    if header_row_idx is None:
        raise ValueError("Could not locate 'Booking ID' header row in 'Bookings Calendar' sheet.")
        
    # Generate sequential Booking ID if not provided
    booking_id = booking_data.get("Booking ID") or booking_data.get("booking_id")
    if not booking_id:
        booking_id = generate_next_booking_id(excel_path)
        
    # Find next empty row after header
    target_row = None
    for r in range(header_row_idx + 1, ws.max_row + 2):
        cell_val = ws.cell(row=r, column=headers.get("Booking ID", 1)).value
        if cell_val is None or str(cell_val).strip() == "":
            target_row = r
            break
            
    if target_row is None:
        target_row = ws.max_row + 1
        
    # Map input dictionary keys to Excel columns
    field_mappings = {
        "Booking ID": booking_id,
        "Date": booking_data.get("Date") or booking_data.get("date"),
        "Time Slot": booking_data.get("Time Slot") or booking_data.get("time_slot") or booking_data.get("slot"),
        "Patient Name": booking_data.get("Patient Name") or booking_data.get("patient_name") or booking_data.get("patient"),
        "Service Type": booking_data.get("Service Type") or booking_data.get("service_type"),
        "Assigned Staff": booking_data.get("Assigned Staff") or booking_data.get("assigned_staff") or booking_data.get("staff_name"),
        "Staff Role": booking_data.get("Staff Role") or booking_data.get("staff_role") or booking_data.get("role"),
        "Status": booking_data.get("Status") or booking_data.get("status") or "Confirmed",
        "Contact Number": booking_data.get("Contact Number") or booking_data.get("contact_number") or booking_data.get("contact"),
        "Address / Area": booking_data.get("Address / Area") or booking_data.get("Address") or booking_data.get("address") or booking_data.get("area"),
        "Notes": booking_data.get("Notes") or booking_data.get("notes") or f"Approved by {approved_by}"
    }
    
    # Write values into Excel cells
    for header_name, col_idx in headers.items():
        if header_name in field_mappings:
            val = field_mappings[header_name]
            if header_name == "Date" and val:
                parsed_d = parse_date(val)
                if parsed_d:
                    val = datetime.combine(parsed_d, time(0, 0))
            ws.cell(row=target_row, column=col_idx, value=val)
            
    wb.save(excel_path)
    wb.close()
    
    return {
        "status": "success",
        "message": f"Booking {booking_id} successfully committed to Excel by coordinator '{approved_by}'.",
        "booking_id": booking_id,
        "row_index": target_row,
        "booking_data": field_mappings
    }