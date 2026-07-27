from typing import Dict, List, Optional
from googleapiclient.discovery import build
from services.auth import get_google_service

# Google Sheets API Read/Write Scope
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/spreadsheets'
]

# Sheet Column Mapping Constants
COLUMNS = {
    "COMPANY": "A",
    "JOB_LINK": "B",
    "TITLE": "C",
    "DATE_APPLIED": "D",
    "DEADLINE": "E",
    "JOB_TYPE": "F",
    "SALARY": "G",
    "CONTACT": "H",
    "LOCATION": "I",
    "STATUS": "J",
    "FULL_RANGE": "A:J"
}

# Valid dropdown options matching Google Sheet chip options
VALID_STATUSES = {
    "not started": "Not Started",
    "applied": "Applied",
    "interview scheduled": "Interview Scheduled",
    "interviewed": "Interviewed",
    "accepted": "Accepted",
    "rejected": "Rejected",
    "no reply": "No Reply",
    "offer": "Offer Received",
    "offer received": "Offer Received"
}


def normalize_status(raw_status: str) -> str:
    """Ensures status string matches exact case/spelling of Google Sheet dropdown chips."""
    if not raw_status:
        return "Applied"
    
    clean_val = raw_status.strip().lower()
    return VALID_STATUSES.get(clean_val, "Applied")


def clean_str(val: str) -> str:
    """Normalizes string and strips common business entity suffixes for consistent matching."""
    if not val:
        return ""
    
    cleaned = val.strip().lower()
    suffixes = [" bio", " inc", " llc", " corp", " corporation", " ltd", " technologies", " technology", " tech"]
    for suffix in suffixes:
        cleaned = cleaned.replace(suffix, "")
    return cleaned.strip()


def get_sheets_service():
    """Authenticates and returns the Google Sheets API client service."""
    return get_google_service('sheets', 'v4')


def build_job_hashmap(rows: list) -> tuple[Dict[str, int], Dict[str, List[int]]]:
    """
    Reads spreadsheet rows and builds dictionary mappings for fast O(1) lookups.
    Returns:
      - composite_map: 'clean_company|clean_title' -> row_number (1-based index)
      - company_map: 'clean_company' -> list of matching row_numbers
    """
    composite_map = {}
    company_map = {}

    for idx, row in enumerate(rows):
        if not row:
            continue
            
        row_number = idx + 1  # 1-based index for Google Sheets API
        company = clean_str(row[0]) if len(row) > 0 else ""
        title = clean_str(row[2]) if len(row) > 2 else ""

        if company:
            # Add to company fallback mapping
            if company not in company_map:
                company_map[company] = []
            company_map[company].append(row_number)

            # Add to primary composite map
            if title:
                composite_key = f"{company}|{title}"
                composite_map[composite_key] = row_number

    return composite_map, company_map


def update_or_append_job(spreadsheet_id: str, job_data: dict, sheet_name: str = "Sheet1"):
    service = get_sheets_service()
    
    # 1. Fetch current rows from sheet
    range_name = f"'{sheet_name}'!{COLUMNS['FULL_RANGE']}"
    result = service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id, 
        range=range_name
    ).execute()
    rows = result.get('values', [])

    raw_company = job_data.get("company_name") or ""
    raw_title = job_data.get("job_title") or ""
    
    norm_company = clean_str(raw_company)
    norm_title = clean_str(raw_title)
    status_value = normalize_status(job_data.get("application_status"))

    # 2. Build O(1) Lookup Maps
    composite_map, company_map = build_job_hashmap(rows)
    
    composite_key = f"{norm_company}|{norm_title}"
    target_row_number = None

    # Step 3: O(1) Composite Match Check ('company|title')
    if composite_key in composite_map:
        target_row_number = composite_map[composite_key]
        print(f"[Sheets Service] 🎯 Exact Composite Match found at Row {target_row_number}.")
    
    # Step 4: Company Fallback Match
    elif norm_company in company_map:
        matching_rows = company_map[norm_company]
        
        if len(matching_rows) == 1:
            target_row_number = matching_rows[0]
        else:
            # Multiple applications at the same company -> match highest title overlap
            for row_num in matching_rows:
                row_title = clean_str(rows[row_num - 1][2]) if len(rows[row_num - 1]) > 2 else ""
                if norm_title and (norm_title in row_title or row_title in norm_title):
                    target_row_number = row_num
                    break
            
            if not target_row_number:
                target_row_number = matching_rows[-1]  # Default to most recent row entry

    # Step 5: Update Existing Row or Append New Row
    if target_row_number:
        print(f"[Sheets Service] 🔄 Updating Row {target_row_number} status to '{status_value}'...")
        
        status_range = f"'{sheet_name}'!{COLUMNS['STATUS']}{target_row_number}"
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=status_range,
            valueInputOption="USER_ENTERED",
            body={"values": [[status_value]]}
        ).execute()

        if job_data.get("date_applied"):
            date_range = f"'{sheet_name}'!{COLUMNS['DATE_APPLIED']}{target_row_number}"
            service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=date_range,
                valueInputOption="USER_ENTERED",
                body={"values": [[job_data.get("date_applied")]]}
            ).execute()
    else:
        print(f"[Sheets Service] ➕ No match found. Appending new application for {raw_company}...")
        
        new_row = [
            raw_company,                                 # Column A: Company Name
            job_data.get("job_link", ""),                # Column B: Job Link
            raw_title,                                   # Column C: Job Title
            job_data.get("date_applied", ""),            # Column D: Date Applied (YYYY-MM-DD)
            job_data.get("deadline", ""),                # Column E: Deadline
            job_data.get("type_of_job", "Internship"),   # Column F: Type of Job
            job_data.get("salary", ""),                  # Column G: Salary
            job_data.get("contact_info", ""),            # Column H: Contact Info
            job_data.get("location", ""),                # Column I: Location
            status_value                                 # Column J: Status Dropdown Chip
        ]
        
        service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range=f"'{sheet_name}'!{COLUMNS['FULL_RANGE']}",
            valueInputOption="USER_ENTERED",
            body={"values": [new_row]}
        ).execute()