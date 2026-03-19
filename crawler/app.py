import streamlit as st
import pandas as pd
import time
import logging

# --- 🚀 [엔진 모듈 임포트] 우리가 만든 3대장 파일 연결 ---
from targeting_agent import (
    extract_text_from_pdf, 
    get_search_keywords_from_ai, 
    search_target_urls, 
    search_award_background, 
    search_award_winners
)
from raw_scraper import scrape_raw_text
from ai_refiner import (
    extract_initial_award_name, 
    verify_and_extract_org_info, 
    extract_candidate_info
)

logging.basicConfig(filename='system.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

st.set_page_config(page_title="후보자 검증 AI 시스템", layout="wide")

# ==========================================
# 1. 초기 데이터 및 Session State 세팅
# ==========================================

SUB1_KEYWORDS = [
    "award", "prize", "fellowship", "foundation", "program", "initiative", 
    "organization", "annual award", "international award", "global award"
]

SUB2_KEYWORDS = [
    "global", "africa", "asia", "europe", "korea", "kenya", "south africa", 
    "ngo", "nonprofit", "youth", "women", "environment", "climate"
]

if 'theme_text' not in st.session_state: st.session_state.theme_text = ""

if 'df_main_kw' not in st.session_state: st.session_state.df_main_kw = pd.DataFrame(columns=["선택", "주제 키워드"])
if 'df_sub1_kw' not in st.session_state: st.session_state.df_sub1_kw = pd.DataFrame({"선택": [True]*len(SUB1_KEYWORDS), "서브 키워드 1": SUB1_KEYWORDS})
if 'df_sub2_kw' not in st.session_state: st.session_state.df_sub2_kw = pd.DataFrame({"선택": [False]*len(SUB2_KEYWORDS), "서브 키워드 2": SUB2_KEYWORDS})
if 'df_combined' not in st.session_state: st.session_state.df_combined = pd.DataFrame(columns=["선택", "검색어"])
if 'df_urls' not in st.session_state: st.session_state.df_urls = pd.DataFrame(columns=["선택", "시상명", "URL"])

if 'step1_done' not in st.session_state: st.session_state.step1_done = False
if 'step2_done' not in st.session_state: st.session_state.step2_done = False
if 'step3_done' not in st.session_state: st.session_state.step3_done = False

# ==========================================
# 2. 사이드바 메뉴 
# ==========================================
st.sidebar.title("시스템 컨트롤 패널")
menu = st.sidebar.radio(
    "진행 단계를 선택하세요:",
    ("Step 1. 시상 주제 분석", "Step 2. 검색어 최종 조합", "Step 3. URL 수집 및 1차 검역", "Step 4. 심층 스크랩 및 검증", "Step 5. 시스템 디버깅")
)

# ==========================================
# 3. 메인 화면 로직
# ==========================================

# --- STEP 1 ---
if menu == "Step 1. 시상 주제 분석":
    st.header("Step 1. 시상 주제 분석 및 키워드 셋업")
    
    uploaded_file = st.file_uploader("심사 기준 PDF 문서를 업로드해 주세요.", type="pdf")
    if uploaded_file is not None:
        with st.spinner("PDF 텍스트 추출 중..."):
            with open("temp_theme.pdf", "wb") as f: f.write(uploaded_file.getbuffer())
            st.session_state.theme_text = extract_text_from_pdf("temp_theme.pdf")
            st.success("PDF 업로드 성공!")

    st.divider()
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("🚀 AI 주제 키워드 추출", disabled=st.session_state.step1_done, use_container_width=True):
            if not st.session_state.theme_text:
                st.warning("PDF를 먼저 업로드 해주세요!")
            else:
                with st.spinner("AI가 핵심 주제를 분석 중입니다..."):
                    st.session_state.step1_done = True
                    # 진짜 AI 엔진 가동!
                    main_kw_list = get_search_keywords_from_ai(st.session_state.theme_text)
                    st.session_state.df_main_kw = pd.DataFrame({"선택": [True]*len(main_kw_list), "주제 키워드": main_kw_list})
                    st.rerun()
            
    with col2:
        if st.session_state.step1_done:
            if st.button("취소 및 초기화", use_container_width=False):
                st.session_state.step1_done = False
                st.session_state.df_main_kw = pd.DataFrame(columns=["선택", "주제 키워드"])
                st.rerun()

    if st.session_state.step1_done:
        c1, c2, c3 = st.columns(3)
        with c1: st.session_state.df_main_kw = st.data_editor(st.session_state.df_main_kw, hide_index=True)
        with c2: st.session_state.df_sub1_kw = st.data_editor(st.session_state.df_sub1_kw, hide_index=True)
        with c3: st.session_state.df_sub2_kw = st.data_editor(st.session_state.df_sub2_kw, hide_index=True)

# --- STEP 2 ---
elif menu == "Step 2. 검색어 최종 조합":
    st.header("Step 2. 검색어 최종 조합")
    if not st.session_state.step1_done:
        st.warning("Step 1을 먼저 완료해 주세요.")
    else:
        col1, col2 = st.columns([1, 4])
        with col1:
            if st.button("조합 생성", disabled=st.session_state.step2_done, use_container_width=True):
                st.session_state.step2_done = True
                main_kws = st.session_state.df_main_kw[st.session_state.df_main_kw["선택"]]["주제 키워드"].tolist()
                sub1_kws = st.session_state.df_sub1_kw[st.session_state.df_sub1_kw["선택"]]["서브 키워드 1"].tolist()
                sub2_kws = st.session_state.df_sub2_kw[st.session_state.df_sub2_kw["선택"]]["서브 키워드 2"].tolist()
                
                combined_list = []
                for m in main_kws:
                    for s1 in sub1_kws: combined_list.append(f"{m} {s1}")
                for s2 in sub2_kws:
                    for m in main_kws:
                        for s1 in sub1_kws: combined_list.append(f"{s2} {m} {s1}")
                
                st.session_state.df_combined = pd.DataFrame({"선택": [True]*len(combined_list), "검색어": combined_list})
                st.rerun()
        with col2:
            if st.session_state.step2_done:
                if st.button("초기화", use_container_width=False):
                    st.session_state.step2_done = False
                    st.rerun()

        if st.session_state.step2_done:
            st.info(f"총 {len(st.session_state.df_combined)}개의 검색어가 생성되었습니다.")
            st.session_state.df_combined = st.data_editor(st.session_state.df_combined, hide_index=False, use_container_width=True)

# --- STEP 3 ---
elif menu == "Step 3. URL 수집 및 1차 검역":
    st.header("Step 3. URL 수집 및 1차 검역 (시상명 발췌)")
    if not st.session_state.step2_done:
        st.warning("Step 2를 먼저 완료해 주세요.")
    else:
        col1, col2 = st.columns([1, 4])
        with col1:
            if st.button("🚀 원문 스크랩 및 1차 추출", disabled=st.session_state.step3_done, use_container_width=True):
                st.session_state.step3_done = True
                active_queries = st.session_state.df_combined[st.session_state.df_combined["선택"]]["검색어"].tolist()
                
                # 🚨 엔진 보호: 테스트를 위해 상위 3개 검색어만 실행 (모두 돌리면 30분 넘게 걸릴 수 있음)
                test_queries = active_queries[:3] 
                st.info(f"API 제한 방지를 위해 활성화된 검색어 중 상위 {len(test_queries)}개만 시범 타격합니다.")
                
                progress_bar = st.progress(0)
                status_text = st.empty()
                results_list = []
                
                for i, query in enumerate(test_queries):
                    status_text.text(f"[{i+1}/{len(test_queries)}] 구글 검색 중: {query}")
                    urls_data = search_target_urls(query)
                    
                    for u_data in urls_data:
                        url = u_data['link']
                        status_text.text(f"원문 스크랩 중: {url[:50]}...")
                        raw_text = scrape_raw_text(url)
                        
                        if raw_text:
                            award_name = extract_initial_award_name(raw_text)
                            if award_name and "관련 없음" not in award_name:
                                results_list.append({"선택": True, "시상명": award_name, "URL": url})
                    progress_bar.progress((i + 1) / len(test_queries))
                
                st.session_state.df_urls = pd.DataFrame(results_list)
                status_text.empty()
                st.rerun()
                
        with col2:
            if st.session_state.step3_done:
                if st.button("결과 취소", use_container_width=False):
                    st.session_state.step3_done = False
                    st.session_state.df_urls = pd.DataFrame(columns=["선택", "시상명", "URL"])
                    st.rerun()

        if st.session_state.step3_done:
            st.success("블랙리스트를 통과한 원문에서 정확한 시상명을 발췌했습니다.")
            st.session_state.df_urls = st.data_editor(st.session_state.df_urls, hide_index=False, use_container_width=True)

# --- STEP 4 ---
elif menu == "Step 4. 심층 스크랩 및 검증":
    st.header("Step 4. 심층 팩트체크 및 수상자 발굴")
    if not st.session_state.step3_done:
        st.warning("Step 3를 먼저 완료해 주세요.")
    else:
        final_targets = st.session_state.df_urls[st.session_state.df_urls["선택"]]
        st.info(f"현재 대기 중인 타겟 수: {len(final_targets)}개")
        
        if st.button("🚀 최종 교차 검증 및 인물 발굴 시작", type="primary"):
            st.divider()
            
            for idx, row in final_targets.iterrows():
                award_name = row['시상명']
                orig_url = row['URL']
                
                with st.expander(f"🔍 [타겟 분석 중] {award_name}", expanded=True):
                    # 1. 기관 정보 교차 검증 (OSINT)
                    st.write("1. 구글 딥서치로 배경지식 교차 검증 중...")
                    bg_context = search_award_background(award_name)
                    orig_text = scrape_raw_text(orig_url)
                    
                    org_info = verify_and_extract_org_info(orig_text, bg_context, orig_url)
                    st.json(org_info)
                    
                    # 2. 수상자/후보자 탐색 (OSINT)
                    st.write("2. 구글 뉴스/발표문 기반 수상자 명단 탐색 중...")
                    winner_urls = search_award_winners(award_name)
                    all_candidates = []
                    
                    for w_data in winner_urls:
                        w_text = scrape_raw_text(w_data['link'])
                        if w_text:
                            cands = extract_candidate_info(w_text)
                            all_candidates.extend(cands)
                    
                    if all_candidates:
                        st.success(f"총 {len(all_candidates)}명의 후보자/수상자 발견!")
                        st.dataframe(pd.DataFrame(all_candidates))
                    else:
                        st.warning("발견된 후보자가 없습니다.")

# --- STEP 5 ---
elif menu == "Step 5. 시스템 디버깅":
    st.header("시스템 디버깅 및 실시간 로그")
    if st.button("로그 새로고침"): st.rerun()
    try:
        with open('system.log', 'r') as f:
            st.text_area("Log Output", f.read()[-3000:], height=400)
    except FileNotFoundError:
        st.info("system.log 파일이 아직 생성되지 않았습니다.")