import base64
from datetime import datetime
from typing import List, Dict, Optional

from services.auth import get_google_service
from utilities.text_cleaner import clean_html

_DONE_LABEL_ID_CACHE: Optional[str] = None
DONE_LABEL_NAME = "Job Tracker Done"


def get_gmail_service():
    return get_google_service('gmail', 'v1')


def get_done_label_id(service=None) -> str:
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
    if not data:
        return ""
    try:
        decoded_bytes = base64.urlsafe_b64decode(data.encode('ASCII'))
        return decoded_bytes.decode('utf-8', errors='ignore')
    except Exception:
        return ""


def extract_email_body(message: dict) -> str:
    """
    Recursively traverses all payload parts to collect plain text and HTML.
    Prefers text/plain if substantial (>100 chars), otherwise falls back to text/html.
    """
    payload = message.get('payload', {})
    plain_text_parts = []
    html_text_parts = []

    def walk_parts(part: dict):
        if not part:
            return

        mime_type = part.get('mimeType', '')
        body = part.get('body', {})
        body_data = body.get('data', '')

        if body_data:
            decoded_text = decode_payload_data(body_data)
            if decoded_text:
                if mime_type == 'text/plain':
                    plain_text_parts.append(decoded_text)
                elif mime_type == 'text/html':
                    html_text_parts.append(decoded_text)

        # Recursively walk subparts
        for subpart in part.get('parts', []):
            walk_parts(subpart)

    walk_parts(payload)

    # 1. Clean and check plain text
    full_plain = "\n".join(plain_text_parts).strip()
    cleaned_plain = clean_html(full_plain) if full_plain else ""

    # If plain text exists and isn't just a tiny footer (>100 chars), use it
    if len(cleaned_plain) > 100:
        return cleaned_plain

    # 2. Fallback to HTML text if plain text was missing or truncated
    full_html = "\n".join(html_text_parts).strip()
    cleaned_html = clean_html(full_html) if full_html else ""
    if cleaned_html:
        return cleaned_html

    # 3. Last resort fallback
    return cleaned_plain or clean_html(message.get('snippet', '').strip())


def fetch_unread_job_emails(max_results: int = 10) -> List[Dict[str, str]]:
    service = get_gmail_service()
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

        message = service.users().messages().get(
            userId='me', 
            id=msg_id, 
            format='full'
        ).execute()
        
        thread_id = message.get('threadId')
        
        internal_date_ms = int(message.get('internalDate', 0))
        if internal_date_ms:
            email_date = datetime.fromtimestamp(internal_date_ms / 1000.0).strftime('%Y-%m-%d')
        else:
            email_date = datetime.now().strftime('%Y-%m-%d')
            
        body = extract_email_body(message)

        email_data.append({
            "id": msg_id,
            "thread_id": thread_id,
            "raw_body": body,
            "email_date": email_date
        })

    return email_data


def mark_email_as_processed(message_id: str):
    service = get_gmail_service()
    done_label_id = get_done_label_id(service)

    service.users().messages().batchModify(
        userId='me',
        body={
            'ids': [message_id],
            'addLabelIds': [done_label_id]
        }
    ).execute()