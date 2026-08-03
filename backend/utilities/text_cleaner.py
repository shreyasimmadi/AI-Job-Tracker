import re
from bs4 import BeautifulSoup


def clean_html(raw_html: str) -> str:
    """
    Takes raw email HTML or body text, strips out ERB/Ruby template tags,
    styling, scripts, and excessive whitespace to optimize token usage for LLM input.
    """
    if not raw_html:
        return ""
    
    # 1. Strip ERB/Ruby template code blocks like <% ... %> that leak from email headers
    cleaned = re.sub(r'<%.*?%>', '', raw_html, flags=re.DOTALL)
    
    # 2. Parse HTML using BeautifulSoup
    soup = BeautifulSoup(cleaned, "html.parser")
    
    # 3. Remove script, style, head, and meta elements
    for element in soup(["script", "style", "head", "meta"]):
        element.decompose()
        
    # 4. Get clean text from the parsed HTML
    text = soup.get_text(separator=" ")
    
    # 5. Collapse multiple white spaces and newlines into single spaces
    text = re.sub(r'\s+', ' ', text)
    
    # 6. Strip leading and trailing whitespace
    return text.strip()


# Quick manual test to make sure ERB tags and HTML are stripped
if __name__ == "__main__":
    test_erb_html = """
    <% is_all_params_exists = X::EmployerBrandingHelper.supports_email_branding?(@test_obj.company) bg_color = X::EmployerB %>
    <html>
        <head><style>.button { color: red; }</style></head>
        <body>
            <h1 class="header">Thank you for applying!</h1>
            <p>We received your application for the <b>Software Engineering Intern</b> position.</p>
        </body>
    </html>
    """
    print("--- Before Cleaning ---")
    print(test_erb_html)
    print("\n--- After Cleaning ---")
    print(clean_html(test_erb_html))