import urllib.parse
import os
import json
import requests
import PyPDF2
from google import genai
from google.genai import types
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure Gemini API using the NEW official SDK
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=GEMINI_API_KEY)

SERPER_API_KEY = os.getenv("SERPER_API_KEY")

def extract_text_from_pdf(pdf_path):
    """
    [Explanation] Extracts text from a PDF file.
    """
    text = ""
    try:
        with open(pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            for page in reader.pages:
                text += page.extract_text() + "\n"
        return text
    except Exception as e:
        print(f"PDF reading error: {e}")
        return ""

def get_search_keywords_from_ai(theme_text):
    """
    [Explanation] Gemini API (New SDK): Generates Google search queries in JSON format.
    """
    prompt = f"""
    You are an expert researcher. Based on the following award theme and criteria, 
    generate 3 specific Google search queries to find global and local awarding institutions, fellowships, or foundations related to this theme.
    Return ONLY a valid JSON array of strings.
    Example: ["climate change activist award", "human rights fellowship africa", "global peace prize institutions"]
    
    Theme Text:
    {theme_text[:2000]}
    """

    try:
        # Generate content using the new SDK syntax and the latest flash model
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            )
        )
        
        # Parse the JSON response
        result_json = json.loads(response.text)
        
        if isinstance(result_json, list):
            keywords = result_json
        elif isinstance(result_json, dict):
            keywords = list(result_json.values())[0]
        else:
            keywords = []
            
        return keywords
        
    except Exception as e:
        print(f"AI keyword extraction error: {e}")
        return []

def search_target_urls(query):
    """
    [Explanation] Serper API: Fetches Google search results.
    """
    url = "https://google.serper.dev/search"
    payload = json.dumps({
      "q": query,
      "num": 5
    })
    headers = {
      'X-API-KEY': SERPER_API_KEY,
      'Content-Type': 'application/json'
    }
    
    try:
        response = requests.request("POST", url, headers=headers, data=payload)
        if response.status_code == 200:
            results = response.json().get("organic", [])
            return [item["link"] for item in results]
        else:
            print(f"Search error: {response.status_code} - {response.text}")
            return []
    except Exception as e:
        print(f"API request failed: {e}")
        return []

# --- Main Execution Logic ---
if __name__ == "__main__":
    sample_theme_text = """
    The award theme for this year is 'Climate Change Response and Inequality Resolution in Africa'. 
    We are looking for grassroots community leaders or innovative environmental activists who have contributed to achieving the UN SDGs.
    """
    
    print("1. Analyzing AI keywords via Gemini...")
    search_queries = get_search_keywords_from_ai(sample_theme_text)
    print(f"Generated search queries: {search_queries}\n")
    
    all_target_urls = set()
    
    print("2. Collecting target institution URLs via Serper...")
    if SERPER_API_KEY:
        for query in search_queries:
            print(f"Searching for: {query}")
            urls = search_target_urls(query)
            all_target_urls.update(urls)
            
        print("\n=== Final Collected Target URLs ===")
        for i, url in enumerate(all_target_urls, 1):
            print(f"{i}. {url}")
    else:
        print("SERPER_API_KEY is not set. Skipping search.")

def get_org_background_context(url):
    """
    Extracts the domain from a URL and searches Google via Serper API 
    to gather background 'About Us' context for the organization.
    """
    try:
        # 1. Extract domain (e.g., https://www.agnesafrica.org/fellowship -> agnesafrica.org)
        domain = urllib.parse.urlparse(url).netloc
        domain = domain.replace("www.", "")
        
        # 2. Create a targeted search query
        search_query = f'"{domain}" about organization background OR wikipedia'
        
        api_key = os.getenv("SERPER_API_KEY")
        if not api_key:
            return ""
            
        url_serper = "https://google.serper.dev/search"
        payload = json.dumps({"q": search_query, "num": 3}) # Get top 3 results
        headers = {
            'X-API-KEY': api_key,
            'Content-Type': 'application/json'
        }
        
        # 3. Request search and compile snippets
        response = requests.post(url_serper, headers=headers, data=payload, timeout=10)
        response.raise_for_status()
        
        results = response.json().get('organic', [])
        context = ""
        for res in results:
            context += f"Title: {res.get('title')}\nSnippet: {res.get('snippet')}\n\n"
            
        return context
        
    except Exception as e:
        print(f"Background search error for {url}: {e}")
        return ""