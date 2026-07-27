"""
Shared mock data for offline Pytest suite.
Contains raw HTML samples, fake Gemini JSON outputs, and mock Google Sheet rows.
"""

MOCK_RAW_HTML_EMAIL = """
<html>
  <head><style>body { font-family: Arial; color: #333; }</style></head>
  <body>
    <h2>Thank you for applying to Google!</h2>
    <p>We received your application for the <b>Software Engineer Intern</b> position.</p>
    <p>Application ID: 987654</p>
  </body>
</html>
"""

MOCK_GEMINI_RESPONSE_JSON = """
{
  "company_name": "Google",
  "job_title": "Software Engineer Intern",
  "date_applied": "2026-07-23",
  "type_of_job": "Internship",
  "application_status": "Applied"
}
"""

MOCK_SHEET_ROWS = [
    ["Company Name", "Job Link", "Job Title", "Date Applied"],           # Row 1 (Header)
    ["Google", "https://google.com/jobs/1", "Software Engineer Intern"], # Row 2
    ["Meta", "https://meta.com/jobs/2", "Frontend Engineer"],            # Row 3
    ["Amazon", "", "AWS Cloud Intern"]                                  # Row 4
]

MOCK_GMAIL_MESSAGES_LIST = [
    {"id": "msg_001", "threadId": "thread_001"},
    {"id": "msg_002", "threadId": "thread_002"},
    {"id": "msg_001", "threadId": "thread_001"}  # Intentional duplicate ID
]

MOCK_MESSY_HTML_EMAIL = """
<html>
  <head>
    <style>body { font-family: Arial; }</style>
    <script>console.log("tracking pixel");</script>
  </head>
  <body>
    <div>
      <!-- Comment -->
      <h1>Application Received</h1>
      <p>Thanks for applying to <b>Palantir Technologies</b>!</p>
      <img src="https://tracking.com/pixel.gif" alt="" />
    </div>
  </body>
</html>
"""

MOCK_MARKDOWN_WRAPPED_JSON = """```json
{
  "company_name": "Palantir",
  "job_title": "Forward Deployed Engineer Intern",
  "date_applied": "2026-07-23",
  "type_of_job": "Internship",
  "application_status": "Applied"
}
```"""

MOCK_PUNCTUATION_SHEET_ROWS = [
    ["Company Name", "Job Link", "Job Title", "Date Applied"],
    ["Google, Inc.", "https://google.com/jobs/1", "Software Engineer - Intern"], # Row 2
    ["Meta Platforms", "https://meta.com/jobs/2", "Frontend Engineer"],          # Row 3
]