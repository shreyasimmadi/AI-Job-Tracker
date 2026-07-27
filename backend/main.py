import os
import time
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI
from apscheduler.schedulers.background import BackgroundScheduler

from services.gmail_service import fetch_unread_job_emails
from utilities.text_cleaner import clean_html
from services.gemini_service import parse_job_email
from services.sheets_service import update_or_append_job

# Load environment variables (.env)
load_dotenv()

GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
CHECK_INTERVAL_MINUTES = int(os.getenv("CHECK_INTERVAL_MINUTES", 15))


def run_pipeline() -> dict:
    """
    Core Pipeline Execution Task.
    Fetches emails, cleans HTML, parses with Gemini, and updates Google Sheet.
    """
    print("\n[Pipeline] 🚀 Running job tracker pipeline check...")
    
    if not GOOGLE_SHEET_ID:
        print("[Pipeline Error] ❌ GOOGLE_SHEET_ID environment variable is missing in .env!")
        return {"status": "error", "message": "GOOGLE_SHEET_ID is missing."}

    processed_count = 0

    try:
        # 1. Fetch matching emails from Gmail API
        emails = fetch_unread_job_emails(max_results=10)
        
        if not emails:
            print("[Pipeline] 📭 No new job emails found.")
            return {"status": "success", "processed": 0, "message": "No new job emails found."}

        print(f"[Pipeline] 📬 Found {len(emails)} matching email(s). Processing...")

        # 2. Iterate through fetched emails
        for email in emails:
            msg_id = email["id"]
            raw_body = email["raw_body"]
            email_date = email.get("email_date", "")

            # Prefer clean_html; fallback to raw_body if HTML cleaner strips all text
            clean_text = clean_html(raw_body)
            if not clean_text.strip() and raw_body.strip():
                clean_text = raw_body.strip()

            if not clean_text.strip():
                print(f"[Pipeline] ⚠️ Skipping email ID {msg_id}: Empty text payload.")
                continue

            print(f"\n[Pipeline] 🤖 Parsing email ID {msg_id} (Length: {len(clean_text)} chars)...")
            print(f"[Snippet Preview]: {clean_text[:120]}...")

            # Parse email payload with Gemini structured outputs
            extracted_job = parse_job_email(clean_text)

            if extracted_job:
                print(
                    f"[Debug] Extracted -> Company: '{extracted_job.company_name}' "
                    f"| Title: '{extracted_job.job_title}' "
                    f"| Status: '{extracted_job.application_status}' "
                    f"| IsJob: {extracted_job.is_job_application}"
                )

            if extracted_job and extracted_job.is_job_application and extracted_job.company_name:
                job_dict = extracted_job.model_dump()
                
                # Enforce the internal Gmail timestamp as ground truth for application date
                job_dict["date_applied"] = email_date

                print(f"[Pipeline] 📊 Updating Google Sheet for {extracted_job.company_name} - {extracted_job.job_title}...")
                update_or_append_job(GOOGLE_SHEET_ID, job_dict)
                processed_count += 1
            else:
                print(f"[Pipeline] ⏭️ Skipped non-job email or missing company details.")

            # Short delay between API processing steps
            time.sleep(2)

        print(f"[Pipeline] ✅ Processing complete! ({processed_count} records processed)")
        return {"status": "success", "processed": processed_count}

    except Exception as e:
        print(f"[Pipeline Error] ❌ An error occurred during pipeline run: {e}")
        return {"status": "error", "message": str(e)}


# Initialize APScheduler for automated cron runs
scheduler = BackgroundScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI Lifespan event: starts scheduler on startup and shuts it down cleanly."""
    print(f"[Server Startup] Starting background scheduler (Interval: {CHECK_INTERVAL_MINUTES} mins)...")
    
    # Run once immediately on server launch
    run_pipeline()
    
    # Schedule repeating background task
    scheduler.add_job(run_pipeline, 'interval', minutes=CHECK_INTERVAL_MINUTES)
    scheduler.start()
    
    yield
    
    print("[Server Shutdown] Stopping background scheduler...")
    scheduler.shutdown()


# Initialize FastAPI Web Application
app = FastAPI(title="AI Job Tracker API", version="1.0.0", lifespan=lifespan)

@app.get("/")
def read_root():
    return {
        "status": "online",
        "service": "AI Job Tracker Backend",
        "version": "1.0.0"
    }

@app.get("/trigger")
def trigger_manual_run():
    """Manual endpoint to trigger the email scanner on demand."""
    result = run_pipeline()
    return {"trigger": "manual", "result": result}