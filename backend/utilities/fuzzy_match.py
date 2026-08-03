import re
from typing import Dict, Optional, Any
from urllib.parse import urlparse

from rapidfuzz import fuzz

"""
Shared matching utilities for identifying "the same job posting" across
different repos, different table formats, and slightly different wording.

Used by:
- github_service.py: to detect genuinely NEW rows within a single repo
  (comparing this poll's parsed rows against the last-seen snapshot)
- github_service.py: to detect cross-repo duplicates (the same posting
  showing up in 2+ of the 6 tracked repos)
- sheets_service.py: to check whether an incoming Gmail application
  matches an existing row already sitting in the Discovered tab
"""

"""
Below this similarity score two titles are considered different jobs.
Chose 85 to catch near-identical wording (ex. "Software Engineer Intern" vs 
"Software Engineering Intern" scores ~93) while still rejecting clearly different 
roles ("Software Engineer Intern" vs "Data Science Intern" scores well below this).
"""
TITLE_SIMILARITY_THRESHOLD = 85

# Common suffixes stripped 
# For exmaple,"Appian" and "Appian Inc." are treated as the same company. 
# Similar to clean_str() in sheets_service.py so company matching behaves consistently everywhere.

_COMPANY_SUFFIXES = [
    " inc", " bio", " llc", " corp", " corporation", " ltd",
    " technologies", " technology", " tech",
]


from urllib.parse import urlparse


def strip_tracking_params(url: str | None) -> str:
    """
    Strips query-string tracking params and fragments off a URL, leaving just scheme + host + path.

    This lets us know if two links from different repos are the same job posting,
    even though each repo's bot appends its own tracking tag.

    Example:
        Original: "https://job-boards.greenhouse.io/appian/jobs/8041237?utm_source=Simplify#apply"
        Cleaned: "https://job-boards.greenhouse.io/appian/jobs/8041237"
    """
    if not url or not url.strip():
        return ""

    cleaned_url = url.strip()
    parsed = urlparse(cleaned_url)

    # Fall back to original trimmed string if scheme or host is missing
    if not parsed.scheme or not parsed.netloc:
        return cleaned_url

    path = parsed.path.rstrip("/")
    return f"{parsed.scheme}://{parsed.netloc}{path}"


def clean_company(name: Optional[str]) -> str:
    """
    Cleans a company name for comparison: lowercase, strip whitespace and common suffixes.
    """
    if not name:
        return ""
    cleaned = name.strip().lower()
    for suffix in _COMPANY_SUFFIXES:
        cleaned = cleaned.replace(suffix, "")
    return cleaned.strip()


def clean_title(title: Optional[str]) -> str:
    """
    Makes title lowercase and strips whitespaces for comparison.
    """
    if not title:
        return ""
    return re.sub(r"\s+", " ", title.strip().lower())


def clean_location(location: str | None) -> str:
    """
    Cleans location string for comparison.

    Handles HTML line-break artifacts (<br>, </br>, <br/>) and general
    whitespace/case normalization.
    """
    if not location:
        return ""

    # Replaces HTML line breaks (<br>, </br>, <br />) with a comma + space
    normalized = re.sub(r"<\s*/?\s*br\s*/?\s*>", ", ", location, flags=re.IGNORECASE)

    # Gets rid of repeated commas and turns surrounding whitespace into a single ", "
    normalized = re.sub(r"(\s*,\s*)+", ", ", normalized)

    # Changes multiple spaces/tabs into a single space
    normalized = re.sub(r"\s+", " ", normalized)

    # Strips leading/trailing spaces and commas, then lowercase
    return normalized.strip(" ,").lower()


def titles_match(title_a: Optional[str], title_b: Optional[str]) -> bool:
    """
    Compares two job titles and returns True if they're similar enough to
    be considered the same role (e.g. "Software Engineer Intern" vs
    "Software Engineering Intern"), and returns False if they're likely different roles.
    """
    a = (title_a or "").strip().lower()
    b = (title_b or "").strip().lower()
    if not a or not b:
        return False
    
    # token_set_ratio ignores word order and extra appended tags
    return fuzz.token_set_ratio(a, b) >= TITLE_SIMILARITY_THRESHOLD


def is_valid_http_url(url: str | None) -> bool:
    """
    Helper to verify a string is a real web address.
    """
    return bool(url and url.startswith(("http://", "https://")))


def row_identity_key(row: dict[str, Any]) -> str:
    """
    Produces single string identifying the job. 
    Used to detect duplicates via exact comparison (e.g. in a set or dict).

    Primary identity: stripped application link, since a job ID inside
    URL is more reliable than title text.

    Falls back to "company|title|location" if  no usable link present.
    """
    raw_link = row.get("link")
    link_key = strip_tracking_params(raw_link) if raw_link else ""

    # Ensure link_key is a true HTTP/HTTPS URL, not a fallback string like "N/A"
    if link_key and is_valid_http_url(link_key):
        return link_key

    # Fallback to metadata "company|title|location" if no usable link
    company = clean_company(row.get("company"))

    raw_title = row.get("title") or ""
    title = re.sub(r"\s+", " ", raw_title).strip().lower()

    location = clean_location(row.get("location"))

    return f"{company}|{title}|{location}"


def is_same_job(row_a: dict[str, Any], row_b: dict[str, Any]) -> bool:
    """
    The checking different repos incase they have same job posting.

    Check 1: Check if stripped links match exactly? If yes then they're same job.

    Check 2: Runs if links don't match. Requires company match AND
    fuzzy title match AND overlapping location match.
    """
    # Primary Check: Direct URL Match
    link_a = strip_tracking_params(row_a.get("link"))
    link_b = strip_tracking_params(row_b.get("link"))

    if (
        is_valid_http_url(link_a)
        and is_valid_http_url(link_b)
        and link_a == link_b
    ):
        return True

    # Fallback Check: Metadata Similarity

    # Company check (Must match exactly after cleaning)
    company_a = clean_company(row_a.get("company"))
    company_b = clean_company(row_b.get("company"))
    if not company_a or not company_b or company_a != company_b:
        return False

    # Title check (Fuzzy match)
    if not titles_match(row_a.get("title"), row_b.get("title")):
        return False

    # Location check (Flexible comparison)
    loc_a = clean_location(row_a.get("location"))
    loc_b = clean_location(row_b.get("location"))

    # If both locations exist, check if one contains the other (e.g. "san francisco" in "san francisco, ca")
    # or if they match directly.
    if loc_a and loc_b:
        locations_overlap = loc_a in loc_b or loc_b in loc_a
        if not locations_overlap:
            return False
    elif bool(loc_a) != bool(loc_b):
        # One row has a location specified while the other is completely empty
        return False

    return True