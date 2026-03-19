import json
from google import genai
from google.genai import types

# Initialize Gemini Client (API 키는 환경 변수 GEMINI_API_KEY에 설정되어 있어야 합니다)
client = genai.Client()

def extract_initial_award_name(raw_text):
    prompt = f"""
    You are an expert data analyst. Read the following text from a website.
    Your ONLY goal is to find the official name of the award, fellowship, grant, or recognition program mentioned.
    
    Return ONLY the exact name as a string (e.g., "The Earthshot Prize"). 
    Do not add any other words. If there is NO award mentioned, return exactly: "관련 없음"
    
    Raw Text:
    {raw_text[:8000]}
    """
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )
        return response.text.strip()
    except Exception as e:
        print(f"Initial Award Name Extraction Error: {e}")
        return "관련 없음"

def verify_and_extract_org_info(raw_text, google_context, url):
    prompt = f"""
    You are an expert OSINT data analyst. You are given TWO pieces of evidence:
    1. [Raw Web Text]: Text from the initial source URL.
    2. [Google Search Context]: 10 Google search snippets about this award to cross-verify the facts.
    
    Synthesize both sources and extract the verified official information.
    Return ONLY a valid JSON object with the exact keys below. If info is missing, write "정보 없음".

    Keys:
    - "시상/프로그램명": Verified official name of the award/program.
    - "주최/관련 기관": Verified official organization hosting/funding it.
    - "출처 유형": Classify the original URL as: "공식 홈페이지", "언론 보도", "개인/블로그", or "기타".
    - "시상 주제": A 1-sentence summary of what the award is for.
    - "URL": "{url}"

    [Raw Web Text]:
    {raw_text[:6000]}
    
    [Google Search Context]:
    {google_context[:4000]}
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
        print(f"Verified Org Info Extraction Error: {e}")
        return {
            "시상/프로그램명": "파싱 에러", "주최/관련 기관": "파싱 에러", 
            "출처 유형": "알 수 없음", "시상 주제": "-", "URL": url
        }

def extract_candidate_info(raw_text):
    prompt = f"""
    You are an expert data analyst. Read the following website text (likely a news article or official announcement).
    Extract information about the AWARD WINNERS, FINALISTS, or CANDIDATES mentioned.
    
    Return ONLY a valid JSON list of objects. Each object must have these exact keys. 
    If a specific piece of information is missing, put "알 수 없음".
    
    Keys for each object:
    - "name": Full name of the candidate/winner.
    - "affiliation": The organization, company, or community they belong to.
    - "country": Their operating country or nationality.
    - "summary": A 1-2 sentence summary of their achievement.
    
    If no people are mentioned, return an empty list: []

    Raw Text:
    {raw_text[:8000]}
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
        print(f"Candidate Extraction Error: {e}")
        return []