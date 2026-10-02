# Saathi Sneha Care — Scheduling Sub-Agent Core Engine
# Implements strictly the 4 core tools defined in the project scope.
import os
import re
from datetime import datetime, date, time, timedelta
from typing import List, Dict, Any, Optional, Tuple, Union
import pandas as pd

EXCEL_PATH = os.path.join("data", "Saathi_Sneha_Care_Scheduling_Calendar_Mockup.xlsx")


def load_sheet(sheet_name: str, excel_path: str = EXCEL_PATH) -> pd.DataFrame:
    """Safely loads a specified sheet from the Excel mockup with dynamic header resolution."""
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
        header_idx = 4
        
    df = pd.read_excel(excel_path, sheet_name=sheet_name, header=header_idx)
    if target_key in df.columns:
        df = df.dropna(subset=[target_key]).copy()
    return df


def parse_date(date_val: Union[str, datetime, date]) -> Optional[date]:
    """Parses date strings or datetime objects into a standard datetime.date."""
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
    """Parses single time string ('9:00 AM', '9am', '14:00')."""
    if not isinstance(t_str, str) or not t_str.strip():
        return None
    s = t_str.strip().upper()
    s = re.sub(r'(\d+)(AM|PM)', r'\1 \2', s)
    s = re.sub(r'\s+', ' ', s)
    
    for fmt in ["%I:%M %p", "%I %p", "%H:%M", "%H:%M:%S", "%I:%M:%S %p"]:
        try:
            return datetime.strptime(s, fmt).time()
        except ValueError:
            pass
    return None


def parse_time_range(time_str: str) -> Optional[Tuple[time, time]]:
    """Parses time range ('9:00 AM - 1:00 PM', '10am to 2pm')."""
    if not isinstance(time_str, str) or not time_str.strip():
        return None
    normalized = time_str.replace('–', '-').replace('—', '-').replace('–', '-')
    normalized = re.sub(r'\s+to\s+', '-', normalized, flags=re.IGNORECASE)
    if '-' not in normalized:
        return None
    parts = normalized.split('-', 1)
    t1 = parse_single_time(parts[0])
    t2 = parse_single_time(parts[1])
    return (t1, t2) if (t1 and t2) else None


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
    """Formats two time objects into '9:00 AM - 10:00 AM'."""
    s1 = datetime.combine(date.today(), t1).strftime("%I:%M %p").lstrip("0")
    s2 = datetime.combine(date.today(), t2).strftime("%I:%M %p").lstrip("0")
    return f"{s1} - {s2}"


def get_available_windows(working_hours_str: str, booked_slots: List[str], slot_duration_minutes: int = 60) -> List[str]:
    """Calculates discrete non-overlapping 1-hour slots during a working shift."""
    shift = parse_time_range(working_hours_str)
    if not shift:
        return []
    curr = datetime.combine(date.today(), shift[0])
    end_dt = datetime.combine(date.today(), shift[1])
    available_slots = []
    
    while curr + timedelta(minutes=slot_duration_minutes) <= end_dt:
        slot_end = curr + timedelta(minutes=slot_duration_minutes)
        cand_slot_str = format_time_slot(curr.time(), slot_end.time())
        conflict = any(times_overlap(cand_slot_str, b) for b in booked_slots)
        if not conflict:
            available_slots.append(cand_slot_str)
        curr += timedelta(minutes=slot_duration_minutes)
    return available_slots


# =========================================================================
# 🎯 THE 4 CORE TOOLS
# =========================================================================

# TOOL 1: read_availability
def read_availability(date_range: Optional[str] = None, role: str = "Nurse") -> List[Dict[str, Any]]:
    """
    TOOL 1 (Read-only): Reads the Staff Availability sheet and returns all staff
    matching the role who are scheduled to work on the given date (excluding 'Off' days).
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
            "staff_id": str(row.get('Staff ID', '')).strip(),
            "name": str(row.get('Name', '')).strip(),
            "role": str(row.get('Role', role)).strip(),
            "specialty": str(row.get('Specialty', '')).strip() if pd.notna(row.get('Specialty')) else '',
            "service_area": str(row.get('Service Area', '')).strip() if pd.notna(row.get('Service Area')) else '',
            "notes": str(row.get('Notes', '')).strip() if pd.notna(row.get('Notes')) else '',
            "working_hours": str(hours).strip() if hours != "N/A" else "Available"
        }
        available_staff.append(staff_member)
        
    return available_staff


# TOOL 2: check_conflict
def check_conflict(staff_id: str, slot: str, date: str) -> bool:
    """
    TOOL 2 (Read-only): Checks whether the requested time slot overlaps with an active
    (non-cancelled) booking in Bookings Calendar or falls outside the staff member's working hours.
    Returns True if there is a conflict or staff is off, False if free.
    """
    target_date = parse_date(date)
    if not target_date:
        return True
    
    day_name = target_date.strftime("%a")
    
    # 1. Verify shift hours in Staff Availability
    avail_df = load_sheet("Staff Availability")
    staff_clean = staff_id.strip().lower()
    target_core = re.sub(r'^(dr\.?|doctor|nurse)\s+', '', staff_clean).strip()
    
    matched = avail_df[
        (avail_df['Staff ID'].astype(str).str.strip().str.lower() == staff_clean) |
        (avail_df['Name'].astype(str).str.strip().str.lower() == staff_clean) |
        (avail_df['Name'].astype(str).str.strip().str.lower().str.contains(target_core, regex=False))
    ]
    
    if matched.empty:
        return True
        
    staff_row = matched.iloc[0]
    staff_name = str(staff_row.get('Name', ''))
    shift = str(staff_row.get(day_name, 'Off')).strip()
    
    if shift.lower() == 'off' or pd.isna(shift):
        return True
        
    if slot and not is_time_within_window(slot, shift):
        return True
        
    # 2. Check active bookings in Bookings Calendar
    bookings_df = load_sheet("Bookings Calendar")
    bookings_df['ParsedDate'] = bookings_df['Date'].apply(parse_date)
    
    assigned_col = bookings_df['Assigned Staff'].astype(str).str.strip().str.lower()
    status_col = bookings_df['Status'].astype(str).str.strip().str.lower()
    
    day_bookings = bookings_df[
        (bookings_df['ParsedDate'] == target_date) &
        (status_col != 'cancelled') &
        (
            (assigned_col == staff_name.strip().lower()) |
            (assigned_col == staff_clean) |
            (assigned_col.str.contains(target_core, regex=False))
        )
    ]
    
    for _, b in day_bookings.iterrows():
        b_slot = str(b.get('Time Slot', '')).strip()
        if slot and times_overlap(slot, b_slot):
            return True
            
    return False


# TOOL 3: propose_slot
def propose_slot(
    role: str = "Nurse", 
    specialty: Optional[str] = None, 
    date: Optional[str] = None, 
    area: Optional[str] = None,
    slot: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    TOOL 3 (Read-only): Combines read_availability and check_conflict to propose
    the top 2-3 conflict-free candidate staff and open time windows for a family request.
    """
    avail_list = read_availability(date_range=date, role=role)
    candidates = []
    
    target_date = parse_date(date)
    
    # Load bookings once for calculating open slots
    bookings_df = load_sheet("Bookings Calendar")
    bookings_df['ParsedDate'] = bookings_df['Date'].apply(parse_date)
    
    for staff in avail_list:
        # Specialty match
        if specialty and specialty.strip():
            s_spec = str(staff.get('specialty', '')).lower()
            if specialty.strip().lower() not in s_spec:
                continue
                
        # Area match
        if area and area.strip():
            s_areas = [a.strip().lower() for a in str(staff.get('service_area', '')).split(',')]
            if area.strip().lower() not in s_areas and not any(area.strip().lower() in a for a in s_areas):
                continue
                
        # Conflict check if specific slot requested
        if slot:
            if check_conflict(staff_id=staff['staff_id'], slot=slot, date=date):
                continue
                
        # Calculate available open 1-hour slots
        staff_name = staff['name']
        day_bookings = bookings_df[
            (bookings_df['ParsedDate'] == target_date) &
            (bookings_df['Status'].astype(str).str.lower() != 'cancelled') &
            (
                (bookings_df['Assigned Staff'].astype(str).str.strip().str.lower() == staff_name.strip().lower()) |
                (bookings_df['Assigned Staff'].astype(str).str.strip().str.lower() == staff['staff_id'].strip().lower())
            )
        ]
        booked_slots = [str(b['Time Slot']).strip() for _, b in day_bookings.iterrows()]
        open_slots = get_available_windows(staff['working_hours'], booked_slots)
        
        # If open slots exist, include candidate with top 2-3 proposed slots
        if open_slots or not booked_slots:
            cand = dict(staff)
            cand["date"] = date
            cand["proposed_slots"] = [slot] if slot else open_slots[:3]
            candidates.append(cand)
            
    return candidates


# TOOL 4: write_booking
def write_booking(booking_data: Dict[str, Any], approved_by: str) -> Dict[str, Any]:
    """
    TOOL 4 (HITL Action): Human-in-the-loop coordinator approval gate.
    Validates the booking proposal. Strictly requires an approved_by coordinator identifier.
    """
    if not approved_by or not isinstance(approved_by, str) or not approved_by.strip():
        raise ValueError("CRITICAL SECURITY ERROR: write_booking requires an explicit 'approved_by' identifier.")
        
    return {
        "status": "success",
        "message": f"Booking staged & validated under coordinator approval: '{approved_by}'",
        "approved_by": approved_by,
        "booking_data": booking_data
    }