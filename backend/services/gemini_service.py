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
        description="Set to TRUE if this email is a legitimate job application confirmation, interview invite, assessment, rejection, status update, or job offer. Set to FALSE for newsletters, marketing, promo emails, or non-job updates."
    )
    company_name: str = Field(
        default="", 
        description="Name of the company or organization (e.g. BalanX, Google, Robinhood). Extract from text, email sender, or signatures."
    )
    job_link: Optional[str] = Field(
        default="", 
        description="URL to the job posting if explicitly provided in the email."
    )
    job_title: str = Field(
        default="Internship", 
        description="Title of the role or position (e.g., 'Software Engineering Intern', 'Data Analyst')."
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
    CLASSIFICATION RULES:
    1. Set `is_job_application` to TRUE if the email is a job application submission confirmation, interview invitation, assessment link, decision update, rejection, OR A JOB OFFER.
    2. Set `is_job_application` to TRUE for ANY email from companies like Capital One, Google, etc. containing assessment invitations, Virtual Job Tryout (VJT) links, CodeSignal, or HackerRank assessments—even if 90% of the text is instructional/FAQ boilerplate.
    3. Set `is_job_application` to FALSE ONLY for purely marketing emails, job alerts/recommendations, weekly newsletters, general account creations, or password resets.
    4. IMPORTANT: Many assessment-invite emails open with a generic phrase like "Thank you for your interest in [Company]" and then spend most of their length on instructional/FAQ-style content (platform requirements, proctoring rules, browser compatibility, backup network tips, "learn more" links) rather than personalized language. Do NOT classify these as FALSE just because the bulk of the email reads like generic instructions -- if the underlying purpose is inviting the candidate to complete a hiring assessment or next step, it is TRUE regardless of how much boilerplate surrounds it.
    5. Recognize common third-party hiring assessment platforms as strong signals of a real job application email, even if the email itself never uses the words "job" or "application": CodeSignal, HackerRank, Virtual Job Tryout, HireVue, Pymetrics, Karat, Codility, and similar coding/assessment platforms.

    EXTRACTION BOUNDARY RULE (critical -- read carefully):
    The platforms named above (CodeSignal, HackerRank, Virtual Job Tryout, HireVue, Pymetrics, Karat, Codility, etc.) are THIRD-PARTY TESTING VENDORS used to administer an assessment. They are NEVER the hiring company. Regardless of how prominently a testing platform's name appears in the email:
    - `company_name` must always be the actual employer/organization the candidate applied to (e.g. "Capital One", "Google") -- NEVER a testing vendor's name, even if the vendor name is mentioned far more often in the email than the employer's name.
    - `contact_info` must never be a testing vendor's generic support address (e.g. anything ending in @hackerrank.com, @codesignal.com, @myworkday.com support domains, etc.). If no genuine recruiter/company contact is present in the email, leave `contact_info` blank rather than substituting the vendor's support email.
    - The employer's name is typically mentioned early in the email (often in the greeting or first sentence, e.g. "Thank you for your interest in ... at Capital One!") -- prioritize that over any vendor name mentioned later in the email body.
    - Ignore generic legal/compliance boilerplate (e.g. AI-usage policies, "termination of employment" warnings, confidentiality notices) when determining `type_of_job`. These are standard disclaimers unrelated to the specific role. Base `type_of_job` only on explicit role-description wording (e.g. "Internship", "Intern", "Summer Analyst", "Full-Time Analyst").

    DATE FORMATTING RULES:
    - `date_applied` MUST be formatted as YYYY-MM-DD (e.g., 2026-07-26).
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