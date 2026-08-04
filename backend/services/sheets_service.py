import re
from typing import Dict, List, Optional
from googleapiclient.discovery import build
from services.auth import get_google_service
from utilities.fuzzy_match import clean_company, clean_title

# Sheet Column Mapping Constants
COLUMNS = {
    "COMPANY": "A",
    "JOB_LINK": "B",
    "TITLE": "C",
    "DATE_APPLIED": "D",
    "LATEST_EMAIL_UPDATE": "E",
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
    "oa": "OA",
    "interview scheduled": "Interview Scheduled",
    "interviewed": "Interviewed",
    "accepted": "Accepted",
    "rejected": "Rejected",
    "no reply": "No Reply",
    "offer": "Offer Received",
    "offer received": "Offer Received",
    "online assessment": "OA",
    "technical assessment": "OA",
    "coding assessment": "OA",
}


def normalize_status(raw_status: str) -> str:
    """Ensures status string matches exact case/spelling of Google Sheet dropdown chips."""
    if not raw_status:
        return "Applied"
    
    clean_val = raw_status.strip().lower()
    return VALID_STATUSES.get(clean_val, "Applied")


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
        if not row or idx == 0:
            continue
            
        row_number = idx + 1  # 1-based index for Google Sheets API
        company = clean_company(row[0]) if len(row) > 0 else ""
        title = clean_title(row[2]) if len(row) > 2 else ""

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


def update_or_append_job(spreadsheet_id: str, job_data: dict, sheet_name: str = "Main"):
    service = get_sheets_service()
    
    # Fetch current rows from sheet
    range_name = f"'{sheet_name}'!{COLUMNS['FULL_RANGE']}"
    result = service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id, 
        range=range_name
    ).execute()
    rows = result.get('values', [])

    raw_company = job_data.get("company_name") or ""
    raw_title = job_data.get("job_title") or ""
    
    norm_company = clean_company(raw_company)
    norm_title = clean_title(raw_title)
    status_value = normalize_status(job_data.get("application_status"))

    # Build O(1) Lookup Maps
    composite_map, company_map = build_job_hashmap(rows)
    
    composite_key = f"{norm_company}|{norm_title}"
    target_row_number = None

    # Composite Match Check ('company|title')
    if composite_key in composite_map:
        target_row_number = composite_map[composite_key]
        print(f"[Sheets Service] 🎯 Exact Composite Match found at Row {target_row_number}.")
    
    # Smart Company Fallback Match
    elif norm_company in company_map:
        matching_rows = company_map[norm_company]
        
        is_assessment_invite = (status_value == "OA")
        incoming_is_hackathon = "hackathon" in norm_title.lower()

        # Extract meaningful tokens from incoming title (ignoring generic stop words)
        stop_words = {"for", "and", "the", "in", "of", "to", "at", "opportunities", "university", "students", "program", "role"}
        incoming_tokens = set(re.findall(r'\b[a-z0-9]+\b', norm_title.lower())) - stop_words

        best_overlap_score = 0
        best_matching_row = None

        # Substring or Token Overlap Search
        for row_num in matching_rows:
            row_title = clean_title(rows[row_num - 1][2]) if len(rows[row_num - 1]) > 2 else ""
            row_title_lower = row_title.lower()
            
            # If this is an OA email and the sheet row is a Hackathon, but the assessment title 
            # doesn't explicitly say "hackathon", SKIP the hackathon row!
            if is_assessment_invite and "hackathon" in row_title_lower and not incoming_is_hackathon:
                continue

            # Direct Substring Match
            if norm_title and (norm_title in row_title_lower or row_title_lower in norm_title):
                target_row_number = row_num
                print(f"[Sheets Service] 🎯 Substring title match found at Row {target_row_number} ({row_title}).")
                break

            # Token Overlap Score Calculation
            row_tokens = set(re.findall(r'\b[a-z0-9]+\b', row_title_lower)) - stop_words
            overlap = incoming_tokens.intersection(row_tokens)
            overlap_score = len(overlap)

            # Keep track of the row with highest keyword overlap (must share at least 2 distinct key terms)
            if overlap_score > best_overlap_score and overlap_score >= 2:
                best_overlap_score = overlap_score
                best_matching_row = row_num

        # Apply token match if no substring match was triggered
        if not target_row_number and best_matching_row:
            target_row_number = best_matching_row
            print(f"[Sheets Service] 🎯 Token overlap match found at Row {target_row_number} (Overlap Score: {best_overlap_score}).")

        # If you applied to multiple roles at this company and keywords don't match, target_row_number stays None
        # so it safely appends a new application row instead of overwriting a different role!
        if not target_row_number and len(matching_rows) == 1:
            single_row_num = matching_rows[0]
            row_title = clean_title(rows[single_row_num - 1][2]) if len(rows[single_row_num - 1]) > 2 else ""
            if not ("hackathon" in row_title.lower() and not incoming_is_hackathon):
                target_row_number = single_row_num
                print(f"[Sheets Service] ℹ️ Single company application fallback at Row {target_row_number}.")

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

        if job_data.get("email_date"):
            update_range = f"'{sheet_name}'!{COLUMNS['LATEST_EMAIL_UPDATE']}{target_row_number}"
            service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=update_range,
                valueInputOption="USER_ENTERED",
                body={"values": [[job_data.get("email_date")]]}
            ).execute()
    else:
        print(f"[Sheets Service] ➕ No match found. Appending new application for {raw_company}...")
        
        first_seen_date = job_data.get("email_date", "") or job_data.get("date_applied", "")

        new_row = [
            raw_company,                                 # Column A: Company Name
            job_data.get("job_link", ""),                # Column B: Job Link
            raw_title,                                   # Column C: Job Title
            first_seen_date,                             # Column D: Date Applied (YYYY-MM-DD)
            first_seen_date,                             # Column E: Latest Email Update
            job_data.get("type_of_job", "Internship"),   # Column F: Type of Job
            job_data.get("salary", ""),                  # Column G: Salary
            job_data.get("contact_info", ""),            # Column H: Contact Info
            job_data.get("location", ""),                # Column I: Location
            status_value                                 # Column J: Status Dropdown Chip
        ]
        
        service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range=f"'{sheet_name}'!A:A",
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body={"values": [new_row]}
        ).execute()