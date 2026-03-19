import os
import requests
from bs4 import BeautifulSoup

def scrape_raw_text(url):
    """
    [역할] 주어진 URL에 접속하여 봇(Bot) 차단 시스템을 우회하고 순수한 본문 텍스트를 추출합니다.
    플랜 A(Jina), 플랜 B(BeautifulSoup)를 기본으로 사용하며, 
    플랜 C(상용 API)는 예비용 비장의 카드로 주석 처리해 두었습니다.
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    # =====================================================================
    # 🚨 [Plan C: 비장의 카드 (All-in-One 상용 스크래핑 API)] 🚨
    # 나중에 Cloudflare 등 강력한 차단에 막혀 A, B가 모두 실패할 경우, 
    # 환경변수에 SCRAPER_API_KEY를 발급받아 넣고 아래 주석(''')을 해제하여 최상단 로직으로 사용하세요.
    # =====================================================================
    '''
    scraper_api_key = os.getenv("SCRAPER_API_KEY")
    if scraper_api_key:
        try:
            # ScraperAPI 엔드포인트를 통해 우회 접속 (render=true 옵션으로 JS까지 렌더링)
            payload = {'api_key': scraper_api_key, 'url': url, 'render': 'true'}
            response = requests.get('http://api.scraperapi.com/', params=payload, timeout=30)
            
            if response.status_code == 200 and len(response.text) > 100:
                soup = BeautifulSoup(response.text, 'html.parser')
                for script_or_style in soup(['script', 'style', 'header', 'footer', 'nav', 'aside']):
                    script_or_style.decompose()
                    
                raw_text = soup.get_text(separator=' ')
                lines = (line.strip() for line in raw_text.splitlines())
                return '\n'.join(chunk.strip() for line in lines for chunk in line.split("  ") if chunk.strip())
        except Exception as e:
            print(f"Plan C (상용 API) 실패 ({url}): {e}")
    '''
    # =====================================================================

    # --- [Plan A: Jina Reader API (무료 우회/마크다운 추출)] ---
    jina_url = f"https://r.jina.ai/{url}"
    try:
        response = requests.get(jina_url, headers=headers, timeout=20)
        if response.status_code == 200 and len(response.text) > 100:
            return response.text
    except Exception as e:
        print(f"Plan A (Jina API) 우회 실패 ({url}): {e}")

    # --- [Plan B: 전통적인 BeautifulSoup 스크래핑] ---
    try:
        response = requests.get(url, headers=headers, timeout=15, verify=False)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 문서 구조에서 불필요한 찌꺼기 뜯어내기
        for script_or_style in soup(['script', 'style', 'header', 'footer', 'nav', 'aside']):
            script_or_style.decompose()
            
        raw_text = soup.get_text(separator=' ')
        lines = (line.strip() for line in raw_text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        cleaned_text = '\n'.join(chunk for chunk in chunks if chunk)
        
        return cleaned_text
        
    except Exception as e:
        print(f"Plan B (전통적 스크래핑) 실패 ({url}): {e}")
        return ""