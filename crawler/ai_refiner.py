import os
import json
from google import genai
from google.genai import types
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure Gemini API using the new SDK
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=GEMINI_API_KEY)

def extract_candidate_info(raw_text):
    """
    Extracts structured candidate information from raw HTML text using Gemini 2.5 Flash.
    Returns a JSON object matching the Notion DB properties.
    """
    prompt = f"""
    You are an expert data analyst. Read the following raw website text and extract information about potential award candidates (individuals or organizations).
    Return ONLY a valid JSON object with the following exact keys. If specific information is missing in the text, put "Not Found".

    Keys to extract:
    - "name": Name of the person or organization.
    - "summary": A 3-line summary of their main achievements or activities.
    - "country": Country of origin or main area of operation.
    - "fact_check": A brief logical evaluation of their credibility based on the text.

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
        
        result_json = json.loads(response.text)
        return result_json
        
    except Exception as e:
        print(f"AI extraction error: {e}")
        return {}

# --- Main Execution Logic ---
if __name__ == "__main__":
    # Sample scraped text for testing
    sample_raw_text = """
    Jane Doe from Kenya has been leading the 'Green Earth Initiative' since 2015. 
    She successfully planted over 1 million trees across the Nairobi region and provided clean drinking water to 5 rural villages. 
    Her innovative approach to utilizing solar-powered water pumps has been recognized by the UN. 
    Recently, she was awarded the Africa Climate Justice Award 2025.
    """
    
    print("1. Feeding raw text to AI...")
    extracted_data = extract_candidate_info(sample_raw_text)
    
    print("\n=== Extracted JSON Data ===")
    print(json.dumps(extracted_data, indent=2, ensure_ascii=False))

def extract_org_info(raw_text, url):
    """
    Extracts organization info from raw text for Phase 1.
    """
    prompt = f"""
    You are an expert data analyst. Read the following website text and extract information about the awarding organization or program.
    Return ONLY a valid JSON object with the following exact keys. If specific information is missing, put "알 수 없음".

    Keys to extract:
    - "기관명": Name of the organization or award program.
    - "URL": "{url}" (Keep this exact url).
    - "시상 주제": Main theme, purpose, or category of the award (in Korean).
    - "최초 시상 년도": The year the award was first given (e.g., "2020년").
    - "후보자 수(추정)": Estimated number of candidates, finalists, or laureates mentioned (e.g., "약 15명", "매년 5명").

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
        
        # --- 추가된 안전망 로직 ---
        raw_output = response.text.strip()
        # 마크다운 찌꺼기(```json)가 붙어있으면 강제로 잘라냄
        if raw_output.startswith("```json"):
            raw_output = raw_output[7:-3].strip()
        elif raw_output.startswith("```"):
            raw_output = raw_output[3:-3].strip()
            
        return json.loads(raw_output)
        # ------------------------
        
    except Exception as e:
        print(f"Org AI extraction error: {e}")
        return {
            "기관명": "파싱 에러", 
            "URL": url, 
            "시상 주제": "파싱 실패", 
            "최초 시상 년도": "-", 
            "후보자 수(추정)": "-"
        }