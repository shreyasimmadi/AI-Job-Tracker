import pytest
from utilities.fuzzy_match import (
    strip_tracking_params,
    clean_company,
    clean_title,
    clean_location,
    titles_match,
    is_valid_http_url,
    row_identity_key,
    is_same_job,
)


# --- strip_tracking_params ---

def test_strip_tracking_params_removes_query_string():
    url = "https://job-boards.greenhouse.io/appian/jobs/8041237?utm_source=Simplify&ref=Simplify"
    assert strip_tracking_params(url) == "https://job-boards.greenhouse.io/appian/jobs/8041237"


def test_strip_tracking_params_removes_fragment():
    url = "https://job-boards.greenhouse.io/appian/jobs/8041237?utm_source=Simplify#apply"
    assert strip_tracking_params(url) == "https://job-boards.greenhouse.io/appian/jobs/8041237"


def test_strip_tracking_params_different_query_same_path():
    """The exact real-world Appian case: same job, two different repos' tracking tags."""
    simplify_link = "https://job-boards.greenhouse.io/appian/jobs/8041237?utm_source=Simplify&ref=Simplify"
    vansh_link = "https://job-boards.greenhouse.io/appian/jobs/8041237?utm_source=github-vansh-ouckah"
    assert strip_tracking_params(simplify_link) == strip_tracking_params(vansh_link)


def test_strip_tracking_params_no_query_string():
    url = "https://jobs.smartrecruiters.com/WesternDigital/744000138727213"
    assert strip_tracking_params(url) == url


def test_strip_tracking_params_trailing_slash_normalized():
    assert strip_tracking_params("https://example.com/jobs/123/") == "https://example.com/jobs/123"


def test_strip_tracking_params_empty_none_whitespace():
    assert strip_tracking_params("") == ""
    assert strip_tracking_params(None) == ""
    assert strip_tracking_params("   ") == ""


def test_strip_tracking_params_malformed_url_falls_back_gracefully():
    assert strip_tracking_params("not a url") == "not a url"


# --- clean_company ---

def test_clean_company_strips_suffix_and_case():
    assert clean_company("Appian Inc") == "appian"
    assert clean_company("Meta Technologies") == "meta"


def test_clean_company_strips_bio_suffix():
    assert clean_company("Moderna Bio") == "moderna"


def test_clean_company_handles_none_and_empty():
    assert clean_company(None) == ""
    assert clean_company("") == ""


def test_clean_company_whitespace_normalized():
    assert clean_company("  Google  ") == "google"


# --- clean_title ---

def test_clean_title_lowercases_and_strips_whitespace():
    assert clean_title("  Software   Engineer   Intern  ") == "software engineer intern"


def test_clean_title_does_not_strip_business_suffixes():
    """Unlike clean_company, clean_title should NOT apply suffix-stripping --
    titles aren't company names, so 'Corp' or 'Inc' inside a title (if it
    ever happened) shouldn't be touched."""
    assert clean_title("Corporate Strategy Intern") == "corporate strategy intern"


def test_clean_title_handles_none_and_empty():
    assert clean_title(None) == ""
    assert clean_title("") == ""


# --- clean_location ---

def test_clean_location_normalizes_br_tags():
    assert clean_location("Austin, TX<br>NYC") == "austin, tx, nyc"
    assert clean_location("Austin, TX</br>New York") == "austin, tx, new york"


def test_clean_location_collapses_repeated_commas():
    assert clean_location("McLean, VA,, Remote") == "mclean, va, remote"


def test_clean_location_case_and_whitespace():
    assert clean_location("  McLean, VA  ") == "mclean, va"


def test_clean_location_empty_or_none():
    assert clean_location(None) == ""
    assert clean_location("") == ""


# --- is_valid_http_url ---

def test_is_valid_http_url_accepts_http_and_https():
    assert is_valid_http_url("https://example.com/jobs/1") is True
    assert is_valid_http_url("http://example.com/jobs/1") is True


def test_is_valid_http_url_rejects_non_url_placeholder():
    assert is_valid_http_url("N/A") is False
    assert is_valid_http_url("") is False
    assert is_valid_http_url(None) is False


def test_is_valid_http_url_rejects_other_schemes():
    assert is_valid_http_url("ftp://example.com/file") is False


# --- titles_match (token_set_ratio) ---

def test_titles_match_near_identical_wording():
    """The exact Appian case: 'Engineer' vs 'Engineering'."""
    assert titles_match("Software Engineer Intern", "Software Engineering Intern") is True


def test_titles_match_identical():
    assert titles_match("Data Scientist Intern", "Data Scientist Intern") is True


def test_titles_match_ignores_trailing_qualifier():
    """token_set_ratio should still match despite an appended qualifier."""
    assert titles_match(
        "Software Engineering Intern - Summer 2027",
        "Software Engineering Intern",
    ) is True


def test_titles_match_rejects_different_roles():
    assert titles_match("Software Engineer Intern", "Data Science Intern") is False


def test_titles_match_rejects_hardware_vs_software():
    assert titles_match("Software Engineer Intern", "Hardware Engineer Intern") is False


def test_titles_match_empty_strings():
    assert titles_match("", "Software Engineer Intern") is False
    assert titles_match(None, None) is False


# --- row_identity_key ---

def test_row_identity_key_uses_stripped_link_when_available():
    row = {
        "company": "Appian",
        "title": "Software Engineer Intern",
        "location": "McLean, VA",
        "link": "https://job-boards.greenhouse.io/appian/jobs/8041237?utm_source=Simplify",
    }
    assert row_identity_key(row) == "https://job-boards.greenhouse.io/appian/jobs/8041237"


def test_row_identity_key_ignores_non_url_link_and_falls_back():
    """A placeholder like 'N/A' in the link field shouldn't be treated as a
    real identity -- should fall back to company|title|location instead."""
    row = {
        "company": "Appian Inc",
        "title": "Software Engineer Intern",
        "location": "McLean, VA",
        "link": "N/A",
    }
    assert row_identity_key(row) == "appian|software engineer intern|mclean, va"


def test_row_identity_key_falls_back_without_link():
    row = {
        "company": "Appian Inc",
        "title": "Software Engineer Intern",
        "location": "McLean, VA",
        "link": "",
    }
    assert row_identity_key(row) == "appian|software engineer intern|mclean, va"


def test_row_identity_key_two_repos_same_job_produce_same_key():
    row_simplify = {
        "company": "Appian",
        "title": "Software Engineer Intern",
        "location": "McLean, VA",
        "link": "https://job-boards.greenhouse.io/appian/jobs/8041237?utm_source=Simplify&ref=Simplify",
    }
    row_vansh = {
        "company": "Appian",
        "title": "Software Engineering Intern",  # slightly different wording
        "location": "McLean, VA",
        "link": "https://job-boards.greenhouse.io/appian/jobs/8041237?utm_source=github-vansh-ouckah",
    }
    assert row_identity_key(row_simplify) == row_identity_key(row_vansh)


# --- is_same_job (full dedup check) ---

def test_is_same_job_matches_via_link():
    row_simplify = {
        "company": "Appian",
        "title": "Software Engineer Intern",
        "location": "McLean, VA",
        "link": "https://job-boards.greenhouse.io/appian/jobs/8041237?utm_source=Simplify",
    }
    row_vansh = {
        "company": "Appian",
        "title": "Software Engineering Intern",
        "location": "McLean, VA",
        "link": "https://job-boards.greenhouse.io/appian/jobs/8041237?utm_source=github-vansh-ouckah",
    }
    assert is_same_job(row_simplify, row_vansh) is True


def test_is_same_job_matches_via_fallback_when_links_differ():
    """The critical regression test for the earlier company_a/company_b bug --
    when links don't share an ID (one is a redirect page), the fallback
    company+title+location check must still correctly return True."""
    row_a = {
        "company": "Appian",
        "title": "Software Engineer Intern",
        "location": "McLean, VA",
        "link": "https://job-boards.greenhouse.io/appian/jobs/8041237?utm_source=Simplify",
    }
    row_b = {
        "company": "Appian",
        "title": "Software Engineering Intern",
        "location": "McLean, VA",
        "link": "https://simplify.jobs/p/31b95070-c5a6-4523-b7d4-54fbaa062677",
    }
    assert is_same_job(row_a, row_b) is True


def test_is_same_job_matches_via_fallback_with_substring_location():
    """New behavior: 'San Francisco' should be considered overlapping with
    'San Francisco, CA' rather than requiring an exact string match."""
    row_a = {
        "company": "Meta",
        "title": "Software Engineer Intern",
        "location": "San Francisco",
        "link": "https://example.com/jobs/111",
    }
    row_b = {
        "company": "Meta",
        "title": "Software Engineering Intern",
        "location": "San Francisco, CA",
        "link": "https://simplify.jobs/p/some-redirect-page",
    }
    assert is_same_job(row_a, row_b) is True


def test_is_same_job_rejects_same_company_different_location():
    """RTX posting the same title in two different cities should NOT be
    treated as duplicates of each other."""
    row_anaheim = {
        "company": "RTX",
        "title": "Software Engineer Intern",
        "location": "Anaheim, CA",
        "link": "https://example.com/jobs/111",
    }
    row_mckinney = {
        "company": "RTX",
        "title": "Software Engineer Intern",
        "location": "McKinney, TX",
        "link": "https://example.com/jobs/222",
    }
    assert is_same_job(row_anaheim, row_mckinney) is False


def test_is_same_job_rejects_different_companies():
    row_a = {
        "company": "Appian",
        "title": "Software Engineer Intern",
        "location": "McLean, VA",
        "link": "https://example.com/jobs/111",
    }
    row_b = {
        "company": "Google",
        "title": "Software Engineer Intern",
        "location": "McLean, VA",
        "link": "https://example.com/jobs/222",
    }
    assert is_same_job(row_a, row_b) is False


def test_is_same_job_rejects_different_roles_same_company_and_location():
    row_a = {
        "company": "Appian",
        "title": "Software Engineer Intern",
        "location": "McLean, VA",
        "link": "https://example.com/jobs/111",
    }
    row_b = {
        "company": "Appian",
        "title": "Information Security Engineer Intern",
        "location": "McLean, VA",
        "link": "https://example.com/jobs/222",
    }
    assert is_same_job(row_a, row_b) is False


def test_is_same_job_rejects_when_one_location_missing():
    """One row has a location, the other doesn't -- shouldn't assume a match."""
    row_a = {
        "company": "Appian",
        "title": "Software Engineer Intern",
        "location": "McLean, VA",
        "link": "https://example.com/jobs/111",
    }
    row_b = {
        "company": "Appian",
        "title": "Software Engineering Intern",
        "location": "",
        "link": "https://example.com/jobs/222",
    }
    assert is_same_job(row_a, row_b) is False


def test_is_same_job_handles_missing_fields_gracefully():
    row_a = {"company": "", "title": "", "location": "", "link": ""}
    row_b = {"company": "Appian", "title": "SWE Intern", "location": "VA", "link": ""}
    assert is_same_job(row_a, row_b) is False


def test_is_same_job_ignores_non_url_link_placeholders():
    """A 'link' value like 'N/A' on both sides shouldn't be treated as a
    matching URL -- must fall through to the metadata check."""
    row_a = {
        "company": "Appian",
        "title": "Software Engineer Intern",
        "location": "McLean, VA",
        "link": "N/A",
    }
    row_b = {
        "company": "Appian",
        "title": "Software Engineering Intern",
        "location": "McLean, VA",
        "link": "N/A",
    }
    # Should still match -- but via the fallback metadata check, not the
    # (invalid) link check
    assert is_same_job(row_a, row_b) is True