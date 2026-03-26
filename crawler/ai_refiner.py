import os
import json
from google import genai
import streamlit as st

# ==========================================
# 🚨 API 키 세팅 (우선순위: 1. Streamlit Secrets -> 2. 환경변수)
# ==========================================
try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
except:
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if GEMINI_API_KEY:
    client = genai.Client(api_key=GEMINI_API_KEY)
else:
    client = None
    print("⚠️ 경고: GEMINI_API_KEY가 설정되지 않았습니다.")

# ==========================================
# 핵심 AI 분석 함수 로직
# ==========================================

def extract_initial_award_name(raw_text):
    """
    [Phase 2] 1차 스크래핑된 웹사이트 본문에서 '단 하나의 공식 시상/프로그램명'만 추출합니다.
    """
    if not client or not raw_text: return "관련 없음"
    
    prompt = f"""
    아래 주어진 웹사이트 텍스트에서 이 문서가 다루고 있는 '가장 핵심적인 1개의 정식 시상식 또는 지원금 프로그램 이름(고유명사)'을 영어로 추출해.
    만약 텍스트가 시상식/지원금과 전혀 관련 없는 내용이거나 광고뿐이라면 오직 "관련 없음" 이라고만 대답해.
    다른 설명은 일절 덧붙이지 말고 상 이름만 출력할 것.

    [웹사이트 텍스트]
    {raw_text[:8000]}
    """
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        return response.text.strip()
    except Exception as e:
        print(f"1차 시상명 추출 에러: {e}")
        return "관련 없음"


def verify_and_extract_org_info(orig_text, bg_context, sample_url):
    """
    [Phase 3] 원문 텍스트와 딥서치 배경지식을 교차 검증하여 최종 기관 정보를 JSON으로 팩트체크합니다.
    """
    if not client: return {}

    prompt = f"""
    너는 글로벌 시상식 및 지원금 프로그램의 팩트체커야. 
    아래 제공된 [스크래핑 원문]과 구글에서 추가로 수집한 [배경지식 Context]를 대조하여 환각(Hallucination) 없이 정확한 정보를 추출해.
    
    [스크래핑 원문 (URL: {sample_url})]
    {orig_text[:5000]}
    
    [구글 배경지식 Context]
    {bg_context[:5000]}
    
    위 정보들을 종합하여 다음 5개의 Key를 가진 JSON 객체로만 대답해. 다른 텍스트는 출력하지 마.
    - "시상/프로그램명": (공식 명칭, 영어)
    - "주최/주관 기관명": (가장 상위의 공식 주최 기관명, 영어)
    - "출처 유형": (공식 홈페이지, 뉴스 기사, NGO 발표문, 알 수 없음 중 택 1)
    - "시상 주제(Theme)": (간단한 핵심 주제 1~2단어 요약)
    - "신뢰도": (원문과 배경지식이 일치하면 "High", 모호하면 "Medium", 불일치/부족하면 "Low")
    """
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        cleaned_response = response.text.strip().replace("```json", "").replace("```", "")
        return json.loads(cleaned_response)
    except Exception as e:
        print(f"기관 팩트체크 에러: {e}")
        return {
            "시상/프로그램명": "추출 실패", "주최/주관 기관명": "추출 실패", 
            "출처 유형": "오류", "시상 주제(Theme)": "오류", "신뢰도": "Low"
        }


def extract_candidate_info(w_text):
    """
    [Phase 4] 수상자 발표문에서 최종 인물(후보자) 명단과 이력을 배열(List of Dicts)로 추출합니다.
    """
    if not client or not w_text: return []

    prompt = f"""
    아래 텍스트는 특정 시상식의 수상자(Winner) 또는 최종 후보자(Finalist)를 발표하는 문서야.
    이 텍스트 안에 등장하는 '모든 수상자/후보자 인물'의 정보를 추출해서 JSON 배열(Array) 형태로 반환해.
    만약 사람 이름이 없거나 단체만 있다면 빈 배열 [] 을 반환해.
    
    각 인물 데이터는 다음 4개의 Key를 가져야 해:
    - "이름": (사람 이름)
    - "소속/직책": (소속된 단체나 직책, 없으면 "N/A")
    - "국가": (국가명, 없으면 "N/A")
    - "주요 업적": (어떤 일로 상을 받았는지 1문장으로 요약)

    [발표문 텍스트]
    {w_text[:8000]}
    """
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        cleaned_response = response.text.strip().replace("```json", "").replace("```", "")
        return json.loads(cleaned_response)
    except Exception as e:
        print(f"인물 정보 추출 에러: {e}")
        return []