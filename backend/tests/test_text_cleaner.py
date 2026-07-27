import pytest
from utilities.text_cleaner import clean_html
from tests.mock_data import MOCK_RAW_HTML_EMAIL, MOCK_MESSY_HTML_EMAIL

def test_clean_html_removes_tags_and_css():
    """Verifies that clean_html strips <style> blocks and HTML tags."""
    cleaned_text = clean_html(MOCK_RAW_HTML_EMAIL)

    assert "<style>" not in cleaned_text
    assert "<h2>" not in cleaned_text
    assert "<b>" not in cleaned_text
    assert "Thank you for applying to Google!" in cleaned_text
    assert "Software Engineer Intern" in cleaned_text

def test_clean_html_strips_scripts_and_comments():
    cleaned = clean_html(MOCK_MESSY_HTML_EMAIL)
    assert "<script>" not in cleaned
    assert "console.log" not in cleaned
    assert "Thanks for applying to" in cleaned
    assert "Palantir Technologies" in cleaned

def test_clean_html_handles_empty_input():
    assert clean_html("") == ""
    assert clean_html(None) == ""