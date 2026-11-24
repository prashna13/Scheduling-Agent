# Saathi Sneha Care — Scheduling Sub-Agent Core Engine
# Implements strictly the 4 core tools defined in the project scope.
# Milestone: Week 6 - HITL Booking & Coordinator Portal
__version__ = "0.6.0"
__milestone__ = "Week 6: HITL Booking & Coordinator Portal"

import os
import re
from datetime import datetime, date, time, timedelta
from typing import List, Dict, Any, Optional, Tuple, Union
import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EXCEL_PATH = os.path.join(BASE_DIR, "data", "Saathi_Sneha_Care_Scheduling_Calendar_Mockup.xlsx")

# Thread-safe in-memory cache mapped by (excel_path, sheet_name) -> (mtime, pd.DataFrame)
_SHEET_CACHE: Dict[Tuple[str, str], Tuple[float, pd.DataFrame]] = {}


def load_sheet(sheet_name: str, excel_path: str = EXCEL_PATH) -> pd.DataFrame:
    """Safely loads a specified sheet from the Excel mockup with in-memory caching and dynamic header resolution."""
    if not os.path.exists(excel_path):
        raise FileNotFoundError(f"Database file not found at {excel_path}")
    
    current_mtime = os.path.getmtime(excel_path)
    cache_key = (os.path.abspath(excel_path), sheet_name)
    
    if cache_key in _SHEET_CACHE:
        cached_mtime, cached_df = _SHEET_CACHE[cache_key]
        if cached_mtime == current_mtime:
            return cached_df.copy()
    
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
        
    _SHEET_CACHE[cache_key] = (current_mtime, df)
    return df.copy()


def get_staff_registry(excel_path: str = EXCEL_PATH) -> List[Tuple[str, str, str]]:
    """Dynamically extracts all registered staff (Name, Staff ID, Role) directly from Staff Availability."""
    df = load_sheet("Staff Availability", excel_path=excel_path)
    registry = []
    for _, row in df.iterrows():
        name = str(row.get('Name', '')).strip()
        s_id = str(row.get('Staff ID', '')).strip()
        role = str(row.get('Role', 'Staff')).strip()
        if name and s_id and s_id.lower() != 'nan':
            registry.append((name, s_id, role))
    return registry


def parse_date(date_val: Union[str, datetime, date]) -> Optional[date]:
    """Parses date strings or datetime objects into a standard datetime.date."""
    if isinstance(date_val, date) and not isinstance(date_val, datetime):
        return date_val
    if isinstance(date_val, datetime):
        return date_val.date()
    if pd.isna(date_val) or not date_val:
        return None
    
    date_str = str(date_val).strip()
    rel_key = re.sub(r'\s+', ' ', date_str.lower())
    if rel_key in ("today", "tonight"):
        return date.today()
    if rel_key == "tomorrow":
        return date.today() + timedelta(days=1)
    if rel_key == "day after tomorrow":
        return date.today() + timedelta(days=2)
    if rel_key == "yesterday":
        return date.today() - timedelta(days=1)
    formats = (
        "%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%d/%m/%Y", 
        "%d-%b-%Y", "%d-%B-%Y", "%d/%b/%Y", "%d/%B/%Y",
        "%b-%d-%Y", "%B-%d-%Y", "%b/%d/%Y", "%B/%d/%Y",
        "%B %d, %Y", "%b %d, %Y", "%d %B %Y", "%d %b %Y",
        "%Y-%m-%d %H:%M:%S"
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
    """Parses time range ('9:00 AM - 1:00 PM', '10am to 2pm') or single time ('11am' -> 1-hour slot)."""
    if not isinstance(time_str, str) or not time_str.strip():
        return None
    normalized = time_str.replace('–', '-').replace('—', '-').replace('–', '-')
    normalized = re.sub(r'\s+to\s+', '-', normalized, flags=re.IGNORECASE)
    if '-' not in normalized:
        # Treat single-time entries like "11am" as a 1-hour block so conflict checks never miss them
        t1 = parse_single_time(normalized)
        if not t1:
            return None
        end_dt = datetime.combine(date.today(), t1) + timedelta(hours=1)
        t2 = end_dt.time() if end_dt.date() == date.today() else time(23, 59)
        return (t1, t2)
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


def get_available_windows(
    working_hours_str: str,
    booked_slots: List[str],
    slot_duration_minutes: int = 60,
    min_start_time: Optional[time] = None
) -> List[str]:
    """Calculates discrete non-overlapping 1-hour slots during a working shift."""
    shift = parse_time_range(working_hours_str)
    if not shift:
        return []
    curr = datetime.combine(date.today(), shift[0])
    end_dt = datetime.combine(date.today(), shift[1])
    available_slots = []
    
    while curr + timedelta(minutes=slot_duration_minutes) <= end_dt:
        slot_end = curr + timedelta(minutes=slot_duration_minutes)
        if min_start_time is None or curr.time() >= min_start_time:
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
def read_availability(
    date_range: Optional[str] = None,
    role: str = "Nurse",
    excel_path: str = EXCEL_PATH
) -> List[Dict[str, Any]]:
    """
    TOOL 1 (Read-only): Reads the Staff Availability sheet and returns all staff
    matching the role who are scheduled to work on the given date (excluding 'Off' days).
    """
    df = load_sheet("Staff Availability", excel_path=excel_path)
    
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


def _norm_staff_label(val: Any) -> str:
    """Normalizes staff names/IDs ignoring punctuation differences like 'Dr.' vs 'dr'."""
    return re.sub(r'[^a-z0-9]+', ' ', str(val or '').lower()).strip()


def _resolve_staff_row(avail_df: pd.DataFrame, staff_id: str) -> Optional[pd.Series]:
    """Resolves a single staff row by exact Staff ID, exact full Name, or unambiguous name token."""
    staff_clean = staff_id.strip().lower()
    if not staff_clean:
        return None
    id_col = avail_df['Staff ID'].astype(str).str.strip().str.lower()
    name_col = avail_df['Name'].astype(str).str.strip().str.lower()

    exact = avail_df[(id_col == staff_clean) | (name_col == staff_clean)]
    if len(exact) == 1:
        return exact.iloc[0]
    if len(exact) > 1:
        raise ValueError(f"AMBIGUOUS STAFF IDENTIFIER: '{staff_id}' matches multiple staff records.")

    target_core = re.sub(r'^(dr\.?|doctor|nurse)\s+', '', staff_clean).strip()
    if not target_core:
        raise ValueError(f"AMBIGUOUS STAFF IDENTIFIER: '{staff_id}' is a generic title without a name.")

    token_pattern = rf'\b{re.escape(target_core)}\b'
    matched = avail_df[name_col.str.contains(token_pattern, regex=True)]
    if len(matched) > 1:
        raise ValueError(f"AMBIGUOUS STAFF IDENTIFIER: '{staff_id}' matches multiple staff members.")
    return matched.iloc[0] if len(matched) == 1 else None


# TOOL 2: check_conflict
def check_conflict(
    staff_id: str,
    slot: str,
    date: str,
    excel_path: str = EXCEL_PATH
) -> bool:
    """
    TOOL 2 (Read-only): Checks whether the requested time slot overlaps with an active
    (non-cancelled) booking in Bookings Calendar or falls outside the staff member's working hours.
    Returns True if there is a conflict or staff is off, False if free.
    """
    target_date = parse_date(date)
    if not target_date:
        return True
    
    day_name = target_date.strftime("%a")
    
    # 1. Verify shift hours in Staff Availability (unambiguous match)
    avail_df = load_sheet("Staff Availability", excel_path=excel_path)
    staff_row = _resolve_staff_row(avail_df, staff_id)
    if staff_row is None:
        return True
        
    staff_name = str(staff_row.get('Name', '')).strip()
    resolved_id = str(staff_row.get('Staff ID', '')).strip().lower()
    shift = str(staff_row.get(day_name, 'Off')).strip()
    
    if shift.lower() == 'off' or pd.isna(shift):
        return True
        
    if slot and not is_time_within_window(slot, shift):
        return True

    if slot and target_date == datetime.now().date():
        parsed_slot = parse_time_range(slot)
        if parsed_slot and parsed_slot[0] < datetime.now().time():
            return True
        
    # 2. Check active bookings in Bookings Calendar using normalized resolved staff name or ID
    bookings_df = load_sheet("Bookings Calendar", excel_path=excel_path)
    bookings_df['ParsedDate'] = bookings_df['Date'].apply(parse_date)
    
    assigned_col = bookings_df['Assigned Staff'].apply(_norm_staff_label)
    status_col = bookings_df['Status'].astype(str).str.strip().str.lower()
    norm_staff_name = _norm_staff_label(staff_name)
    norm_resolved_id = _norm_staff_label(resolved_id)
    
    day_bookings = bookings_df[
        (bookings_df['ParsedDate'] == target_date) &
        (status_col != 'cancelled') &
        ((assigned_col == norm_staff_name) | (assigned_col == norm_resolved_id))
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
    slot: Optional[str] = None,
    excel_path: str = EXCEL_PATH
) -> List[Dict[str, Any]]:
    """
    TOOL 3 (Read-only): Combines read_availability and check_conflict to propose
    the top 2-3 conflict-free candidate staff and open time windows for a family request.
    """
    avail_list = read_availability(date_range=date, role=role, excel_path=excel_path)
    candidates = []
    
    target_date = parse_date(date)
    
    # Load bookings once for calculating open slots
    bookings_df = load_sheet("Bookings Calendar", excel_path=excel_path)
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
            if check_conflict(staff_id=staff['staff_id'], slot=slot, date=date, excel_path=excel_path):
                continue
                
        # Calculate available open 1-hour slots using normalized staff name or ID
        norm_staff_name = _norm_staff_label(staff['name'])
        norm_staff_id = _norm_staff_label(staff['staff_id'])
        assigned_col = bookings_df['Assigned Staff'].apply(_norm_staff_label)
        day_bookings = bookings_df[
            (bookings_df['ParsedDate'] == target_date) &
            (bookings_df['Status'].astype(str).str.lower() != 'cancelled') &
            ((assigned_col == norm_staff_name) | (assigned_col == norm_staff_id))
        ]
        booked_slots = [str(b['Time Slot']).strip() for _, b in day_bookings.iterrows()]
        min_start = datetime.now().time() if target_date == datetime.now().date() else None
        open_slots = get_available_windows(staff['working_hours'], booked_slots, min_start_time=min_start)
        
        # Only include candidate when at least one open slot remains
        if open_slots:
            cand = dict(staff)
            cand["date"] = date
            cand["proposed_slots"] = [slot] if slot else open_slots[:3]
            candidates.append(cand)
            
    return candidates


# =========================================================================
# 📋 STEP 1 & 2: BOOKING DATA CONTRACT, STAGING & EXCEL PERSISTENCE (TOOL 4)
# =========================================================================

import json
import threading

_BOOKING_LOCK = threading.RLock()
STAGED_DRAFTS_PATH = os.path.join(BASE_DIR, "data", "staged_drafts.json")
_STAGED_DRAFTS: List[Dict[str, Any]] = []
_DRAFT_COUNTER: int = 0
DEFAULT_AUTHORIZED_COORDINATORS = {"coordinator_prashna", "coordinator_admin", "coordinator_sneha"}


def verify_coordinator_approval(approved_by: str) -> str:
    """Validates coordinator identity at the write boundary against AUTHORIZED_COORDINATORS."""
    if not approved_by or not isinstance(approved_by, str) or not approved_by.strip():
        raise ValueError("CRITICAL SECURITY ERROR: write_booking requires an explicit 'approved_by' identifier.")
    clean = approved_by.strip()
    raw_allowed = os.getenv("AUTHORIZED_COORDINATORS", "")
    allowed = {c.strip().lower() for c in raw_allowed.split(",") if c.strip()} or DEFAULT_AUTHORIZED_COORDINATORS
    if clean.lower() not in allowed:
        raise ValueError(f"CRITICAL SECURITY ERROR: Unauthorized coordinator '{clean}'.")
    return clean


def _save_drafts_to_disk() -> None:
    """Persists _STAGED_DRAFTS to disk and raises IOError if persistence fails."""
    try:
        os.makedirs(os.path.dirname(STAGED_DRAFTS_PATH), exist_ok=True)
        with open(STAGED_DRAFTS_PATH, "w", encoding="utf-8") as f:
            json.dump({"counter": _DRAFT_COUNTER, "drafts": _STAGED_DRAFTS}, f, indent=2)
    except Exception as exc:
        raise IOError(f"DRAFT PERSISTENCE ERROR: Could not persist staged drafts to {STAGED_DRAFTS_PATH}: {exc}") from exc


def _load_drafts_from_disk() -> None:
    """Loads persisted staged drafts from disk on module initialization."""
    global _STAGED_DRAFTS, _DRAFT_COUNTER
    if os.path.exists(STAGED_DRAFTS_PATH):
        try:
            with open(STAGED_DRAFTS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                _STAGED_DRAFTS = data.get("drafts", [])
                _DRAFT_COUNTER = int(data.get("counter", len(_STAGED_DRAFTS)))
        except Exception:
            _STAGED_DRAFTS = []


_load_drafts_from_disk()


def normalize_booking_contract(booking_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Step 1: Normalizes any booking dictionary (snake_case or Excel Title-Case) into the Booking Data Contract.
    """
    raw_slot = str(booking_data.get("time_slot") or booking_data.get("Time Slot") or booking_data.get("slot") or "").strip()
    parsed_range = parse_time_range(raw_slot)
    norm_slot = format_time_slot(parsed_range[0], parsed_range[1]) if parsed_range else raw_slot

    raw_date = booking_data.get("date") or booking_data.get("Date")
    b_date = parse_date(raw_date)
    norm_date = b_date.strftime("%Y-%m-%d") if b_date else str(raw_date or "").strip()

    return {
        "session_id": str(booking_data.get("session_id") or "default").strip(),
        "patient_name": str(booking_data.get("patient_name") or booking_data.get("Patient Name") or booking_data.get("Patient") or "Patient Inquiry").strip(),
        "contact_number": str(booking_data.get("contact_number") or booking_data.get("Contact Number") or "+91 90xxxxxx00").strip(),
        "date": norm_date,
        "time_slot": norm_slot,
        "assigned_staff": str(booking_data.get("assigned_staff") or booking_data.get("Assigned Staff") or booking_data.get("staff_name") or "").strip(),
        "staff_role": str(booking_data.get("staff_role") or booking_data.get("Staff Role") or booking_data.get("role") or "Doctor").strip(),
        "service_type": str(booking_data.get("service_type") or booking_data.get("Service Type") or "Home healthcare consult").strip(),
        "address_area": str(booking_data.get("address_area") or booking_data.get("Address / Area") or booking_data.get("area") or "Mumbai").strip(),
        "status": str(booking_data.get("status") or booking_data.get("Status") or "Confirmed").strip(),
        "notes": str(booking_data.get("notes") or booking_data.get("Notes") or "").strip()
    }


def _validate_not_past_date(date_str: str) -> date:
    """Rejects unparseable or past dates (earlier than today) at booking boundaries."""
    b_date = parse_date(date_str)
    if not b_date:
        raise ValueError(f"INVALID DATE: Could not parse booking date '{date_str}'.")
    today = date.today()
    if b_date < today:
        raise ValueError(
            f"PAST DATE ERROR: Cannot book or finalize an appointment for a past date ({b_date.strftime('%Y-%m-%d')}). "
            f"Bookings must be for today ({today.strftime('%Y-%m-%d')}) or a future date."
        )
    return b_date


def stage_booking_draft(booking_data: Dict[str, Any], persist_draft: bool = True) -> Dict[str, Any]:
    """
    Stages a conflict-free booking draft in memory and JSON disk journal for coordinator review.
    Does NOT write to the Excel database (enforcing Zero Unsupervised Writes).
    """
    global _DRAFT_COUNTER
    contract = normalize_booking_contract(booking_data)
    if contract["date"]:
        _validate_not_past_date(contract["date"])
    contract["status"] = "Pending Approval"

    with _BOOKING_LOCK:
        if persist_draft:
            for existing in _STAGED_DRAFTS:
                if (
                    existing.get("session_id", "default") == contract["session_id"]
                    and existing.get("date") == contract["date"]
                    and existing.get("time_slot") == contract["time_slot"]
                    and existing.get("assigned_staff", "").lower() == contract["assigned_staff"].lower()
                    and existing.get("patient_name", "").lower() == contract["patient_name"].lower()
                ):
                    for key in ("patient_name", "contact_number", "service_type", "address_area", "notes"):
                        if contract.get(key):
                            existing[key] = contract[key]
                    _save_drafts_to_disk()
                    return existing

            _DRAFT_COUNTER += 1
            contract["draft_id"] = f"DRAFT-{_DRAFT_COUNTER:02d}"
            _STAGED_DRAFTS.append(contract)
            _save_drafts_to_disk()
        else:
            contract["draft_id"] = "DRAFT-PREVIEW"

    return contract


def get_staged_drafts(session_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Returns staged booking drafts (filtered by session_id when provided)."""
    with _BOOKING_LOCK:
        if session_id:
            return [dict(d) for d in _STAGED_DRAFTS if d.get("session_id", "default") == session_id]
        return [dict(d) for d in _STAGED_DRAFTS]


def dismiss_staged_draft(draft_id: str) -> bool:
    """Removes a staged booking draft when rejected or dismissed by a coordinator or cancelled by user."""
    global _STAGED_DRAFTS
    with _BOOKING_LOCK:
        before = len(_STAGED_DRAFTS)
        _STAGED_DRAFTS = [d for d in _STAGED_DRAFTS if d.get("draft_id") != draft_id]
        _save_drafts_to_disk()
        return len(_STAGED_DRAFTS) < before


def _next_bk_id_from_ws(ws: Any) -> str:
    max_id = 100
    for row in ws.iter_rows(min_row=5, values_only=True):
        val = str(row[0] or "").strip()
        if val.upper().startswith("BK-"):
            try:
                max_id = max(max_id, int(val.split("-")[1]))
            except (ValueError, IndexError):
                pass
    return f"BK-{max_id + 1}"


def get_next_booking_id(excel_path: str = EXCEL_PATH) -> str:
    """Scans Bookings Calendar in Excel and returns the next sequential ID (e.g. BK-113)."""
    import openpyxl
    wb = openpyxl.load_workbook(excel_path, read_only=True)
    next_id = _next_bk_id_from_ws(wb["Bookings Calendar"])
    wb.close()
    return next_id


# TOOL 4: write_booking
def write_booking(
    booking_data: Dict[str, Any],
    approved_by: str,
    excel_path: str = EXCEL_PATH
) -> Dict[str, Any]:
    """
    TOOL 4 (HITL Action): Human-in-the-loop coordinator approval gate.
    Authenticates coordinator at the write boundary, validates required schedule fields
    and workbook existence, re-verifies no conflict exists (TOCTOU guard) under a thread lock,
    appends the row to Excel, and returns success ONLY after the write succeeds.
    """
    global _STAGED_DRAFTS
    clean_approver = verify_coordinator_approval(approved_by)
    contract = normalize_booking_contract(booking_data)
    booking_id = booking_data.get("booking_id")

    if not (contract["date"] and contract["time_slot"] and contract["assigned_staff"]):
        raise ValueError(
            "MISSING SCHEDULE FIELDS: 'date', 'time_slot', and 'assigned_staff' are required to write a booking."
        )

    _validate_not_past_date(contract["date"])

    if not os.path.exists(excel_path):
        raise FileNotFoundError(f"Database file not found at {excel_path}")

    import openpyxl
    with _BOOKING_LOCK:
        # TOCTOU Conflict Re-Check right before committing to Excel
        if check_conflict(
            staff_id=contract["assigned_staff"],
            slot=contract["time_slot"],
            date=contract["date"],
            excel_path=excel_path
        ):
            raise ValueError(
                f"CONFLICT ERROR: {contract['assigned_staff']} is already booked or unavailable on "
                f"{contract['date']} for {contract['time_slot']}."
            )

        wb = openpyxl.load_workbook(excel_path)
        try:
            ws = wb["Bookings Calendar"]

            if not booking_id:
                booking_id = _next_bk_id_from_ws(ws)

            b_date = parse_date(contract["date"])
            date_val = datetime.combine(b_date, time(0, 0)) if b_date else contract["date"]

            base_notes = contract["notes"]
            approval_note = f"Approved by {clean_approver}"
            final_notes = f"{base_notes} | {approval_note}" if base_notes else approval_note

            last_row_idx = 5
            for idx, row in enumerate(ws.iter_rows(min_row=5, values_only=True), start=5):
                if any(cell is not None and str(cell).strip() != "" for cell in row):
                    last_row_idx = idx
            target_row_idx = last_row_idx + 1

            new_row_values = [
                booking_id,
                date_val,
                contract["time_slot"],
                contract["patient_name"],
                contract["service_type"],
                contract["assigned_staff"],
                contract["staff_role"],
                "Confirmed",
                contract["contact_number"],
                contract["address_area"],
                final_notes
            ]

            for col_idx, val in enumerate(new_row_values, start=1):
                cell = ws.cell(row=target_row_idx, column=col_idx, value=val)
                if col_idx == 2 and isinstance(val, datetime):
                    cell.number_format = 'ddd", "dd-mmm-yyyy'

            try:
                wb.save(excel_path)
            except PermissionError as exc:
                raise PermissionError(
                    "EXCEL FILE LOCKED: Please close the Excel calendar file in Microsoft Excel and try again."
                ) from exc
        finally:
            wb.close()

        _SHEET_CACHE.clear()

        draft_id = booking_data.get("draft_id")
        avail_df = load_sheet("Staff Availability", excel_path=excel_path)

        def _canonical_staff_key(staff_val: str) -> str:
            try:
                row = _resolve_staff_row(avail_df, staff_val)
                if row is not None:
                    return str(row.get("Staff ID", staff_val)).strip().lower()
            except ValueError:
                pass
            return staff_val.strip().lower()

        booked_staff_key = _canonical_staff_key(contract["assigned_staff"])
        remaining_drafts: List[Dict[str, Any]] = []
        auto_cancelled_drafts: List[Dict[str, Any]] = []

        for d in _STAGED_DRAFTS:
            if draft_id and d.get("draft_id") == draft_id:
                continue
            is_conflict = (
                d.get("date") == contract["date"]
                and _canonical_staff_key(d.get("assigned_staff", "")) == booked_staff_key
                and times_overlap(d.get("time_slot", ""), contract["time_slot"])
            )
            if is_conflict:
                cancelled = dict(d)
                cancelled["status"] = "Cancelled"
                cancelled["cancellation_reason"] = (
                    f"Slot confirmed for booking {booking_id} ({contract['assigned_staff']} on "
                    f"{contract['date']} {contract['time_slot']})."
                )
                auto_cancelled_drafts.append(cancelled)
            else:
                remaining_drafts.append(d)

        _STAGED_DRAFTS = remaining_drafts
        _save_drafts_to_disk()

    return {
        "status": "success",
        "booking_id": booking_id,
        "message": f"Booking {booking_id} confirmed & written under coordinator approval: '{clean_approver}'",
        "approved_by": clean_approver,
        "booking": contract,
        "booking_data": contract,
        "auto_cancelled_drafts": auto_cancelled_drafts
    }


def save_sheet_edits(
    sheet_name: str,
    edited_df: pd.DataFrame,
    approved_by: str,
    excel_path: str = EXCEL_PATH
) -> int:
    """
    Saves manual coordinator edits strictly for 'Bookings Calendar' back to Excel
    while preserving title rows (1-4), headers (row 5), and never modifying 'Staff Availability'.
    """
    verify_coordinator_approval(approved_by)
    if sheet_name != "Bookings Calendar":
        raise ValueError(
            f"READ-ONLY SHEET ERROR: '{sheet_name}' is read-only and cannot be modified. "
            f"Only 'Bookings Calendar' can be written."
        )
    if not os.path.exists(excel_path):
        raise FileNotFoundError(f"Database file not found at {excel_path}")

    target_key = "Booking ID"
    import openpyxl

    with _BOOKING_LOCK:
        wb = openpyxl.load_workbook(excel_path)
        try:
            ws = wb[sheet_name]

            header_row_idx = 5
            headers: List[str] = []
            for idx, row in enumerate(ws.iter_rows(min_row=1, max_row=10, values_only=True), start=1):
                vals = [str(v).strip() if v is not None else "" for v in row]
                if target_key in vals:
                    header_row_idx = idx
                    headers = [v for v in vals if v]
                    break

            if not headers:
                headers = [str(c).strip() for c in edited_df.columns]

            # Drop completely empty rows from dynamic data_editor
            clean_rows: List[List[Any]] = []
            for _, row in edited_df.iterrows():
                row_vals = []
                has_any = False
                for col in headers:
                    val = row.get(col, None) if col in edited_df.columns else None
                    if pd.isna(val) or (isinstance(val, str) and not val.strip()):
                        val = None
                    else:
                        has_any = True
                        if sheet_name == "Bookings Calendar" and col == "Date":
                            parsed = parse_date(val)
                            if parsed:
                                val = datetime.combine(parsed, time(0, 0))
                    row_vals.append(val)
                if has_any:
                    clean_rows.append(row_vals)

            # Clear existing data rows below header without touching title/header rows
            max_clear_row = max(ws.max_row, header_row_idx + len(clean_rows))
            for r_idx in range(header_row_idx + 1, max_clear_row + 1):
                for c_idx in range(1, len(headers) + 1):
                    ws.cell(row=r_idx, column=c_idx, value=None)

            for offset, row_vals in enumerate(clean_rows, start=1):
                for c_idx, val in enumerate(row_vals, start=1):
                    cell = ws.cell(row=header_row_idx + offset, column=c_idx, value=val)
                    if sheet_name == "Bookings Calendar" and c_idx == 2 and isinstance(val, datetime):
                        cell.number_format = 'ddd", "dd-mmm-yyyy'

            try:
                wb.save(excel_path)
            except PermissionError as exc:
                raise PermissionError(
                    "EXCEL FILE LOCKED: Please close the Excel calendar file in Microsoft Excel and try again."
                ) from exc
        finally:
            wb.close()

        _SHEET_CACHE.clear()
        return len(clean_rows)


# =========================================================================
# WEEK 3 EXTENSION: 2-3 SLOT PROPOSAL CONVENIENCE WRAPPER
# =========================================================================

def suggest_slots_for_request(
    role: str = "Doctor",
    date_val: Optional[str] = None,
    specialty: Optional[str] = None,
    area: Optional[str] = None,
    preferred_slot: Optional[str] = None
) -> Dict[str, Any]:
    """
    Week 3 Deliverable: High-level helper specifically designed to return 2-3
    conflict-free time slots for a visit request rather than a simple binary yes/no.
    Wraps propose_slot() to provide structured slot recommendations.
    """
    candidates = propose_slot(
        role=role,
        specialty=specialty,
        date=date_val,
        area=area,
        slot=preferred_slot
    )
    return {
        "milestone": "Week 3",
        "date": date_val,
        "role": role,
        "total_available": len(candidates),
        "candidates": candidates
    }
