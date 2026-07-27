import pytest
from services.sheets_service import build_job_hashmap
from tests.mock_data import MOCK_SHEET_ROWS, MOCK_PUNCTUATION_SHEET_ROWS

class MockValues:
    def get(self, spreadsheetId, range):
        return self
    def execute(self):
        return {"values": MOCK_SHEET_ROWS}

class MockSheetsService:
    """Simulates Google Sheets API service offline."""
    def spreadsheets(self):
        return self
    def values(self):
        return MockValues()

def test_composite_hashmap_indexing():
    """Verifies that O(1) Composite Hash Map indexes rows correctly."""
    mock_service = MockSheetsService()
    hashmap = build_job_hashmap(mock_service, "fake_spreadsheet_id")

    # Composite Key Lookup ('company|job_title' -> Row Number)
    assert hashmap.get("google|software engineer intern") == 2
    assert hashmap.get("meta|frontend engineer") == 3
    
    # Fallback Company Lookup
    assert hashmap.get("amazon") == 4
    
    # Non-existent Entry
    assert hashmap.get("apple|iOS developer") is None

class MockPunctuationService:
    def spreadsheets(self):
        return self
    def values(self):
        return self
    def get(self, spreadsheetId, range):
        return self
    def execute(self):
        return {"values": MOCK_PUNCTUATION_SHEET_ROWS}

def test_hashmap_normalization():
    mock_service = MockPunctuationService()
    hashmap = build_job_hashmap(mock_service, "fake_id")
    
    # Hashmap indexes raw strings lowercase
    assert hashmap.get("google, inc.|software engineer - intern") == 2
    assert hashmap.get("meta platforms") == 3