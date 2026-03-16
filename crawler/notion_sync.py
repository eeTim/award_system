import os
import requests
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

NOTION_API_KEY = os.getenv("NOTION_API_KEY")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")

def create_notion_page(candidate_data):
    """
    Sends the extracted candidate JSON data to the specified Notion Database.
    Make sure the property names here exactly match the property names in your Notion DB.
    """
    url = "https://api.notion.com/v1/pages"
    
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }

    # Map the JSON data to Notion's specific property structures
    # Note: Property names ("이름", "AI 3줄 요약", etc.) must match Notion exactly.
    data = {
        "parent": { "database_id": NOTION_DATABASE_ID },
        "properties": {
            "이름": {
                "title": [
                    {
                        "text": {
                            "content": candidate_data.get("name", "Unknown")
                        }
                    }
                ]
            },
            "AI 3줄 요약": {
                "rich_text": [
                    {
                        "text": {
                            "content": candidate_data.get("summary", "")
                        }
                    }
                ]
            },
            "국가": {
                "select": {
                    "name": candidate_data.get("country", "Unknown")
                }
            },
            "팩트체크(AI 교차검증)": {
                "rich_text": [
                    {
                        "text": {
                            "content": candidate_data.get("fact_check", "")
                        }
                    }
                ]
            }
        }
    }

    try:
        response = requests.post(url, headers=headers, data=json.dumps(data))
        
        if response.status_code == 200:
            print(f"Successfully added '{candidate_data.get('name')}' to Notion!")
            return True
        else:
            print(f"Failed to add to Notion. Status Code: {response.status_code}")
            print(f"Error Details: {response.text}")
            return False
            
    except Exception as e:
        print(f"Notion API Request Error: {e}")
        return False

# --- Main Execution Logic ---
if __name__ == "__main__":
    # The JSON data we got from ai_refiner.py
    sample_json_data = {
        "name": "Jane Doe",
        "summary": "Jane Doe leads the 'Green Earth Initiative' since 2015, successfully planting over 1 million trees across the Nairobi region.\nShe provided clean drinking water to 5 rural villages through innovative solar-powered water pumps.\nHer efforts are recognized by the UN, and she was awarded the Africa Climate Justice Award 2025.",
        "country": "Kenya",
        "fact_check": "The information provided suggests high credibility. Her initiative's impact (1 million trees, 5 villages with water) is stated, and her approach is recognized by the UN. A recent award further supports her achievements."
    }
    
    if NOTION_API_KEY and NOTION_DATABASE_ID:
        print("1. Sending data to Notion Database...")
        create_notion_page(sample_json_data)
    else:
        print("Error: Notion API Key or Database ID is missing in .env file.")