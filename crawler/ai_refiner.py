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