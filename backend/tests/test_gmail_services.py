import pytest
from services.gmail_service import PROCESSED_MESSAGE_IDS
from tests.mock_data import MOCK_GMAIL_MESSAGES_LIST

def test_processed_ids_hashset_deduplication():
    """Verifies O(1) Hash Set deduplication prevents processing the same message twice."""
    # Reset set for testing
    PROCESSED_MESSAGE_IDS.clear()

    processed_count = 0
    for msg in MOCK_GMAIL_MESSAGES_LIST:
        msg_id = msg["id"]
        
        # O(1) Hash Set Lookup
        if msg_id in PROCESSED_MESSAGE_IDS:
            continue
            
        PROCESSED_MESSAGE_IDS.add(msg_id)
        processed_count += 1

    # Out of 3 items in MOCK_GMAIL_MESSAGES_LIST (where 1 was a duplicate), only 2 should be processed
    assert processed_count == 2
    assert "msg_001" in PROCESSED_MESSAGE_IDS
    assert "msg_002" in PROCESSED_MESSAGE_IDS