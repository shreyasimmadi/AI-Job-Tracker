import base64
from datetime import datetime
from typing import List, Dict, Optional

from services.auth import get_google_service
from utilities.text_cleaner import clean_html

# Cached label ID for "Job-Tracker-Done" so we only look it up once per process,
# not on every single pipeline run.
_DONE_LABEL_ID_CACHE: Optional[str] = None

DONE_LABEL_NAME = "Job Tracker Done"


def get_gmail_service():
    """Initializes and returns the Gmail API service client using shared OAuth auth."""
    return get_google_service('gmail', 'v1')


def get_done_label_id(service=None) -> str:
    """
    Looks up the Gmail label ID for DONE_LABEL_NAME (e.g. 'Job-Tracker-Done').
    Gmail's API requires a label ID (like 'Label_123') to apply/remove labels,
    not the display name, so this resolves the name -> ID once and caches it.

    Raises a clear error if the label doesn't exist yet, since it must be
    created manually in Gmail first (Settings -> Labels -> Create new label).
    """
    global _DONE_LABEL_ID_CACHE
    if _DONE_LABEL_ID_CACHE:
        return _DONE_LABEL_ID_CACHE

    service = service or get_gmail_service()
    labels_response = service.users().labels().list(userId='me').execute()
    labels = labels_response.get('labels', [])

    for label in labels:
        if label.get('name') == DONE_LABEL_NAME:
            _DONE_LABEL_ID_CACHE = label['id']
            return _DONE_LABEL_ID_CACHE

    raise ValueError(
        f"Gmail label '{DONE_LABEL_NAME}' not found. "
        f"Create it manually in Gmail (Settings -> Labels -> Create new label) first."
    )


def decode_payload_data(data: str) -> str:
    """Decodes URL-safe base64 encoded string data from Gmail API payloads."""
    if not data:
        return ""
    decoded_bytes = base64.urlsafe_b64decode(data.encode('ASCII'))
    return decoded_bytes.decode('utf-8', errors='ignore')


def extract_email_body(message: dict) -> str:
    def extract_email_body(message: dict) -> str:
    """
    Recursively inspects Gmail payload MIME parts.
    Prefers 'text/plain' content first to reduce LLM token usage, but cleans all
    text streams through clean_html() to strip ERB template tags and markup.
    Falls back to cleaned 'text/html' only if plain text is absent,
    and uses message snippet as a last resort.
    """
    payload = message.get('payload', {})
    plain_text_parts = []
    html_text_parts = []

    def walk_parts(part: dict):
        mime_type = part.get('mimeType', '')
        body_data = part.get('body', {}).get('data', '')

        if body_data:
            decoded_text = decode_payload_data(body_data)
            if mime_type == 'text/plain':
                plain_text_parts.append(decoded_text)
            elif mime_type == 'text/html':
                html_text_parts.append(decoded_text)

        # Recursively walk multipart subparts (multipart/alternative, multipart/mixed, etc.)
        for subpart in part.get('parts', []):
            walk_parts(subpart)

    walk_parts(payload)

    # 1. Primary choice: Return cleaned plain text
    full_plain = "\n".join(plain_text_parts).strip()
    if full_plain:
        cleaned_plain = clean_html(full_plain)
        if cleaned_plain:
            return cleaned_plain

    # 2. Fallback choice: Strip and return HTML text only if no plain text exists
    full_html = "\n".join(html_text_parts).strip()
    if full_html:
        cleaned_html = clean_html(full_html)
        if cleaned_html:
            return cleaned_html

    # 3. Final fallback: Use email snippet
    return clean_html(message.get('snippet', '').strip())

def fetch_unread_job_emails(max_results: int = 10) -> List[Dict[str, str]]:
    """
    Queries emails matching 'label:Job-Tracker -label:Job-Tracker-Done newer_than:7d'.

    Dedup is handled entirely server-side by Gmail via the Job-Tracker-Done label
    (applied by mark_email_as_processed after a successful pipeline run) —
    this survives process restarts and is unaffected by you reading emails
    yourself, unlike relying on the UNREAD flag or an in-memory set.
    """
    service = get_gmail_service()

    # newer_than:7d is just a generous safety bound so the query doesn't scan
    # the entire inbox history -- the Job-Tracker-Done label exclusion is what
    # actually prevents reprocessing, not this time window.
    query = 'label:Job-Tracker -label:Job-Tracker-Done newer_than:7d'

    results = service.users().messages().list(
        userId='me', 
        q=query, 
        maxResults=max_results
    ).execute()
    
    messages = results.get('messages', [])
    email_data = []

    for msg in messages:
        msg_id = msg['id']

        # Fetch full message payload
        message = service.users().messages().get(
            userId='me', 
            id=msg_id, 
            format='full'
        ).execute()
        
        thread_id = message.get('threadId')
        
        # Convert internal Gmail timestamp (ms) to YYYY-MM-DD date string
        internal_date_ms = int(message.get('internalDate', 0))
        if internal_date_ms:
            email_date = datetime.fromtimestamp(internal_date_ms / 1000.0).strftime('%Y-%m-%d')
        else:
            email_date = datetime.now().strftime('%Y-%m-%d')
            
        # Extract body text (prefers text/plain)
        body = extract_email_body(message)

        email_data.append({
            "id": msg_id,
            "thread_id": thread_id,
            "raw_body": body,
            "email_date": email_date
        })

    return email_data


def mark_email_as_processed(message_id: str):
    """
    Applies the Job-Tracker-Done label to a message, marking it as handled.
    This is Gmail-side, permanent state -- call this ONLY after the email has
    been fully and successfully processed (i.e. after update_or_append_job
    succeeds), so a mid-pipeline failure leaves the email unlabeled and
    eligible for retry on the next run instead of being silently skipped.
    """
    service = get_gmail_service()
    done_label_id = get_done_label_id(service)

    service.users().messages().batchModify(
        userId='me',
        body={
            'ids': [message_id],
            'addLabelIds': [done_label_id]
        }
    ).execute()