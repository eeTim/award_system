'''
이 코드는 원문 3개의 전체를 스크래핑 하는 코드입니다.
'''

import requests
from bs4 import BeautifulSoup
import pandas as pd
import time

def debug_scrape_raw_text(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    print(f"\n🌐 [접속 시도] {url}")
    
    # --- [Plan A: Jina Reader API (JS 렌더링 및 보안 우회)] ---
    jina_url = f"https://r.jina.ai/{url}"
    print("   👉 [Plan A] Jina 우회 API 타격 중...")
    try:
        response = requests.get(jina_url, headers=headers, timeout=20)
        if response.status_code == 200 and len(response.text) > 100:
            text_len = len(response.text)
            print(f"   ✅ [Plan A 성공] 보안망 우회 완료! (글자 수: {text_len}자)")
            # 🚨 수정됨: 미리보기가 아닌 원문 전체 반환
            return {"URL": url, "성공 여부": "성공 (Plan A)", "글자 수": text_len, "본문 전체": response.text}
        else:
            print(f"   ⚠️ [Plan A 실패] 응답 코드 {response.status_code} 또는 내용 부족. Plan B로 전환합니다.")
    except Exception as e:
        print(f"   ⚠️ [Plan A 에러] {e}")

    # --- [Plan B: 전통적인 BeautifulSoup 스크래핑] ---
    print("   👉 [Plan B] 직접 HTTP 접속 및 파싱 시도 중...")
    try:
        response = requests.get(url, headers=headers, timeout=15, verify=False)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        for script_or_style in soup(['script', 'style', 'header', 'footer', 'nav', 'aside']):
            script_or_style.decompose()
            
        raw_text = soup.get_text(separator=' ')
        lines = (line.strip() for line in raw_text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        cleaned_text = '\n'.join(chunk for chunk in chunks if chunk)
        
        text_len = len(cleaned_text)
        if text_len > 100:
            print(f"   ✅ [Plan B 성공] HTML 직접 파싱 완료! (글자 수: {text_len}자)")
            # 🚨 수정됨: 미리보기가 아닌 원문 전체 반환
            return {"URL": url, "성공 여부": "성공 (Plan B)", "글자 수": text_len, "본문 전체": cleaned_text}
        else:
            print("   🚫 [Plan B 실패] 웹사이트가 비어있거나 보안에 막혔습니다.")
            return {"URL": url, "성공 여부": "실패 (내용 없음)", "글자 수": 0, "본문 전체": ""}
            
    except Exception as e:
        print(f"   🚫 [Plan B 에러] 차단됨: {e}")
        return {"URL": url, "성공 여부": f"완전 실패 ({e})", "글자 수": 0, "본문 전체": ""}

# ==========================================
# 실행부: 상위 3개 URL 테스트 및 CSV 송출
# ==========================================
if __name__ == "__main__":
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    # 기존 10개 리스트
    all_test_urls = [
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

    # 🚨 수정됨: 딱 3개만 잘라서 테스트 진행
    test_urls = all_test_urls[:3]

    print("=" * 60)
    print(f"🕵️‍♂️ [스크래핑 원문 추출 테스트 시작] - 총 {len(test_urls)}개 URL")
    print("=" * 60)

    results = []
    success_count = 0

    for url in test_urls:
        res_dict = debug_scrape_raw_text(url)
        results.append(res_dict)
        if "성공" in res_dict["성공 여부"]:
            success_count += 1
        
        time.sleep(2)

    df = pd.DataFrame(results)
    csv_filename = "scraping_fulltext_results.csv"
    df.to_csv(csv_filename, index=False, encoding='utf-8-sig')

    print("\n" + "=" * 60)
    print(f"🎯 [최종 성적] {len(test_urls)}개 중 {success_count}개 성공")
    print(f"💾 [파일 저장 완료] 결과가 '{csv_filename}' 파일로 송출되었습니다.")
    print("=" * 60)