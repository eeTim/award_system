'''
Phase.2에서 정확한 검색이 되는지 테스트하는 코드입니다. 
Dorks 1차 검색 : 조립된 검색어 뒤에 -site:youtube.com 등 검색 연산자(Dorks)를 강제 결합하여 Serper API를 호출, 상위 10개의 구글 검색 결과를 가져옵니다.
'''
import os
import json
import requests
from dotenv import load_dotenv

# 환경 변수 로드 (.env 금고에서 API 키를 가져옵니다)
load_dotenv()

def debug_search_target_urls(query):
    api_key = os.getenv("SERPER_API_KEY")
    if not api_key:
        print("❌ 에러: .env 파일에 SERPER_API_KEY가 없습니다.")
        return []

    # 1. 쿼리 조립
    dorks = " -site:youtube.com -site:pinterest.com -site:instagram.com -site:tiktok.com -site:facebook.com"
    final_query = query + dorks
    print(f"\n🚀 [디버그] 구글에 전송할 최종 쿼리: {final_query}")

    url_serper = "https://google.serper.dev/search"
    payload = json.dumps({"q": final_query, "num": 10})
    headers = {'X-API-KEY': api_key, 'Content-Type': 'application/json'}

    # 2. 구글 API 호출
    try:
        response = requests.post(url_serper, headers=headers, data=payload, timeout=10)
        response.raise_for_status()
        results = response.json().get('organic', [])
        print(f"📥 [디버그] 구글 API 응답 완료: 총 {len(results)}개의 URL을 가져왔습니다.\n")
    except Exception as e:
        print(f"❌ [디버그] Serper API 에러: {e}")
        return []

    # 3. 3중 블랙리스트 가동
    domain_blacklist = [
        "googleadservices.com", "doubleclick.net", "googlesyndication.com", "youtube.com", "youtu.be",
        "vimeo.com", "tiktok.com", "pinterest.com", "pin.it", "instagram.com", "imgur.com", "flickr.com",
        "shutterstock.com", "gettyimages", "amazon", "ebay", "etsy.com"
    ]
    pattern_blacklist = [
        "adurl=", "gclid=", "gbraid=", "wbraid=", "/ads/", "/shopping/", "/video/", "/watch?", "/reel/", "/pin/", "/image/", "/img/"
    ]
    ext_blacklist = [
        ".jpg", ".jpeg", ".png", ".gif", ".webp", ".mp4", ".mov", ".avi", ".zip", ".rar", ".exe", ".pdf"
    ]

    filtered_results = []
    drop_count = 0

    print("-" * 60)
    print("🛡️ [디버그] 3중 블랙리스트 필터링 가동 (차단 및 통과 내역)")
    print("-" * 60)

    for i, res in enumerate(results):
        link = res.get('link', '').lower()
        title = res.get('title', '')
        snippet = res.get('snippet', '')
        
        dropped = False
        drop_reason = ""

        # 어떤 필터에 걸렸는지 상세 추적
        if any(b in link for b in domain_blacklist):
            dropped = True
            drop_reason = f"도메인 블랙리스트 ({[b for b in domain_blacklist if b in link][0]})"
        elif any(p in link for p in pattern_blacklist):
            dropped = True
            drop_reason = f"패턴 블랙리스트 ({[p for p in pattern_blacklist if p in link][0]})"
        elif any(link.endswith(e) for e in ext_blacklist):
            dropped = True
            drop_reason = f"확장자 블랙리스트 ({[e for e in ext_blacklist if link.endswith(e)][0]})"

        if dropped:
            print(f"🚫 [차단됨] {title[:30]}...\n   👉 URL: {link}\n   👉 사유: {drop_reason}\n")
            drop_count += 1
            continue

        # 통과된 데이터
        print(f"✅ [통과됨] {title[:30]}...\n   👉 URL: {link}\n")
        filtered_results.append({
            "title": title,
            "link": res.get('link'),
            "snippet": snippet
        })

    print("-" * 60)
    print(f"🎯 [최종 결과] 총 {len(results)}개 중 {drop_count}개 차단, 최종 {len(filtered_results)}개 생존.")
    print("-" * 60)
    
    return filtered_results

# 테스트 실행부
if __name__ == "__main__":
    # 가주님이 테스트하고 싶은 검색어를 여기에 입력하세요.
    test_query = "climate change award africa 2024" 
    
    survivors = debug_search_target_urls(test_query)
    
    print("\n[살아남은 데이터 구조 샘플]")
    for s in survivors[:1]: # 첫 번째 생존자만 샘플로 출력
        print(f"Title: {s['title']}")
        print(f"Link: {s['link']}")
        print(f"Snippet: {s['snippet'][:80]}...")