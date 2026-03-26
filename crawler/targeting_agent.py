import os
import json
import requests
import PyPDF2
from google import genai
import streamlit as st

# ==========================================
# 🚨 API 키 세팅 (우선순위: 1. Streamlit Secrets -> 2. 환경변수)
# ==========================================
try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
except:
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

try:
    SERPER_API_KEY = st.secrets["SERPER_API_KEY"]
except:
    SERPER_API_KEY = os.getenv("SERPER_API_KEY")

# 제미나이 클라이언트 초기화
if GEMINI_API_KEY:
    client = genai.Client(api_key=GEMINI_API_KEY)
else:
    client = None
    print("⚠️ 경고: GEMINI_API_KEY가 설정되지 않았습니다.")

# ==========================================
# 3중 블랙리스트 세팅 (가비지 데이터 차단망)
# ==========================================
DOMAIN_BLACKLIST = [
    "googleadservices.com", "doubleclick.net", "googlesyndication.com", "youtube.com", "youtu.be",
    "vimeo.com", "tiktok.com", "pinterest.com", "pin.it", "instagram.com", "imgur.com", "flickr.com",
    "shutterstock.com", "gettyimages", "amazon", "ebay", "etsy.com", "facebook.com", "twitter.com", "x.com"
]
PATTERN_BLACKLIST = [
    "adurl=", "gclid=", "gbraid=", "wbraid=", "/ads/", "/shopping/", "/video/", "/watch?", "/reel/", "/pin/", "/image/", "/img/"
]
EXT_BLACKLIST = [
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".mp4", ".mov", ".avi", ".zip", ".rar", ".exe", ".pdf"
]

# ==========================================
# 핵심 함수 로직
# ==========================================

def extract_text_from_pdf(pdf_path):
    """[Step 1] 업로드된 심사 기준 PDF에서 순수 텍스트를 추출합니다."""
    text = ""
    try:
        with open(pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            for page in reader.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted + "\n"
    except Exception as e:
        print(f"PDF 파싱 에러: {e}")
    return text

def get_search_keywords_from_ai(text):
    """[Step 1] 제미나이를 호출하여 PDF 본문에서 핵심 주제(Theme) 키워드 배열을 뽑아냅니다."""
    if not client: return []
    
    prompt = f"""
    아래 텍스트는 특정 시상식이나 지원금 프로그램의 심사 기준입니다.
    이 문서가 타겟팅하는 '가장 핵심적인 주제(Theme) 키워드'를 영어로 5~10개 추출하세요.
    단, 'award', 'grant', 'prize' 같이 흔하고 뻔한 단어는 절대 포함하지 마세요.
    
    결과는 반드시 다음과 같은 순수 JSON 배열(Array) 형태로만 출력하세요. 다른 말은 덧붙이지 마세요.
    ["climate change", "youth empowerment", "renewable energy"]
    
    텍스트:
    {text[:5000]}
    """
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        cleaned_response = response.text.strip().replace("```json", "").replace("```", "")
        return json.loads(cleaned_response)
    except Exception as e:
        print(f"AI 키워드 추출 에러: {e}")
        return []

def search_target_urls(query):
    """[Step 3] 검색어(Dorks)로 구글을 타격하고 3중 블랙리스트로 걸러낸 순도 높은 URL 배열을 반환합니다."""
    if not SERPER_API_KEY: return []
    
    # [문지기 1] Dorks 사전 필터링 (가장 무거운 SNS 사이트 원천 차단)
    dorks = " -site:youtube.com -site:pinterest.com -site:instagram.com -site:tiktok.com -site:facebook.com"
    final_query = query + dorks
    
    url = "https://google.serper.dev/search"
    payload = json.dumps({"q": final_query, "num": 10})
    headers = {'X-API-KEY': SERPER_API_KEY, 'Content-Type': 'application/json'}
    
    try:
        response = requests.post(url, headers=headers, data=payload, timeout=10)
        response.raise_for_status()
        results = response.json().get('organic', [])
    except Exception as e:
        print(f"Serper API 에러: {e}")
        return []
        
    # [문지기 2] 3중 블랙리스트 사후 필터링
    filtered_results = []
    for res in results:
        link = res.get('link', '').lower()
        if any(b in link for b in DOMAIN_BLACKLIST): continue
        if any(p in link for p in PATTERN_BLACKLIST): continue
        if any(link.endswith(e) for e in EXT_BLACKLIST): continue
        filtered_results.append(res)
        
    return filtered_results

def search_award_background(award_name):
    """[Step 3] 팩트체크용 딥서치: 시상명에 대한 구글 검색 상위 10개 요약본(Context)을 뭉쳐서 반환합니다."""
    if not SERPER_API_KEY: return ""
    
    query = f'"{award_name}" about OR history'
    url = "https://google.serper.dev/search"
    payload = json.dumps({"q": query, "num": 10})
    headers = {'X-API-KEY': SERPER_API_KEY, 'Content-Type': 'application/json'}
    
    try:
        response = requests.post(url, headers=headers, data=payload, timeout=10)
        response.raise_for_status()
        results = response.json().get('organic', [])
        
        # 검색 결과의 제목과 요약문(Snippet)을 하나의 텍스트 덩어리로 병합
        context = ""
        for res in results:
            context += f"Title: {res.get('title')}\nSnippet: {res.get('snippet')}\n\n"
        return context
    except Exception as e:
        print(f"배경지식 검색 에러: {e}")
        return ""

def search_award_winners(award_name):
    """[Step 4] 인물 색출용: 해당 시상식의 수상자 발표 기사나 공식 웹페이지 URL 5개를 반환합니다."""
    if not SERPER_API_KEY: return []
    
    query = f'"{award_name}" winner OR finalist OR recipient'
    url = "https://google.serper.dev/search"
    payload = json.dumps({"q": query, "num": 5}) # 속도를 위해 5개만 타격
    headers = {'X-API-KEY': SERPER_API_KEY, 'Content-Type': 'application/json'}
    
    try:
        response = requests.post(url, headers=headers, data=payload, timeout=10)
        response.raise_for_status()
        return response.json().get('organic', [])
    except Exception as e:
        print(f"수상자 검색 에러: {e}")
        return []