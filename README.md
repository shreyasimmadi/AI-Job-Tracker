# AI Job Tracker Backend

An automated background engineering pipeline built with Python, FastAPI, and APScheduler. It scans incoming emails via the Gmail API, parses job application statuses using Google Gemini, and synchronizes application data in real time with Google Sheets.

Contributors: Shreyas Immadi

## What it does

- **Scan** incoming job confirmation emails via the Gmail API — filtered automatically under the `Job-Tracker` label.
- **Extract & Clean** — recursively decodes MIME parts and strips raw HTML markup into streamlined text snippets.
- **Parse with AI** — passes cleaned body text into Gemini 3.5 Flash Lite with Pydantic schema enforcement to extract structured data (company, title, status, deadlines, location, job type).
- **Deduplicate** — uses an O(1) in-memory hash set to skip duplicate email payloads instantly during execution.
- **Sync to Sheets** — runs composite string matching logic to either update existing application statuses or append formatted new entries with native `YYYY-MM-DD` calendar-triggering dates and dropdown status chips.

## Tech stack

- Python 3.10+
- FastAPI + Uvicorn
- APScheduler (BackgroundScheduler)
- Google Gemini API (`gemini-3.5-flash-lite`), Pydantic
- Gmail API, Google Sheets API (Google Auth / OAuth 2.0)
- `python-dotenv`

## Prerequisites

- Python 3.10 or higher
- A Google Cloud Platform (GCP) project with **Gmail API** and **Google Sheets API** enabled
- OAuth 2.0 Client credentials downloaded from GCP (`credentials.json`)
- API keys for:
  - Google Gemini (`GEMINI_API_KEY`)

## Setup

## 1. Clone the repo and navigate to the project directory:

    git clone https://github.com/your-username/ai-job-tracker-backend.git
    cd ai-job-tracker-backend

## 2. Create and activate a Python virtual environment:

      python3 -m venv venv
      source venv/bin/activate   
      On Windows: venv\Scripts\activate

## 3. Install dependencies:

      pip install -r requirements.txt

## 4. Place your GCP OAuth credentials inside the `config/` directory:

      config/credentials.json

## 5. Add your environment variables. Create a `.env` file in the project root:

      GEMINI_API_KEY=your_gemini_api_key
      GOOGLE_SHEET_ID=your_google_sheet_id
      CHECK_INTERVAL_MINUTES=15

## Running the app

Start the development server with Uvicorn:

      uvicorn main:app --reload

On initial launch, a browser window will open requesting OAuth consent for Gmail and Sheets access. Upon approval, authentication tokens are cached to `config/token.json`.

The background scheduler will run an immediate scan on startup, then repeat every 15 minutes automatically.

## Using the app

1. **Verify server status.** Visit `http://127.0.0.1:8000/` in your browser to confirm the FastAPI backend is online.
2. **Trigger manual scan.** Navigate to `http://127.0.0.1:8000/trigger` to instantly trigger an email scanning cycle outside of the 15-minute interval.
3. **Check Google Sheets.** View your updated spreadsheet rows—application statuses update dynamically and new applications auto-populate with formatted `YYYY-MM-DD` calendar dates and status dropdown chips.

## Project structure

    config/
      credentials.json     # GCP OAuth client configuration (Git-ignored)
      token.json           # Cached OAuth user tokens (Git-ignored)
    services/
      gemini_service.py    # Gemini schema definition & structured extraction
      gmail_service.py     # Gmail API authentication, email fetching & MIME decoding
      sheets_service.py    # Google Sheets API client & row updating logic
    utilities/
      text_cleaner.py      # HTML stripping & payload cleaning helpers
    .env.example           # Environment template file
    .gitignore             # Excludes keys, tokens, environments, and caches
    main.py                # FastAPI app instance, lifespans & APScheduler background loop
    requirements.txt       # Python package dependencies

## Scripts

- `uvicorn main:app --reload` — start FastAPI development server with hot-reloading
- `python main.py` — execute direct script entry point

## Troubleshooting

- **Missing credentials error** — verify `credentials.json` is located inside the `config/` directory.
- **Gmail date offset by 1 day** — verify system local time versus UTC offsets in `gmail_service.py`.
- **Rate-limited by Gemini** — pipeline automatically handles retry intervals between batch parsing calls.

## Version History & Roadmap

- **v1.0.0 (Current)** — Automated Gmail polling, Gemini Pydantic parsing, Google Sheets integration, and local timezone handling.
- **v2.0.0 (Planned)** — Persistent SQLite/PostgreSQL database storage, web dashboard for application metrics, automated rejection analytics, and interview calendar reminders.