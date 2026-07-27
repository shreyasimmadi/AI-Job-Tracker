import base64
from datetime import datetime
from typing import List, Dict, Set

from services.auth import get_google_service
from utilities.text_cleaner import clean_html

# In-memory O(1) Hash Set to track processed email message IDs during runtime
PROCESSED_MESSAGE_IDS: Set[str] = set()


def get_gmail_service():
    """Initializes and returns the Gmail API service client using shared OAuth auth."""
    return get_google_service('gmail', 'v1')


def decode_payload_data(data: str) -> str:
    """Decodes URL-safe base64 encoded string data from Gmail API payloads."""
    if not data:
        return ""
    decoded_bytes = base64.urlsafe_b64decode(data.encode('ASCII'))
    return decoded_bytes.decode('utf-8', errors='ignore')


def extract_email_body(message: dict) -> str:
    """
    Recursively inspects Gmail payload MIME parts.
    Prefers 'text/plain' content first to reduce LLM token usage.
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

    # 1. Primary choice: Return aggregated plain text
    full_plain = "\n".join(plain_text_parts).strip()
    if full_plain:
        return full_plain

    # 2. Fallback choice: Strip and return HTML text only if no plain text exists
    full_html = "\n".join(html_text_parts).strip()
    if full_html:
        return clean_html(full_html)

    # 3. Final fallback: Use email snippet
    return message.get('snippet', '').strip()


def fetch_unread_job_emails(max_results: int = 10) -> List[Dict[str, str]]:
    """
    Queries emails matching 'label:Job-Tracker newer_than:1d'.
    Uses an in-memory hash set to skip duplicate message IDs during runtime.
    """
    service = get_gmail_service()
    
    # Query strictly filters by Job-Tracker label for emails received within the past day
    query = 'label:Job-Tracker newer_than:1d'
    
    results = service.users().messages().list(
        userId='me', 
        q=query, 
        maxResults=max_results
    ).execute()
    
    messages = results.get('messages', [])
    email_data = []

    for msg in messages:
        msg_id = msg['id']
        
        # O(1) Runtime Cache Check: Skip if already processed in current server session
        if msg_id in PROCESSED_MESSAGE_IDS:
            print(f"[O(1) Hash Set Hit] Message {msg_id} already processed. Skipping.")
            continue

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
        
        # Track ID in runtime hash set
        PROCESSED_MESSAGE_IDS.add(msg_id)

    return email_data


def mark_email_as_read(message_id: str):
    """Removes the UNREAD label from processed emails."""
    service = get_gmail_service()
    service.users().messages().batchModify(
        userId='me',
        body={
            'ids': [message_id],
            'removeLabelIds': ['UNREAD']
        }
    ).execute()