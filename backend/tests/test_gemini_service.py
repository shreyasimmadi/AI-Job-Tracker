import pytest
from services.gemini_service import JobApplicationData
from tests.mock_data import MOCK_GEMINI_RESPONSE_JSON, MOCK_MARKDOWN_WRAPPED_JSON

def test_job_application_pydantic_schema():
    """Verifies Pydantic schema validation using mock JSON output."""
    data = JobApplicationData.model_validate_json(MOCK_GEMINI_RESPONSE_JSON)

    assert data.company_name == "Google"
    assert data.job_title == "Software Engineer Intern"
    assert data.date_applied == "2026-07-23"
    assert data.type_of_job == "Internship"
    assert data.application_status == "Applied"

def test_pydantic_handles_json_fences():
    # Strip markdown fences if present
    raw_json = MOCK_MARKDOWN_WRAPPED_JSON.strip()
    if raw_json.startswith("```json"):
        raw_json = raw_json.removeprefix("```json").removesuffix("```").strip()
        
    data = JobApplicationData.model_validate_json(raw_json)
    assert data.company_name == "Palantir"
    assert data.job_title == "Forward Deployed Engineer Intern"