import os
from typing import Optional, Literal
from pydantic import BaseModel, Field
from google import genai
from google.genai import types
from dotenv import load_dotenv

# Load environment variables from backend/.env
load_dotenv()

# Initialize the official Google GenAI Client
# Automatically detects GEMINI_API_KEY from the environment
client = genai.Client()

# Define the exact blueprint matching your Google Sheet columns
class JobApplicationData(BaseModel):
    is_job_application: bool = Field(
        description=(
            "Set to TRUE for ANY job application confirmation, interview invite, assessment link/invitation "
            "(e.g., Capital One Virtual Job Tryout, HackerRank, CodeSignal, HireVue), status update, rejection, "
            "or offer. Set to FALSE ONLY for marketing emails, job alerts, newsletters, or password resets."
        )
    )
    company_name: str = Field(
        default="", 
        description="The ACTUAL hiring employer/company (e.g. 'JPMorgan', 'JPMorganChase', 'Capital One'). "
            "NEVER use third-party testing platform names like 'HackerRank', 'CodeSignal', or 'HireVue'."
    )
    job_link: Optional[str] = Field(
        default="", 
        description="URL to the job posting if explicitly provided in the email."
    )
    job_title: str = Field(
        default="Internship", 
        description="The specific job or program title. For assessment invites with generic titles "
            "(e.g., 'NAMR Software Engineer Program - Campus Hiring - 2027'), shorten or extract "
            "the core program name (e.g., 'Software Engineer Program' or 'Summer Internship') "
            "so fuzzy matching can match existing applications."
    )
    date_applied: str = Field(
        default="", 
        description="Date the application was submitted or the email date formatted strictly as YYYY-MM-DD. Always convert dates like 'July 26' or 'today' into YYYY-MM-DD."
    )
    
    # Matches Google Sheet 'Type of Job' dropdown choices
    type_of_job: Literal["Full-Time", "Part-Time", "Freelance", "Contract", "Internship", "Other"] = Field(
        default="Internship", 
        description="Employment type (e.g. Internship, Full-Time)."
    )
    
    salary: Optional[str] = Field(
        default="", 
        description="Salary, hourly rate, or compensation details if mentioned."
    )
    contact_info: Optional[str] = Field(
        default="", 
        description="Recruiter or contact person's email address or LinkedIn URL if available."
    )
    location: Optional[str] = Field(
        default="", 
        description="Job location (e.g., 'Remote', 'Hybrid', or 'City, State')."
    )
    
    # MUST MATCH exact Google Sheet dropdown values:
    application_status: Literal[
        "Not Started", "Applied", "OA", "Interview Scheduled", 
        "Interviewed", "Accepted", "Rejected", "No Reply", "Offer Received"
    ] = Field(
        default="Applied",
        description="Current application status derived from the email context."
    )


def parse_job_email(clean_email_text: str) -> JobApplicationData:
    """
    Parses clean email body text with Gemini and extracts structured job application data.
    """
    prompt = f"""
        Analyze the following email body regarding a candidate's job application, interview, or offer update.

        CLASSIFICATION RULES:
        1. Set `is_job_application` to TRUE if the email is a job application submission confirmation, interview invitation, assessment link, decision update, rejection, OR A JOB OFFER.
        2. Set `is_job_application` to TRUE for ANY email from companies like Capital One, JPMorgan, Google, etc. containing assessment invitations, Virtual Job Tryout (VJT) links, CodeSignal, or HackerRank assessments—even if 90% of the text is instructional/FAQ boilerplate or contains raw template tags.
        3. Set `is_job_application` to FALSE ONLY for purely marketing emails, job alerts/recommendations, weekly newsletters, general account creations, or password resets.
        4. IMPORTANT: Ignore any raw HTML, CSS, or Ruby/ERB template tags (e.g. `<% is_all_params_exists = ... %>`) that appear at the beginning or end of the text payload. Focus strictly on human-readable text.
        5. Recognize common third-party hiring assessment platforms as strong signals of a real job application email, even if the email itself never uses the words "job" or "application": CodeSignal, HackerRank, Virtual Job Tryout, HireVue, Pymetrics, Karat, Codility, and similar coding/assessment platforms.

        EXTRACTION BOUNDARY & TITLE NORMALIZATION RULES (critical -- read carefully):
        1. EMPLOYER vs VENDOR:
        - CodeSignal, HackerRank, Virtual Job Tryout, HireVue, etc. are THIRD-PARTY TESTING VENDORS. They are NEVER the hiring company.
        - `company_name` must ALWAYS be the actual employer/organization hiring the candidate (e.g., "JPMorgan", "JPMorganChase", "Capital One", "Google") -- NEVER "HackerRank" or "CodeSignal".
        - Determine `company_name` by looking at the email subject line, header, or the opening sentence (e.g., "To keep your application for the JPMorganChase position moving forward..."). Prioritize this employer over any testing vendor mentioned in the body.
        2. JOB TITLE NORMALIZATION FOR ASSESSMENTS:
        - For assessment/testing emails that use generic or internal program titles (e.g. "JPMorganChase – NAMR Software Engineer Program – Campus Hiring – 2027"), shorten or strip non-essential internal codes/tags so the title simplifies to the core role (e.g., "Software Engineer Program" or "Summer Internship").
        - This ensures fuzzy-matching logic can match the assessment update to an existing job application row on the candidate's spreadsheet.
        3. CONTACT INFO & DISCLAIMERS:
        - `contact_info` must NEVER be a vendor's generic support email (e.g. support@hackerrank.com, support@codesignal.com, etc.). If no direct company/recruiter contact is given, leave `contact_info` blank ("").
        - Ignore generic legal/compliance disclaimers when determining `type_of_job`. Base `type_of_job` strictly on explicit role wording (e.g. "Internship", "Full-Time").

        DATE FORMATTING RULES:
        - `date_applied` MUST be formatted as YYYY-MM-DD (e.g., 2026-08-03).
        - Do not output relative strings like "Today" or text dates like "July 26th". Always format as numerical YYYY-MM-DD.

        STATUS MAPPING RULES (Map strictly to these exact Google Sheet dropdown string values):
        - If the email contains a job offer, official offer letter, or congratulations on an offer -> "Offer Received"
        - If the email confirms you formally accepted the job -> "Accepted"
        - If the email invites you to complete an online assessment, technical assessment, coding challenge, or coding test (NOT a live interview) -> "OA". This includes emails that mention completing an assessment on CodeSignal, HackerRank, Virtual Job Tryout, HireVue, Pymetrics, Karat, Codility, or similar third-party platforms, even if the email is phrased as a "thank you for applying" or confirmation-style message rather than explicitly saying "assessment."
        - If the email invites to a live interview, phone screen, or on-site/virtual interview -> "Interview Scheduled"
        - If the email is a rejection or non-selection notice -> "Rejected"
        - If the email is an initial application submission confirmation -> "Applied"
        - Otherwise default to -> "Applied"

        Email Content:
        {clean_email_text}
        """

    response = client.models.generate_content(
        model='gemini-3.5-flash-lite',
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=JobApplicationData,
        ),
    )

    return JobApplicationData.model_validate_json(response.text)