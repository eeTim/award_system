'''
현재 코드는 jira api를 빼고, 1단계는 requests+beautifulsoup로 시도하고, 2단계는 curl_cffi로 시도하는 방식입니다.
'''

import requests
from curl_cffi import requests as cureq # 🚨 핵심 무기: 브라우저 위조 라이브러리
from bs4 import BeautifulSoup
import pandas as pd
import time
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def extract_clean_text(html_content):
    """HTML에서 쓸데없는 코드를 걷어내고 순수 본문만 추출하는 헬퍼 함수"""
    soup = BeautifulSoup(html_content, 'html.parser')
    for script_or_style in soup(['script', 'style', 'header', 'footer', 'nav', 'aside']):
        script_or_style.decompose()
        
    raw_text = soup.get_text(separator=' ')
    lines = (line.strip() for line in raw_text.splitlines())
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    return '\n'.join(chunk for chunk in chunks if chunk)

def debug_scrape_raw_text(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    print(f"\n🌐 [접속 시도] {url}")
    
    # --- [New Plan A: 일반 requests (가장 빠름)] ---
    print("   👉 [Plan A] 일반 HTTP 접속 시도 중...")
    try:
        response = requests.get(url, headers=headers, timeout=15, verify=False)
        if response.status_code == 200:
            cleaned_text = extract_clean_text(response.text)
            if len(cleaned_text) > 100:
                print(f"   ✅ [Plan A 성공] 보안 없음. 즉시 파싱 완료! (글자 수: {len(cleaned_text)}자)")
                return {"URL": url, "성공 여부": "성공 (Plan A: 일반)", "글자 수": len(cleaned_text), "본문 전체": cleaned_text}
        else:
            print(f"   ⚠️ [Plan A 실패] 응답 코드 {response.status_code}. 방화벽 감지됨.")
    except Exception as e:
        print(f"   ⚠️ [Plan A 에러] {e}")

    # --- [New Plan B: curl_cffi (크롬 지문 위조)] ---
    # Plan A가 실패했을 경우에만 실행됩니다.
    print("   👉 [Plan B] 방화벽 감지! curl_cffi(Chrome 120 위조 모드)로 우회 타격 중...")
    try:
        # 🚨 impersonate="chrome120" 옵션이 서버를 속이는 핵심 키입니다.
        response_b = cureq.get(url, impersonate="chrome120", timeout=15)
        
        if response_b.status_code == 200:
            cleaned_text = extract_clean_text(response_b.text)
            if len(cleaned_text) > 100:
                print(f"   ✅ [Plan B 성공] 🛡️ TLS 방어막 우회 완료! (글자 수: {len(cleaned_text)}자)")
                return {"URL": url, "성공 여부": "성공 (Plan B: curl_cffi)", "글자 수": len(cleaned_text), "본문 전체": cleaned_text}
            else:
                print("   🚫 [Plan B 실패] 접속은 했으나 자바스크립트 렌더링 장벽에 막힘.")
        else:
            print(f"   🚫 [Plan B 실패] 위조 실패. 응답 코드: {response_b.status_code}")
            
    except Exception as e:
        print(f"   🚫 [Plan B 에러] 완전 차단됨: {e}")
        
    return {"URL": url, "성공 여부": "최종 실패", "글자 수": 0, "본문 전체": ""}

# ==========================================
# 실행부: 10개 URL 테스트
# ==========================================
if __name__ == "__main__":
    test_urls = [
        "https://earthshotprize.org/the-prize/cape-town-2024/",
        "https://www.miga.org/press-release/africa-sustainable-futures-awards-winners-announced",
        "https://live.worldbank.org/en/event/2024/africa-sustainable-futures-awards",
        "https://www.kofiannanfoundation.org/news/the-winners-of-the-2024-kofi-annan-award-for-innovation-in-africa/",
        "https://www.adaptation-undp.org/sustainable-housing-initiative-honoured-finalist-2024-global-center-adaptations-local-adaptation",
        "https://growingafrica.pub/excel-africa-award-and-fellowship-recipients-for-2024/",
        "https://knowledge.energyinst.org/new-energy-world/article?id=138933",
        "https://pacja.org/pacja-awards-journalists-reporting-on-the-environment-and-climate-change-in-africa-accer/",
        "https://climateawards.africa/",
        "https://earthshotprize.org/news/the-earthshot-prize-lands-in-south-africa-for-earthshot-week-2024/"
    ]

    print("=" * 60)
    print(f"🕵️‍♂️ [New 스크래핑 우회 테스트 시작] - 총 {len(test_urls)}개 URL")
    print("=" * 60)

    results = []
    success_count = 0

    for url in test_urls:
        res_dict = debug_scrape_raw_text(url)
        results.append(res_dict)
        if "성공" in res_dict["성공 여부"]:
            success_count += 1
        
        time.sleep(1) # 매너 타임

    df = pd.DataFrame(results)
    csv_filename = "scraping_curl_results.csv"
    df.to_csv(csv_filename, index=False, encoding='utf-8-sig')

    print("\n" + "=" * 60)
    print(f"🎯 [최종 성적] {len(test_urls)}개 중 {success_count}개 성공")
    print(f"💾 [파일 저장 완료] 결과가 '{csv_filename}' 파일로 송출되었습니다.")
    print("=" * 60)