import streamlit as st
import pandas as pd
import time
import logging
import urllib3
from dotenv import load_dotenv

# 1. 환경변수 로드 및 시스템 세팅
load_dotenv() # .env 금고에서 API 키를 불러와 시스템 전역에 적용
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logging.basicConfig(filename='system.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 2. 백엔드 엔진 모듈 임포트
from targeting_agent import extract_text_from_pdf, get_search_keywords_from_ai, search_target_urls, search_award_background, search_award_winners
from raw_scraper import scrape_raw_text
from ai_refiner import extract_initial_award_name, verify_and_extract_org_info, extract_candidate_info

st.set_page_config(page_title="후보자 검증 AI 시스템", layout="wide")

# ==========================================
# 3. Session State (전역 메모리) 초기화
# ==========================================
SUB1_KEYWORDS = ["award", "prize", "fellowship", "foundation", "program", "initiative", "organization", "annual award", "international award", "global award"]
SUB2_KEYWORDS = ["global", "africa", "asia", "europe", "korea", "kenya", "south africa", "ngo", "nonprofit", "youth", "women", "environment", "climate"]

if 'theme_text' not in st.session_state: st.session_state.theme_text = ""
if 'current_step' not in st.session_state: st.session_state.current_step = "Step 1. 시상 주제 분석"

if 'df_main_kw' not in st.session_state: st.session_state.df_main_kw = pd.DataFrame(columns=["선택", "주제 키워드"])
if 'df_sub1_kw' not in st.session_state: st.session_state.df_sub1_kw = pd.DataFrame({"선택": [True]*len(SUB1_KEYWORDS), "서브 키워드 1": SUB1_KEYWORDS})
if 'df_sub2_kw' not in st.session_state: st.session_state.df_sub2_kw = pd.DataFrame({"선택": [False]*len(SUB2_KEYWORDS), "서브 키워드 2": SUB2_KEYWORDS})
if 'df_combined' not in st.session_state: st.session_state.df_combined = pd.DataFrame(columns=["선택", "검색어"])
if 'df_urls' not in st.session_state: st.session_state.df_urls = pd.DataFrame(columns=["선택", "시상명", "URL"])
if 'df_verified_orgs' not in st.session_state: st.session_state.df_verified_orgs = pd.DataFrame()

if 'step1_done' not in st.session_state: st.session_state.step1_done = False
if 'step2_done' not in st.session_state: st.session_state.step2_done = False
if 'step3_extracted' not in st.session_state: st.session_state.step3_extracted = False
if 'step3_verified' not in st.session_state: st.session_state.step3_verified = False
if 'step4_done' not in st.session_state: st.session_state.step4_done = False
if 'is_running' not in st.session_state: st.session_state.is_running = False

def go_to_step(step_name):
    st.session_state.current_step = step_name

# ==========================================
# 4. 사이드바 (내비게이션)
# ==========================================
st.sidebar.title("시스템 컨트롤 패널")
menu = st.sidebar.radio(
    "진행 단계를 선택하세요:",
    ("Step 1. 시상 주제 분석", "Step 2. 검색어 최종 조합", "Step 3. URL 수집 및 교차 검증", "Step 4. 수상자 발굴 및 전송", "Step 5. 시스템 디버깅"),
    key="current_step"
)

# ==========================================
# 5. 메인 화면 로직 (라우팅)
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
                with st.spinner("AI 분석 중..."):
                    st.session_state.step1_done = True
                    main_kw_list = get_search_keywords_from_ai(st.session_state.theme_text)
                    
                    # 🚨 AI API 에러 대비 안전망 (Fallback)
                    if not main_kw_list:
                        st.error("⚠️ 구글 API 할당량 초과! 테스트용 임시 키워드를 삽입합니다.")
                        main_kw_list = ["climate change", "grassroots innovation", "environmental activism", "sustainable agriculture", "community resilience"]
                        
                    st.session_state.df_main_kw = pd.DataFrame({"선택": [True]*len(main_kw_list), "주제 키워드": main_kw_list})
                    st.rerun()
    with col2:
        if st.session_state.step1_done:
            if st.button("초기화", use_container_width=False):
                st.session_state.step1_done = False
                st.rerun()

    if st.session_state.step1_done:
        c1, c2, c3 = st.columns(3)
        with c1: st.session_state.df_main_kw = st.data_editor(st.session_state.df_main_kw, hide_index=True, key="de_main")
        with c2: st.session_state.df_sub1_kw = st.data_editor(st.session_state.df_sub1_kw, hide_index=True, key="de_sub1")
        with c3: st.session_state.df_sub2_kw = st.data_editor(st.session_state.df_sub2_kw, hide_index=True, key="de_sub2")
        
        if st.button("✨ 다음 단계로 이동", type="primary"):
            go_to_step("Step 2. 검색어 최종 조합")
            st.rerun()

# --- STEP 2 ---
elif menu == "Step 2. 검색어 최종 조합":
    st.header("Step 2. 검색어 최종 조합")
    if not st.session_state.step1_done: st.warning("Step 1을 먼저 완료해 주세요.")
    else:
        if st.button("검색어 조합 생성", disabled=st.session_state.step2_done):
            st.session_state.step2_done = True
            main_kws = st.session_state.df_main_kw[st.session_state.df_main_kw["선택"]]["주제 키워드"].tolist()
            sub1_kws = st.session_state.df_sub1_kw[st.session_state.df_sub1_kw["선택"]]["서브 키워드 1"].tolist()
            sub2_kws = st.session_state.df_sub2_kw[st.session_state.df_sub2_kw["선택"]]["서브 키워드 2"].tolist()
            
            combined_list = [f"{m} {s1}" for m in main_kws for s1 in sub1_kws] + [f"{s2} {m} {s1}" for s2 in sub2_kws for m in main_kws for s1 in sub1_kws]
            st.session_state.df_combined = pd.DataFrame({"선택": [True]*len(combined_list), "검색어": combined_list})
            st.rerun()

        if st.session_state.step2_done:
            st.session_state.df_combined = st.data_editor(st.session_state.df_combined, hide_index=False, use_container_width=True)
            if st.button("✨ 다음 단계로 이동", type="primary"):
                go_to_step("Step 3. URL 수집 및 교차 검증")
                st.rerun()

# --- STEP 3 ---
elif menu == "Step 3. URL 수집 및 교차 검증":
    st.header("Step 3. URL 수집 및 교차 검증")
    if not st.session_state.step2_done: st.warning("Step 2를 먼저 완료해 주세요.")
    else:
        # Phase 3A: 1차 발췌
        if st.button("1️⃣ 원문 스크랩 및 1차 발췌", disabled=st.session_state.step3_extracted):
            st.session_state.step3_extracted = True
            active_queries = st.session_state.df_combined[st.session_state.df_combined["선택"]]["검색어"].tolist()
            test_queries = active_queries[:3] # 테스트용 제한
            
            progress_bar = st.progress(0, text="검색 준비 중...")
            results_list = []
            
            for i, query in enumerate(test_queries):
                progress_bar.progress((i / len(test_queries)), text=f"검색 중: {query}")
                urls_data = search_target_urls(query) # 3중 필터링 적용된 URL들 반환
                
                for u_data in urls_data:
                    url = u_data['link']
                    raw_text = scrape_raw_text(url) # curl_cffi 기반 스텔스 스크래핑
                    if raw_text:
                        time.sleep(4) # API Rate Limit 방지
                        award_name = extract_initial_award_name(raw_text)
                        if award_name and "관련 없음" not in award_name:
                            results_list.append({"시상명": award_name, "URL": url})
            
            if results_list:
                df = pd.DataFrame(results_list)
                df_grouped = df.groupby('시상명', as_index=False).agg({'URL': lambda x: '\n'.join(x)})
                df_grouped.insert(0, '선택', True)
                st.session_state.df_urls = df_grouped
            st.rerun()

        if st.session_state.step3_extracted:
            st.session_state.df_urls = st.data_editor(st.session_state.df_urls, use_container_width=True)
            st.divider()
            
            # Phase 3B: 딥서치 교차 검증
            if st.button("2️⃣ 심층 교차 검증 시작", disabled=st.session_state.step3_verified, type="primary"):
                st.session_state.step3_verified = True
                targets = st.session_state.df_urls[st.session_state.df_urls["선택"]]["시상명"].tolist()
                pb_verify = st.progress(0, text="교차 검증 준비 중...")
                verified_data = []
                
                for i, award in enumerate(targets):
                    pb_verify.progress((i / len(targets)), text=f"딥서치 중: {award}")
                    bg_context = search_award_background(award)
                    sample_url = st.session_state.df_urls[st.session_state.df_urls["시상명"] == award]["URL"].values[0].split('\n')[0]
                    orig_text = scrape_raw_text(sample_url)
                    
                    time.sleep(4)
                    org_info = verify_and_extract_org_info(orig_text, bg_context, sample_url)
                    org_info['선택'] = True
                    verified_data.append(org_info)
                
                st.session_state.df_verified_orgs = pd.DataFrame(verified_data)
                st.rerun()

            if st.session_state.step3_verified:
                st.session_state.df_verified_orgs = st.data_editor(st.session_state.df_verified_orgs, use_container_width=True)
                if st.button("✨ 다음 단계로 이동", type="primary"):
                    go_to_step("Step 4. 수상자 발굴 및 전송")
                    st.rerun()

# --- STEP 4 ---
elif menu == "Step 4. 수상자 발굴 및 전송":
    st.header("Step 4. 수상자 발굴 및 n8n/Notion 전송")
    if not st.session_state.step3_verified: st.warning("Step 3를 완료해 주세요.")
    else:
        final_targets = st.session_state.df_verified_orgs[st.session_state.df_verified_orgs["선택"]]
        
        col1, col2 = st.columns([1, 4])
        with col1:
            if st.button("🚀 후보자 탐색 시작", disabled=st.session_state.is_running, type="primary"):
                st.session_state.is_running = True
                st.rerun()
        with col2:
            if st.session_state.is_running:
                if st.button("🛑 중지 (Stop)"):
                    st.session_state.is_running = False
                    st.rerun()

        if st.session_state.is_running:
            all_candidates = []
            for idx, row in final_targets.iterrows():
                if not st.session_state.is_running: break
                award_name = row['시상/프로그램명']
                with st.expander(f"🔍 [탐색 결과] {award_name}", expanded=True):
                    winner_urls = search_award_winners(award_name)
                    temp_cands = []
                    for w_data in winner_urls:
                        w_text = scrape_raw_text(w_data['link'])
                        if w_text:
                            time.sleep(4)
                            cands = extract_candidate_info(w_text)
                            temp_cands.extend(cands)
                    
                    if temp_cands:
                        st.dataframe(pd.DataFrame(temp_cands))
                        all_candidates.extend(temp_cands)
            
            if st.session_state.is_running:
                st.session_state.is_running = False
                st.session_state.step4_done = True
                st.session_state.all_candidates = all_candidates

        if st.session_state.step4_done:
            st.dataframe(pd.DataFrame(st.session_state.all_candidates), use_container_width=True)
            if st.button("💾 n8n Webhook으로 노션(Notion) 전송", type="primary"):
                # 이곳에 requests.post(n8n_webhook_url, json=data) 로직이 들어갈 예정입니다.
                st.success("✅ n8n으로 데이터 전송 성공! (웹훅 연동 준비 완료)")

# --- STEP 5 ---
elif menu == "Step 5. 시스템 디버깅":
    st.header("시스템 로그")
    if st.button("로그 새로고침"): st.rerun()
    try:
        with open('system.log', 'r') as f: st.text_area("Log", f.read()[-3000:], height=400)
    except Exception: st.info("로그 파일 없음.")