import os
import requests
import json
import streamlit as st

# ==========================================
# 🚨 웹훅 URL 세팅 (우선순위: 1. Streamlit Secrets -> 2. 환경변수)
# ==========================================
try:
    N8N_WEBHOOK_URL = st.secrets["N8N_WEBHOOK_URL"]
except:
    N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL")

def send_data_to_n8n(candidates_list, award_name, org_name, theme):
    """
    [Phase 4] 추출된 최종 후보자 배열(List)을 n8n 웹훅으로 POST 전송합니다.
    - 데이터 구조를 노션 DB에 맵핑하기 좋게 패키징하여 보냅니다.
    """
    if not N8N_WEBHOOK_URL:
        print("⚠️ 에러: N8N_WEBHOOK_URL이 설정되지 않았습니다.")
        return False

    if not candidates_list:
        print(f"ℹ️ 전송할 인물 데이터가 없습니다. ({award_name})")
        return False

    # n8n이 받아서 처리하기 좋게 메타데이터와 배열을 예쁘게 포장(Payload)합니다.
    payload = {
        "metadata": {
            "award_name": award_name,
            "organization": org_name,
            "theme": theme
        },
        "candidates": candidates_list
    }

    headers = {
        'Content-Type': 'application/json'
    }

    print(f"🚀 n8n 웹훅으로 데이터 전송 시도 중... (대상: {len(candidates_list)}명)")

    try:
        # HTTP POST 요청으로 n8n 트리거를 작동시킵니다.
        response = requests.post(N8N_WEBHOOK_URL, headers=headers, data=json.dumps(payload), timeout=15)
        
        # 200번대 응답(성공)인지 확인
        if response.ok:
            print(f"✅ n8n 전송 성공! (응답 코드: {response.status_code})")
            return True
        else:
            print(f"🚫 n8n 전송 실패: 서버가 {response.status_code} 코드를 반환했습니다.")
            print(f"상세 메시지: {response.text}")
            return False

    except requests.exceptions.RequestException as e:
        # 인터넷 끊김, 타임아웃 등 네트워크 단 에러 처리
        print(f"🚫 n8n 웹훅 연결 에러 (네트워크 문제): {e}")
        return False