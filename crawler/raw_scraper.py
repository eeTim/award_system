import requests
from bs4 import BeautifulSoup

def scrape_raw_text(url):
    """
    Connects to the given URL, bypasses basic bot protections, 
    and extracts only the clean, readable text from the HTML structure.
    """
    # Pretend to be a normal web browser (Chrome) to avoid being blocked
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status() 
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Remove unwanted elements (scripts, styles, hidden tags)
        for script_or_style in soup(['script', 'style', 'header', 'footer', 'nav']):
            script_or_style.decompose()
            
        # Extract pure text and clean up whitespaces
        raw_text = soup.get_text(separator=' ')
        lines = (line.strip() for line in raw_text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        cleaned_text = '\n'.join(chunk for chunk in chunks if chunk)
        
        return cleaned_text
        
    except Exception as e:
        print(f"Error while scraping {url}: {e}")
        return ""