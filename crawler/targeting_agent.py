import os
import json
import requests
import PyPDF2
from google import genai
from google.genai import types

# Initialize Gemini Client (API 키는 환경 변수 GEMINI_API_KEY에 설정되어 있어야 합니다)
client = genai.Client()

def extract_text_from_pdf(file_path):
    text = ""
    try:
        with open(file_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            for page in reader.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted + "\n"
    except Exception as e:
        print(f"PDF Extraction Error: {e}")
    return text.strip()

def get_search_keywords_from_ai(theme_text):
    prompt = f"""
    You are an expert data analyst. Read the following award/grant guideline text.
    Extract 5 to 10 core "theme keywords" (in English). 
    These keywords should strictly represent the MAIN TOPIC (e.g., 'climate change', 'grassroots innovation').
    DO NOT include words like 'award' or 'grant' as they will be added manually later.
    
    Return ONLY a valid JSON list of strings. 
    Example: ["climate change response", "inequality resolution", "grassroots environmentalism"]
    
    Text: {theme_text[:8000]}
    """
    
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            )
        )
        
        raw_output = response.text.strip()
        if raw_output.startswith("```json"): 
            raw_output = raw_output[7:-3].strip()
        elif raw_output.startswith("```"): 
            raw_output = raw_output[3:-3].strip()
            
        return json.loads(raw_output)
    except Exception as e:
        print(f"AI Keyword Extraction Error: {e}")
        return []

def search_target_urls(query):
    api_key = os.getenv("SERPER_API_KEY")
    if not api_key:
        return []

    dorks = " -site:youtube.com -site:pinterest.com -site:instagram.com -site:tiktok.com -site:facebook.com"
    final_query = query + dorks

    url_serper = "https://google.serper.dev/search"
    payload = json.dumps({"q": final_query, "num": 10})
    headers = {'X-API-KEY': api_key, 'Content-Type': 'application/json'}

    try:
        response = requests.post(url_serper, headers=headers, data=payload, timeout=10)
        response.raise_for_status()
        results = response.json().get('organic', [])
    except Exception as e:
        print(f"Serper API Error: {e}")
        return []

    domain_blacklist = [
        "googleadservices.com", "doubleclick.net", "googlesyndication.com", "youtube.com", "youtu.be",
        "vimeo.com", "tiktok.com", "pinterest.com", "pin.it", "instagram.com", "imgur.com", "flickr.com",
        "shutterstock.com", "gettyimages", "amazon", "ebay", "etsy.com"
    ]
    pattern_blacklist = [
        "adurl=", "gclid=", "gbraid=", "wbraid=", "/ads/", "/shopping/", "/video/", "/watch?", "/reel/", "/pin/", "/image/", "/img/"
    ]
    ext_blacklist = [
        ".jpg", ".jpeg", ".png", ".gif", ".webp", ".mp4", ".mov", ".avi", ".zip", ".rar", ".exe", ".pdf"
    ]

    filtered_results = []
    for res in results:
        link = res.get('link', '').lower()
        title = res.get('title', '')
        snippet = res.get('snippet', '')

        if any(b in link for b in domain_blacklist): continue
        if any(p in link for p in pattern_blacklist): continue
        if any(link.endswith(e) for e in ext_blacklist): continue

        filtered_results.append({
            "title": title,
            "link": res.get('link'),
            "snippet": snippet
        })

    return filtered_results

def search_award_background(award_name):
    api_key = os.getenv("SERPER_API_KEY")
    if not api_key: 
        return ""

    search_query = f'"{award_name}" about OR history OR official site'
    url_serper = "https://google.serper.dev/search"
    # 딥서치를 위해 10개의 결과를 가져옵니다.
    payload = json.dumps({"q": search_query, "num": 10})
    headers = {'X-API-KEY': api_key, 'Content-Type': 'application/json'}

    try:
        response = requests.post(url_serper, headers=headers, data=payload, timeout=10)
        response.raise_for_status()
        results = response.json().get('organic', [])
        
        context = f"--- 구글 딥서치 결과 (검색어: {award_name}) ---\n"
        for i, res in enumerate(results):
            context += f"[{i+1}] Title: {res.get('title')}\nSnippet: {res.get('snippet')}\nLink: {res.get('link')}\n\n"
        return context
    except Exception as e:
        print(f"Background search error: {e}")
        return ""

def search_award_winners(award_name, year=""):
    api_key = os.getenv("SERPER_API_KEY")
    if not api_key:
        return []

    # 수상자를 찾기 위한 타겟팅 쿼리 조립
    search_query = f'"{award_name}" (winner OR laureate OR finalist OR candidates)'
    if year:
        search_query += f' {year}'

    url_serper = "https://google.serper.dev/search"
    payload = json.dumps({"q": search_query, "num": 5}) # 수상자 명단은 보통 상위 5개 기사에 집중됨
    headers = {'X-API-KEY': api_key, 'Content-Type': 'application/json'}

    try:
        response = requests.post(url_serper, headers=headers, data=payload, timeout=10)
        response.raise_for_status()
        results = response.json().get('organic', [])
        
        # 여기서도 기본 블랙리스트 필터링을 약하게 적용 가능하지만, 언론 보도를 찾아야 하므로 패스합니다.
        winner_urls = []
        for res in results:
            winner_urls.append({
                "title": res.get('title'),
                "link": res.get('link')
            })
        return winner_urls
    except Exception as e:
        print(f"Winner search error: {e}")
        return []