import streamlit as st
import pandas as pd
import time
import logging
import os

# Set up basic logging to file for Tab 5 (Debugging)
logging.basicConfig(
    filename='system.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

from targeting_agent import extract_text_from_pdf, get_search_keywords_from_ai, search_target_urls
from raw_scraper import scrape_raw_text
from ai_refiner import extract_candidate_info
from notion_sync import create_notion_page

# 1. Basic web page configuration
st.set_page_config(page_title="후보자 검증 AI 시스템", layout="wide")

# 2. Initialize Session State for 5-step flow
if 'theme_text' not in st.session_state:
    st.session_state.theme_text = ""
if 'target_urls' not in st.session_state:
    st.session_state.target_urls = []
if 'basic_candidates' not in st.session_state:
    st.session_state.basic_candidates = [] # Holds data from Phase 2

# 3. Create left sidebar menu
st.sidebar.title("시스템 컨트롤 패널")
menu = st.sidebar.radio(
    "메뉴를 선택하세요:",
    (
        "1. 시상 주제 업로드", 
        "2. 1차: 타겟 기관 탐색", 
        "3. 2차: 후보자 기초 스크랩", 
        "4. 3차: 심층 검증 및 노션 전송", 
        "5. 시스템 디버깅"
    )
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
                logging.info("Theme PDF successfully uploaded and extracted.")
                st.success("파일이 성공적으로 업로드 및 분석되었습니다!")
                with st.expander("추출된 텍스트 미리보기"):
                    st.write(extracted_text[:500] + " ... (이하 생략)")
            else:
                logging.error("Failed to extract text from PDF.")
                st.error("텍스트 추출에 실패했습니다. 파일 형식을 확인해 주세요.")

elif menu == "2. 1차: 타겟 기관 탐색":
    st.header("1차: AI 타겟 기관 탐색")
    st.write("AI가 테마를 분석하여 대상 웹사이트를 찾고 기관 정보를 요약합니다.")
    
    if not st.session_state.theme_text:
        st.warning("먼저 '1. 시상 주제 업로드' 탭에서 PDF 파일을 업로드해 주세요.")
        if st.button("테스트용 샘플 텍스트로 강제 진행하기"):
            st.session_state.theme_text = "The award theme for this year is 'Climate Change Response and Inequality Resolution in Africa'."
            st.rerun()
    else:
        if st.button("기관 탐색 및 정보 수집 시작"):
            st.info("AI가 검색어를 도출하고 기관 URL을 수집합니다...")
            logging.info("Phase 1: Starting target organization search.")
            
            search_queries = get_search_keywords_from_ai(st.session_state.theme_text)
            
            progress_bar = st.progress(0)
            all_target_urls = set()
            
            for i, query in enumerate(search_queries):
                urls = search_target_urls(query)
                all_target_urls.update(urls)
                progress_bar.progress((i + 1) / len(search_queries))
                time.sleep(1)
                
            st.session_state.target_urls = list(all_target_urls)
            logging.info(f"Phase 1: Found {len(st.session_state.target_urls)} URLs.")
            
            st.success(f"총 {len(st.session_state.target_urls)}개의 타겟 기관 URL 수집 완료!")
            
            # Display as a table for user review
            df_urls = pd.DataFrame(st.session_state.target_urls, columns=["Target URL"])
            st.dataframe(df_urls, use_container_width=True)

elif menu == "3. 2차: 후보자 기초 스크랩":
    st.header("2차: 후보자 기초 스크랩 (리스트업)")
    st.write("수집된 기관 웹사이트에서 후보자들의 기초 정보(이름, 1줄 요약)만 빠르게 수집합니다.")
    
    if not st.session_state.target_urls:
        st.warning("먼저 '2. 1차: 타겟 기관 탐색' 탭을 완료해 주세요.")
        if st.button("테스트용 샘플 URL 1개로 강제 진행하기"):
            st.session_state.target_urls = ["https://earthshotprize.org/news/africas-climate-leadership-highlights-and-reflections-from-kenya-connect/"]
            st.rerun()
    else:
        st.info(f"현재 대기 중인 타겟 웹사이트: {len(st.session_state.target_urls)}개")
        
        if st.button("기초 정보 스크랩 시작 (노션 전송 X)"):
            progress_bar = st.progress(0)
            status_text = st.empty()
            temp_candidates = []
            
            for i, url in enumerate(st.session_state.target_urls):
                status_text.text(f"[{i+1}/{len(st.session_state.target_urls)}] 수집 중: {url}")
                logging.info(f"Phase 2: Scraping URL: {url}")
                
                raw_text = scrape_raw_text(url)
                if raw_text and len(raw_text) > 100:
                    ai_result = extract_candidate_info(raw_text)
                    
                    if isinstance(ai_result, dict):
                        temp_candidates.append(ai_result)
                    elif isinstance(ai_result, list):
                        temp_candidates.extend(ai_result)
                        
                progress_bar.progress((i + 1) / len(st.session_state.target_urls))
                time.sleep(1)
                
            # Filter out invalid names
            st.session_state.basic_candidates = [
                c for c in temp_candidates 
                if isinstance(c, dict) and c.get("name") and c.get("name") not in ["Not Found", "Unknown"]
            ]
            
            status_text.text("기초 스크랩이 완료되었습니다. 아래 표를 확인해 주세요.")
            logging.info(f"Phase 2: Scraped {len(st.session_state.basic_candidates)} candidates.")
            
        # Display candidates in a UI table if they exist in session state
        if st.session_state.basic_candidates:
            st.success(f"총 {len(st.session_state.basic_candidates)}명의 후보자가 임시 수집되었습니다.")
            df_candidates = pd.DataFrame(st.session_state.basic_candidates)
            st.dataframe(df_candidates, use_container_width=True)

elif menu == "4. 3차: 심층 검증 및 노션 전송":
    st.header("3차: 심층 검증 및 노션 전송")
    st.write("2차에서 수집된 리스트를 바탕으로, 선택한 항목에 대해 심층 딥서치를 진행한 후 노션으로 전송합니다.")
    
    if not st.session_state.basic_candidates:
        st.warning("먼저 '3. 2차: 후보자 기초 스크랩' 탭에서 인물 리스트를 추출해 주세요.")
    else:
        st.info(f"심층 검증 대기 중인 후보자: {len(st.session_state.basic_candidates)}명")
        
        # Checkbox Options for Deep Search
        st.subheader("심층 검증 옵션 선택")
        col1, col2, col3 = st.columns(3)
        with col1:
            opt_news = st.checkbox("최근 언론 보도 (News)", value=True)
        with col2:
            opt_factcheck = st.checkbox("AI 팩트체크 (Fact Check)", value=True)
        with col3:
            opt_awards = st.checkbox("과거 수상 이력 (Past Awards)", value=False)
            
        if st.button("선택 항목 심층 검증 및 노션 전송"):
            progress_bar = st.progress(0)
            status_text = st.empty()
            success_count = 0
            
            for i, candidate in enumerate(st.session_state.basic_candidates):
                name = candidate.get("name")
                status_text.text(f"[{i+1}/{len(st.session_state.basic_candidates)}] 심층 검증 중: {name}")
                logging.info(f"Phase 3: Deep Dive for {name}. Options: News={opt_news}, FactCheck={opt_factcheck}")
                
                # Placeholder for Deep Search Agent Logic (To be implemented)
                time.sleep(1) 
                
                status_text.text(f"[{i+1}/{len(st.session_state.basic_candidates)}] 노션 DB로 전송 중: {name}")
                is_success = create_notion_page(candidate)
                if is_success:
                    success_count += 1
                    logging.info(f"Phase 3: Successfully sent {name} to Notion.")
                    
                progress_bar.progress((i + 1) / len(st.session_state.basic_candidates))
                
            status_text.text("모든 심층 검증 및 노션 전송이 완료되었습니다!")
            st.success(f"총 {success_count}명의 후보자 데이터가 노션에 업데이트되었습니다.")

elif menu == "5. 시스템 디버깅":
    st.header("시스템 디버깅 및 실시간 로그")
    st.write("백그라운드 파이썬 스크립트의 실행 로그를 확인합니다.")
    
    if st.button("로그 새로고침"):
        st.rerun()
        
    try:
        with open('system.log', 'r') as f:
            logs = f.read()
            # Show the last 2000 characters of the log
            st.text_area("Log Output", logs[-2000:], height=400)
    except FileNotFoundError:
        st.info("system.log 파일이 아직 생성되지 않았습니다.")