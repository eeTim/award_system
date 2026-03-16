import streamlit as st
import pandas as pd
import time
import logging

logging.basicConfig(filename='system.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 기존 코드: from ai_refiner import extract_candidate_info
from ai_refiner import extract_candidate_info, extract_org_info
from targeting_agent import extract_text_from_pdf, get_search_keywords_from_ai, search_target_urls
from raw_scraper import scrape_raw_text
from ai_refiner import extract_candidate_info
from notion_sync import create_notion_page

st.set_page_config(page_title="후보자 검증 AI 시스템", layout="wide")

# --- Session State Initialization ---
if 'theme_text' not in st.session_state: st.session_state.theme_text = ""
if 'target_orgs' not in st.session_state: st.session_state.target_orgs = [] # Updated to hold dicts, not just URLs
if 'basic_candidates' not in st.session_state: st.session_state.basic_candidates = []

# Button States
if 'run_phase1' not in st.session_state: st.session_state.run_phase1 = False
if 'run_phase2' not in st.session_state: st.session_state.run_phase2 = False
if 'run_phase3' not in st.session_state: st.session_state.run_phase3 = False

st.sidebar.title("시스템 컨트롤 패널")
menu = st.sidebar.radio(
    "메뉴를 선택하세요:",
    ("1. 시상 주제 업로드", "2. 1차: 타겟 기관 탐색", "3. 2차: 후보자 기초 스크랩", "4. 3차: 심층 검증 및 노션 전송", "5. 시스템 디버깅")
)

# --- TAB 1 ---
if menu == "1. 시상 주제 업로드":
    st.header("올해의 시상 테마 업로드")
    uploaded_file = st.file_uploader("심사 기준이 담긴 PDF 문서를 업로드해 주세요.", type="pdf")
    if uploaded_file is not None:
        with st.spinner("PDF 텍스트를 추출하는 중입니다..."):
            with open("temp_theme.pdf", "wb") as f: f.write(uploaded_file.getbuffer())
            extracted_text = extract_text_from_pdf("temp_theme.pdf")
            if extracted_text:
                st.session_state.theme_text = extracted_text
                st.success("파일 업로드 및 분석 성공!")
                with st.expander("추출된 텍스트 미리보기"): st.write(extracted_text[:500] + "...")

# --- TAB 2 ---
elif menu == "2. 1차: 타겟 기관 탐색":
    st.header("1차: AI 타겟 기관 탐색")
    st.write("AI가 대상 웹사이트를 찾고, 해당 기관의 핵심 정보를 파싱(Parsing)하여 리스트업합니다.")
    
    if not st.session_state.theme_text:
        st.warning("먼저 '1. 시상 주제 업로드' 탭에서 PDF 파일을 업로드해 주세요.")
        if st.button("샘플 텍스트로 강제 진행하기"):
            st.session_state.theme_text = "Climate Change Response and Inequality Resolution in Africa."
            st.rerun()
    else:
        # Button UI Logic (Start / Reset)
        col1, col2 = st.columns([1, 4])
        with col1:
            if st.button("기관 탐색 시작", disabled=st.session_state.run_phase1, use_container_width=True):
                st.session_state.run_phase1 = True
                st.rerun()
        with col2:
            if st.session_state.run_phase1 or len(st.session_state.target_orgs) > 0:
                if st.button("취소 및 초기화", use_container_width=False):
                    st.session_state.run_phase1 = False
                    st.session_state.target_orgs = []
                    st.rerun()

        # Execution Logic
        if st.session_state.run_phase1 and len(st.session_state.target_orgs) == 0:
            status_text = st.empty()
            status_text.info("AI가 검색어를 도출하고 기관 URL을 수집하고 있습니다...")
            
            search_queries = get_search_keywords_from_ai(st.session_state.theme_text)
            
            progress_bar = st.progress(0)
            temp_urls = set()
            
            # 1단계: URL 찾기 (진행도 0~30%)
            for i, query in enumerate(search_queries):
                urls = search_target_urls(query)
                temp_urls.update(urls)
                progress_bar.progress((i + 1) / len(search_queries) * 0.3)
                time.sleep(1)
            
            urls_list = list(temp_urls)[:10] # 테스트를 위해 최대 10개 기관만 파싱
            parsed_orgs = []
            
            # 2단계: 웹사이트 접속 및 AI 파싱 (진행도 30~100%)
            status_text.info(f"총 {len(urls_list)}개의 기관 웹사이트에 접속하여 세부 정보를 파싱 중입니다. 잠시만 기다려주세요...")
            
            for i, url in enumerate(urls_list):
                raw_text = scrape_raw_text(url) # 텍스트 긁어오기
                
                if raw_text and len(raw_text) > 100:
                    org_data = extract_org_info(raw_text, url) # AI가 5가지 정보로 파싱
                    parsed_orgs.append(org_data)
                else:
                    parsed_orgs.append({"기관명": "접속 불가 (보안 차단)", "URL": url, "시상 주제": "-", "최초 시상 년도": "-", "후보자 수(추정)": "-"})
                    
                progress_bar.progress(0.3 + ((i + 1) / len(urls_list)) * 0.7)
                time.sleep(1)
                
            status_text.empty() # 파싱이 다 끝나면 로딩 텍스트를 지움
            st.session_state.target_orgs = parsed_orgs
            st.rerun() # 모든 데이터가 준비된 후 화면을 새로고침하여 표를 띄움

        # Display Data
        if len(st.session_state.target_orgs) > 0:
            st.success(f"총 {len(st.session_state.target_orgs)}개의 타겟 기관 정보가 성공적으로 파싱되었습니다.")
            df_orgs = pd.DataFrame(st.session_state.target_orgs)
            st.dataframe(df_orgs, use_container_width=True)

# --- TAB 3 ---
elif menu == "3. 2차: 후보자 기초 스크랩":
    st.header("2차: 후보자 기초 스크랩 (리스트업)")
    
    if not st.session_state.target_orgs:
        st.warning("먼저 '2. 1차: 타겟 기관 탐색' 탭을 완료해 주세요.")
    else:
        st.info(f"파싱 완료된 기관 수: {len(st.session_state.target_orgs)}개")
        
        # Button UI Logic
        col1, col2 = st.columns([1, 4])
        with col1:
            if st.button("기초 정보 스크랩 시작", disabled=st.session_state.run_phase2, use_container_width=True):
                st.session_state.run_phase2 = True
                st.rerun()
        with col2:
            if st.session_state.run_phase2 or len(st.session_state.basic_candidates) > 0:
                if st.button("취소 및 리스트 초기화", use_container_width=False):
                    st.session_state.run_phase2 = False
                    st.session_state.basic_candidates = []
                    st.rerun()

        # Execution Logic
        if st.session_state.run_phase2 and len(st.session_state.basic_candidates) == 0:
            progress_bar = st.progress(0)
            status_text = st.empty()
            temp_candidates = []
            
            urls_to_scrape = [org["URL"] for org in st.session_state.target_orgs]
            
            for i, url in enumerate(urls_to_scrape):
                status_text.text(f"[{i+1}/{len(urls_to_scrape)}] 수집 중: {url}")
                raw_text = scrape_raw_text(url)
                if raw_text and len(raw_text) > 100:
                    ai_result = extract_candidate_info(raw_text)
                    if isinstance(ai_result, dict): temp_candidates.append(ai_result)
                    elif isinstance(ai_result, list): temp_candidates.extend(ai_result)
                        
                progress_bar.progress((i + 1) / len(urls_to_scrape))
                time.sleep(1)
                
            st.session_state.basic_candidates = [c for c in temp_candidates if isinstance(c, dict) and c.get("name")]
            st.rerun()

        # Display Data
        if len(st.session_state.basic_candidates) > 0:
            st.success(f"총 {len(st.session_state.basic_candidates)}명의 후보자가 임시 수집되었습니다.")
            df_candidates = pd.DataFrame(st.session_state.basic_candidates)
            st.dataframe(df_candidates, use_container_width=True)

# --- TAB 4 ---
elif menu == "4. 3차: 심층 검증 및 노션 전송":
    st.header("3차: 심층 검증 및 노션 전송")
    
    if not st.session_state.basic_candidates:
        st.warning("먼저 '3. 2차: 후보자 기초 스크랩' 탭에서 인물 리스트를 추출해 주세요.")
    else:
        st.info(f"심층 검증 대기 중인 후보자: {len(st.session_state.basic_candidates)}명")
        
        st.subheader("심층 검증 옵션 선택")
        col1, col2, col3 = st.columns(3)
        with col1: opt_news = st.checkbox("최근 언론 보도 (News)", value=True)
        with col2: opt_factcheck = st.checkbox("AI 팩트체크 (Fact Check)", value=True)
        with col3: opt_awards = st.checkbox("과거 수상 이력 (Past Awards)", value=False)
            
        # Button UI Logic
        col_btn1, col_btn2 = st.columns([1, 4])
        with col_btn1:
            if st.button("심층 검증 및 전송 시작", disabled=st.session_state.run_phase3, use_container_width=True):
                st.session_state.run_phase3 = True
                st.rerun()
        with col_btn2:
            if st.session_state.run_phase3:
                if st.button("상태 초기화"):
                    st.session_state.run_phase3 = False
                    st.rerun()
                    
        # Execution Logic
        if st.session_state.run_phase3:
            progress_bar = st.progress(0)
            status_text = st.empty()
            success_count = 0
            
            for i, candidate in enumerate(st.session_state.basic_candidates):
                name = candidate.get("name")
                status_text.text(f"[{i+1}/{len(st.session_state.basic_candidates)}] 심층 검증 및 전송 중: {name}")
                time.sleep(1) # Deep search logic placeholder
                is_success = create_notion_page(candidate)
                if is_success: success_count += 1
                progress_bar.progress((i + 1) / len(st.session_state.basic_candidates))
                
            st.success(f"총 {success_count}명의 후보자 데이터가 노션에 업데이트되었습니다.")
            st.session_state.run_phase3 = False # Reset after completion

# --- TAB 5 ---
elif menu == "5. 시스템 디버깅":
    st.header("시스템 디버깅 및 실시간 로그")
    if st.button("로그 새로고침"): st.rerun()
    try:
        with open('system.log', 'r') as f:
            st.text_area("Log Output", f.read()[-2000:], height=400)
    except FileNotFoundError:
        st.info("system.log 파일이 아직 생성되지 않았습니다.")