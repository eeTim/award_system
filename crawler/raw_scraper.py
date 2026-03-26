import os
import requests
from curl_cffi import requests as cureq
from bs4 import BeautifulSoup
import urllib3

# SSL 인증서 경고 숨김 (터미널 깔끔하게 유지)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def extract_clean_text(html_content):
    """
    [헬퍼 함수] HTML에서 자바스크립트, CSS, 메뉴 등을 걷어내고 순수 본문 텍스트만 추출합니다.
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    for script_or_style in soup(['script', 'style', 'header', 'footer', 'nav', 'aside']):
        script_or_style.decompose()
        
    raw_text = soup.get_text(separator=' ')
    lines = (line.strip() for line in raw_text.splitlines())
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    return '\n'.join(chunk for chunk in chunks if chunk)


def scrape_raw_text(url):
    """
    [역할] 주어진 URL에 접속하여 봇(Bot) 차단 시스템을 우회하고 순수한 본문 텍스트를 추출합니다.
    - Plan A: 일반 requests (빠른 속도)
    - Plan B: curl_cffi (Chrome 120 지문 위조로 WAF 우회)
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    # =====================================================================
    # 🚨 [Plan C: 최후의 보루 (상용 Web Unlocker API)] 🚨
    # 나중에 캡차(CAPTCHA) 등 극한의 방어막에 막혀 A, B가 모두 실패할 경우를 대비한 플랜입니다.
    # =====================================================================
    '''
    scraper_api_key = os.getenv("SCRAPER_API_KEY")
    if scraper_api_key:
        try:
            payload = {'api_key': scraper_api_key, 'url': url, 'render': 'true'}
            response = requests.get('http://api.scraperapi.com/', params=payload, timeout=30)
            if response.status_code == 200 and len(response.text) > 100:
                return extract_clean_text(response.text)
        except Exception as e:
            print(f"Plan C (상용 API) 에러 ({url}): {e}")
    '''
    # =====================================================================

    # --- [Plan A: 일반 HTTP 접속 (가장 빠름)] ---
    # 방화벽이 없는 약 70%의 사이트를 0.5초 만에 빠르게 긁어옵니다.
    try:
        response = requests.get(url, headers=headers, timeout=15, verify=False)
        if response.status_code == 200:
            cleaned_text = extract_clean_text(response.text)
            if len(cleaned_text) > 100:
                return cleaned_text
    except Exception:
        pass # 에러가 나거나 403으로 막히면 조용히 Plan B로 넘어갑니다.

    # --- [Plan B: curl_cffi (크롬 브라우저 지문 위조)] ---
    # Plan A가 실패한 깐깐한 사이트들을 Chrome 120 브라우저인 척 속여서 뚫어냅니다.
    try:
        response_b = cureq.get(url, impersonate="chrome120", timeout=15)
        if response_b.status_code == 200:
            cleaned_text = extract_clean_text(response_b.text)
            if len(cleaned_text) > 100:
                return cleaned_text
    except Exception as e:
        # Plan B마저 실패한 경우에만 로그를 남깁니다.
        print(f"🚫 [스크래핑 최종 실패] {url} - 사유: {e}")

    # 모든 플랜이 실패했을 경우 빈 문자열 반환 (시스템 다운 방지)
    return ""