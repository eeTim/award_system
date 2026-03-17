import requests
from bs4 import BeautifulSoup

def scrape_raw_text(url):
    """
    Connects to the given URL using Jina AI Reader to bypass bot protections 
    and extract clean, LLM-friendly markdown text.
    Fallback to traditional requests if Jina fails.
    """
    # 1. Try Jina Reader API (Bypasses most JS/Cloudflare blocks)
    jina_url = f"https://r.jina.ai/{url}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    try:
        response = requests.get(jina_url, headers=headers, timeout=20)
        if response.status_code == 200 and len(response.text) > 100:
            return response.text
            
    except Exception as e:
        print(f"Jina API failed for {url}: {e}")

    # 2. Fallback: Traditional BeautifulSoup if Jina fails
    try:
        response = requests.get(url, headers=headers, timeout=15, verify=False)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        for script_or_style in soup(['script', 'style', 'header', 'footer', 'nav']):
            script_or_style.decompose()
            
        raw_text = soup.get_text(separator=' ')
        lines = (line.strip() for line in raw_text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        return '\n'.join(chunk for chunk in chunks if chunk)
        
    except Exception as e:
        print(f"Fallback scraping failed for {url}: {e}")
        return ""