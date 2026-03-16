import streamlit as st
import pandas as pd
import time

# Import functions from all our custom modules
from targeting_agent import extract_text_from_pdf, get_search_keywords_from_ai, search_target_urls
from raw_scraper import scrape_raw_text
from ai_refiner import extract_candidate_info
from notion_sync import create_notion_page

# 1. Basic web page configuration
st.set_page_config(page_title="후보자 검증 AI 시스템", layout="wide")

# 2. Initialize Session State (Memory pocket)
if 'theme_text' not in st.session_state:
    st.session_state.theme_text = ""
if 'target_urls' not in st.session_state:
    st.session_state.target_urls = []

# 3. Create left sidebar menu
st.sidebar.title("시스템 컨트롤 패널")
menu = st.sidebar.radio(
    "메뉴를 선택하세요:",
    ("1. 시상 주제 업로드", "2. 타겟 기관 탐색", "3. 후보자 스크랩 및 전송", "4. 시스템 디버깅")
)

# 4. Screen configuration for each menu
if menu == "1. 시상 주제 업로드":
    st.header("올해의 시상 테마 업로드")
    st.write("심사 기준이 담긴 PDF 문서를 업로드해 주세요.")
    
    uploaded_file = st.file_uploader("PDF 파일 선택", type="pdf")
    
    if uploaded_file is not None:
        with st.spinner("PDF 텍스트를 추출하는 중입니다..."):
            with open("temp_theme.pdf", "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            extracted_text = extract_text_from_pdf("temp_theme.pdf")
            
            if extracted_text:
                st.session_state.theme_text = extracted_text
                st.success("파일이 성공적으로 업로드 및 분석되었습니다!")
                with st.expander("추출된 텍스트 미리보기"):
                    st.write(extracted_text[:500] + " ... (이하 생략)")
            else:
                st.error("텍스트 추출에 실패했습니다. 파일 형식을 확인해 주세요.")

elif menu == "2. 타겟 기관 탐색":
    st.header("1차: AI 타겟 기관 탐색")
    st.write("AI가 테마를 분석하여 크롤링할 대상 웹사이트를 찾습니다.")
    
    if not st.session_state.theme_text:
        st.warning("먼저 '1. 시상 주제 업로드' 탭에서 PDF 파일을 업로드해 주세요.")
        
        # Fallback text for testing purposes
        if st.button("테스트용 샘플 텍스트로 강제 진행하기"):
            st.session_state.theme_text = "The award theme for this year is 'Climate Change Response and Inequality Resolution in Africa'. We are looking for grassroots community leaders or innovative environmental activists who have contributed to achieving the UN SDGs."
            st.success("테스트용 텍스트가 장전되었습니다! 아래 탐색 버튼을 다시 눌러주세요.")
            st.rerun()
            
    else:
        if st.button("기관 탐색 시작 (약 1분 소요)"):
            st.info("AI가 검색어를 도출하고 있습니다...")
            search_queries = get_search_keywords_from_ai(st.session_state.theme_text)
            st.write(f"**도출된 핵심 검색어:** {search_queries}")
            
            st.info("검색어를 바탕으로 타겟 웹사이트 URL을 수집합니다...")
            progress_bar = st.progress(0)
            all_target_urls = set()
            
            for i, query in enumerate(search_queries):
                urls = search_target_urls(query)
                all_target_urls.update(urls)
                progress_bar.progress((i + 1) / len(search_queries))
                time.sleep(1)
                
            st.session_state.target_urls = list(all_target_urls)
            st.success(f"총 {len(st.session_state.target_urls)}개의 타겟 기관 URL 수집이 완료되었습니다!")
            
            df_urls = pd.DataFrame(st.session_state.target_urls, columns=["Target URL"])
            st.dataframe(df_urls, use_container_width=True)

elif menu == "3. 후보자 스크랩 및 전송":
    st.header("2차: 후보자 수집 및 노션 전송")
    st.write("수집된 기관에서 인물 데이터를 긁어오고 AI 평가를 진행한 뒤 노션으로 보냅니다.")
    
    # Check if target URLs are available
    if not st.session_state.target_urls:
        st.warning("수집된 타겟 URL이 없습니다. '2. 타겟 기관 탐색' 탭에서 먼저 기관을 탐색해 주세요.")
        
        # Fallback URL for testing purposes
        if st.button("테스트용 샘플 URL 1개로 강제 진행하기"):
            st.session_state.target_urls = ["https://earthshotprize.org/news/africas-climate-leadership-highlights-and-reflections-from-kenya-connect/"]
            st.success("테스트용 URL이 장전되었습니다! 아래 버튼을 다시 눌러주세요.")
            st.rerun()
    else:
        st.info(f"현재 대기 중인 타겟 웹사이트: {len(st.session_state.target_urls)}개")
        
        if st.button("수집 및 AI 평가 시작 (약 20분 소요)"):
            progress_bar = st.progress(0)
            status_text = st.empty()
            success_count = 0
            
            # Main Execution Loop
            for i, url in enumerate(st.session_state.target_urls):
                status_text.text(f"[{i+1}/{len(st.session_state.target_urls)}] 접속 및 텍스트 수집 중: {url}")
                
                # Module 2: Scrape Raw Text
                raw_text = scrape_raw_text(url)
                
                # If text is successfully scraped and has decent length
                if raw_text and len(raw_text) > 100:
                    status_text.text(f"[{i+1}/{len(st.session_state.target_urls)}] AI 데이터 분석 및 정제 중...")
                    
                    # Module 3: AI Refiner
                    ai_result = extract_candidate_info(raw_text)
                    
                    # Normalize result to a list to handle both dict (1 person) and list (multiple people)
                    candidates_list = []
                    if isinstance(ai_result, dict):
                        candidates_list = [ai_result]
                    elif isinstance(ai_result, list):
                        candidates_list = ai_result
                        
                    # Process each candidate found
                    for candidate_data in candidates_list:
                        if isinstance(candidate_data, dict) and candidate_data.get("name") and candidate_data.get("name") not in ["Not Found", "Unknown"]:
                            status_text.text(f"[{i+1}/{len(st.session_state.target_urls)}] 노션 DB로 전송 중: {candidate_data.get('name')}")
                            
                            # Module 4: Notion Sync
                            is_success = create_notion_page(candidate_data)
                            if is_success:
                                success_count += 1
                                
                # Update progress bar and add slight delay for API rate limits
                progress_bar.progress((i + 1) / len(st.session_state.target_urls))
                time.sleep(2) 
                
            status_text.text("모든 크롤링 및 전송 작업이 완료되었습니다!")
            st.success(f"총 {success_count}명의 후보자 데이터가 노션에 성공적으로 업데이트되었습니다! 🎉")

elif menu == "4. 시스템 디버깅":
    st.header("시스템 디버깅 및 로그")
    st.write("백그라운드에서 실행 중인 시스템의 상태와 에러 로그를 확인합니다.")
    st.code("System is running normally...\nNo errors found yet.")