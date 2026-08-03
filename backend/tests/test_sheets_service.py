from unittest.mock import MagicMock, patch

import pytest

from services.sheets_service import (
    build_job_hashmap,
    normalize_status,
    update_or_append_job,
    COLUMNS,
)


# --- normalize_status ---

def test_normalize_status_known_values():
    assert normalize_status("applied") == "Applied"
    assert normalize_status("Online Assessment") == "OA"
    assert normalize_status("OA") == "OA"  # exact literal Gemini now outputs
    assert normalize_status("REJECTED") == "Rejected"


def test_normalize_status_unknown_falls_back_to_applied():
    assert normalize_status("some unexpected status") == "Applied"


def test_normalize_status_empty_or_none():
    assert normalize_status("") == "Applied"
    assert normalize_status(None) == "Applied"


# --- build_job_hashmap (uses clean_company / clean_title now, not clean_str) ---

def test_build_job_hashmap_composite_key_uses_company_and_title_normalization():
    rows = [
        ["Appian Inc", "link", "Software Engineer Intern", "2026-08-01"],
    ]
    composite_map, company_map = build_job_hashmap(rows)
    # Company suffix ("Inc") should be stripped; title just lowercased/whitespace-normalized
    assert "appian|software engineer intern" in composite_map
    assert composite_map["appian|software engineer intern"] == 1
    assert company_map["appian"] == [1]


def test_build_job_hashmap_title_normalization_does_not_strip_suffixes():
    """
    Titles should NOT go through company-suffix stripping -- clean_title is
    just lowercase + whitespace collapse. A title containing something that
    looks like a suffix substring (unlikely in practice, but worth locking
    down) should be preserved as-is aside from case/whitespace.
    """
    rows = [
        ["Some Corp", "link", "  Software   Engineer   Intern  ", "2026-08-01"],
    ]
    composite_map, _ = build_job_hashmap(rows)
    # Company "Some Corp" -> "some" (suffix stripped), title whitespace-collapsed
    assert "some|software engineer intern" in composite_map


def test_build_job_hashmap_groups_multiple_rows_same_company():
    rows = [
        ["Appian", "link1", "Software Engineer Intern", "2026-08-01"],
        ["Appian", "link2", "Data Science Intern", "2026-08-02"],
    ]
    _, company_map = build_job_hashmap(rows)
    assert company_map["appian"] == [1, 2]


def test_build_job_hashmap_skips_empty_rows():
    rows = [
        [],
        ["Appian", "link", "Software Engineer Intern", "2026-08-01"],
    ]
    composite_map, company_map = build_job_hashmap(rows)
    assert len(company_map["appian"]) == 1
    assert company_map["appian"] == [2]  # row_number correctly offset by the empty row


def test_build_job_hashmap_handles_short_rows_missing_title_column():
    rows = [
        ["Appian"],  # no title column at all
    ]
    composite_map, company_map = build_job_hashmap(rows)
    assert company_map["appian"] == [1]
    assert composite_map == {}  # no title -> no composite key added


def test_build_job_hashmap_empty_sheet():
    composite_map, company_map = build_job_hashmap([])
    assert composite_map == {}
    assert company_map == {}


# --- update_or_append_job (mocked Google Sheets API) ---

def _make_mock_service(existing_rows):
    """Builds a mock Sheets API service whose .get().execute() returns the
    given rows, and records every .update()/.append() call for assertions."""
    mock_service = MagicMock()
    mock_service.spreadsheets().values().get().execute.return_value = {
        "values": existing_rows
    }
    return mock_service


@patch("services.sheets_service.get_sheets_service")
def test_update_or_append_job_appends_new_row_when_no_match(mock_get_service):
    mock_service = _make_mock_service(existing_rows=[])
    mock_get_service.return_value = mock_service

    job_data = {
        "company_name": "Appian",
        "job_title": "Software Engineer Intern",
        "application_status": "Applied",
        "email_date": "2026-08-01",
        "job_link": "https://example.com/jobs/123",
        "location": "McLean, VA",
    }
    update_or_append_job("fake_sheet_id", job_data)

    # Should have called append (new row), not update (existing row)
    mock_service.spreadsheets().values().append.assert_called_once()
    call_kwargs = mock_service.spreadsheets().values().append.call_args.kwargs
    new_row = call_kwargs["body"]["values"][0]
    assert new_row[0] == "Appian"
    assert new_row[3] == "2026-08-01"  # DATE_APPLIED
    assert new_row[4] == "2026-08-01"  # LATEST_EMAIL_UPDATE (same on first creation)


@patch("services.sheets_service.get_sheets_service")
def test_update_or_append_job_updates_existing_row_via_composite_match(mock_get_service):
    existing_rows = [
        ["Appian", "https://example.com/jobs/123", "Software Engineer Intern",
         "2026-07-01", "2026-07-01", "Internship", "", "", "McLean, VA", "Applied"],
    ]
    mock_service = _make_mock_service(existing_rows)
    mock_get_service.return_value = mock_service

    job_data = {
        "company_name": "Appian",
        "job_title": "Software Engineer Intern",
        "application_status": "Interview Scheduled",
        "email_date": "2026-07-15",
    }
    update_or_append_job("fake_sheet_id", job_data)

    # Should NOT append a new row -- should update the existing one
    mock_service.spreadsheets().values().append.assert_not_called()
    assert mock_service.spreadsheets().values().update.call_count == 2  # status + latest_email_update

    update_calls = mock_service.spreadsheets().values().update.call_args_list
    ranges_written = [c.kwargs["range"] for c in update_calls]
    assert any(COLUMNS["STATUS"] in r for r in ranges_written)
    assert any(COLUMNS["LATEST_EMAIL_UPDATE"] in r for r in ranges_written)
    # Critically: DATE_APPLIED column should NEVER appear in the update calls
    assert not any(f"!{COLUMNS['DATE_APPLIED']}" in r for r in ranges_written)


@patch("services.sheets_service.get_sheets_service")
def test_update_or_append_job_date_applied_never_overwritten_on_update(mock_get_service):
    """Regression test for the original bug: a rejection/interview email
    arriving after the initial application must not touch DATE_APPLIED."""
    existing_rows = [
        ["Appian", "link", "Software Engineer Intern",
         "2026-07-01", "2026-07-01", "Internship", "", "", "McLean, VA", "Applied"],
    ]
    mock_service = _make_mock_service(existing_rows)
    mock_get_service.return_value = mock_service

    job_data = {
        "company_name": "Appian",
        "job_title": "Software Engineer Intern",
        "application_status": "Rejected",
        "email_date": "2026-08-10",  # arrives weeks later
    }
    update_or_append_job("fake_sheet_id", job_data)

    update_calls = mock_service.spreadsheets().values().update.call_args_list
    for call in update_calls:
        assert f"!{COLUMNS['DATE_APPLIED']}" not in call.kwargs["range"]