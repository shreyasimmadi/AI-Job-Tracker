import re
from bs4 import BeautifulSoup

def clean_html(raw_html: str) -> str:
    """
    Takes raw email HTML or body text, strips out styling, scripts, 
    and excessive whitespace to optimize token usage for LLM input.
    """
    if not raw_html:
        return ""
    
    # 1. Parse HTML using BeautifulSoup
    soup = BeautifulSoup(raw_html, "html.parser")
    
    # 2. Remove script and style elements (which contain CSS and Javascript codes)
    for element in soup(["script", "style", "head", "meta"]):
        element.decompose()
        
    # 3. Get clean text from the parsed HTML
    text = soup.get_text(separator=" ")
    
    # 4. Collapse multiple white spaces and newlines into single spaces
    text = re.sub(r'\s+', ' ', text)
    
    # 5. Strip leading and trailing whitespace
    return text.strip()

# Quick manual test to make sure it works if run directly
if __name__ == "__main__":
    test_html = """
    <html>
        <head><style>.button { color: red; }</style></head>
        <body>
            <h1 class="header">Thank you for applying!</h1>
            <p style="display:none;">Tracking Pixel 12345</p>
            <p>We received your application for the <b>Software Engineering Intern</b> position.</p>
        </body>
    </html>
    """
    print("--- Before Cleaning ---")
    print(test_html)
    print("\n--- After Cleaning ---")
    print(clean_html(test_html))