import streamlit as st
import pandas as pd
import time
import logging
import urllib3

# SSL 경고문 숨기기 (터미널 깔끔하게 유지)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logging.basicConfig(filename='system.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

from targeting_agent import extract_text_from_pdf, get_search_keywords_from_ai, search_target_urls, search_award_background, search_award_winners
from raw_scraper import scrape_raw_text
from ai_refiner import extract_initial_award_name, verify_and_extract_org_info, extract_candidate_info

st.set_page_config(page_title="후보자 검증 AI 시스템", layout="wide")

# ==========================================
# 1. 초기 데이터 및 Session State 세팅
# ==========================================
SUB1_KEYWORDS = ["award", "prize", "fellowship", "foundation", "program", "initiative", "organization", "annual award", "international award", "global award"]
SUB2_KEYWORDS = ["global", "africa", "asia", "europe", "korea", "kenya", "south africa", "ngo", "nonprofit", "youth", "women", "environment", "climate"]

if 'theme_text' not in st.session_state: st.session_state.theme_text = ""
if 'current_step' not in st.session_state: st.session_state.current_step = "Step 1. 시상 주제 분석"

# 데이터 프레임 상태
if 'df_main_kw' not in st.session_state: st.session_state.df_main_kw = pd.DataFrame(columns=["선택", "주제 키워드"])
if 'df_sub1_kw' not in st.session_state: st.session_state.df_sub1_kw = pd.DataFrame({"선택": [True]*len(SUB1_KEYWORDS), "서브 키워드 1": SUB1_KEYWORDS})
if 'df_sub2_kw' not in st.session_state: st.session_state.df_sub2_kw = pd.DataFrame({"선택": [False]*len(SUB2_KEYWORDS), "서브 키워드 2": SUB2_KEYWORDS})
if 'df_combined' not in st.session_state: st.session_state.df_combined = pd.DataFrame(columns=["선택", "검색어"])
if 'df_urls' not in st.session_state: st.session_state.df_urls = pd.DataFrame(columns=["선택", "시상명", "URL"])
if 'df_verified_orgs' not in st.session_state: st.session_state.df_verified_orgs = pd.DataFrame()

# 진행 상태 토글
if 'step1_done' not in st.session_state: st.session_state.step1_done = False
if 'step2_done' not in st.session_state: st.session_state.step2_done = False
if 'step3_extracted' not in st.session_state: st.session_state.step3_extracted = False
if 'step3_verified' not in st.session_state: st.session_state.step3_verified = False
if 'step4_done' not in st.session_state: st.session_state.step4_done = False
if 'is_running' not in st.session_state: st.session_state.is_running = False

def go_to_step(step_name):
    st.session_state.current_step = step_name

# ==========================================
# 2. 사이드바 메뉴 
# ==========================================
st.sidebar.title("시스템 컨트롤 패널")
menu = st.sidebar.radio(
    "진행 단계를 선택하세요:",
    ("Step 1. 시상 주제 분석", "Step 2. 검색어 최종 조합", "Step 3. URL 수집 및 교차 검증", "Step 4. 수상자 발굴 및 전송", "Step 5. 시스템 디버깅"),
    key="current_step"
)

# ==========================================
# 3. 메인 화면 로직
# ==========================================

# --- STEP 1 ---
if menu == "Step 1. 시상 주제 분석":
    st.header("Step 1. 시상 주제 분석 및 키워드 셋업")
    st.caption("📌 **[목적]** 심사 기준 PDF에서 AI가 핵심 테마를 추출하고, 실무자가 서브 키워드를 결합할 준비를 합니다.")
    st.caption("👉 **[가이드]** PDF 업로드 ➡️ 'AI 키워드 추출' 클릭 ➡️ 하단 표에서 검색에 쓸 키워드 체크 ➡️ '다음 단계로' 클릭")
    
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
        # key 부여로 즉각적인 화면 새로고침(Lag) 방지
        with c1: st.session_state.df_main_kw = st.data_editor(st.session_state.df_main_kw, hide_index=True, key="de_main")
        with c2: st.session_state.df_sub1_kw = st.data_editor(st.session_state.df_sub1_kw, hide_index=True, key="de_sub1")
        with c3: st.session_state.df_sub2_kw = st.data_editor(st.session_state.df_sub2_kw, hide_index=True, key="de_sub2")
        
        st.divider()
        if st.button("✨ 키워드 선택 완료! 다음 단계로 이동", type="primary"):
            go_to_step("Step 2. 검색어 최종 조합")
            st.rerun()

# --- STEP 2 ---
elif menu == "Step 2. 검색어 최종 조합":
    st.header("Step 2. 검색어 최종 조합")
    st.caption("📌 **[목적]** 체크된 주제와 서브 키워드를 곱하여(x) 구글에 타격할 최종 검색어 리스트를 생성합니다.")
    st.caption("👉 **[가이드]** '조합 생성' 클릭 ➡️ 리스트 확인 및 불필요한 검색어 체크 해제 ➡️ '다음 단계로' 클릭")

    if not st.session_state.step1_done:
        st.warning("Step 1을 먼저 완료해 주세요.")
    else:
        col1, col2 = st.columns([1, 4])
        with col1:
            if st.button("검색어 조합 생성", disabled=st.session_state.step2_done, use_container_width=True):
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
            
            st.divider()
            if st.button("✨ 조합 확인 완료! 다음 단계로 이동", type="primary"):
                go_to_step("Step 3. URL 수집 및 교차 검증")
                st.rerun()

# --- STEP 3 ---
elif menu == "Step 3. URL 수집 및 교차 검증":
    st.header("Step 3. URL 수집 및 교차 검증")
    st.caption("📌 **[목적]** 검색어로 웹사이트를 긁어와 정확한 '시상명'을 1차 발췌하고(중복 제거), 구글 딥서치를 통해 공식 기관 정보를 교차 검증합니다.")
    st.caption("👉 **[가이드]** '원문 스크랩(1차)' 클릭 ➡️ 추출된 시상명 표 확인 ➡️ '심층 교차 검증' 클릭")

    if not st.session_state.step2_done:
        st.warning("Step 2를 먼저 완료해 주세요.")
    else:
        # [Phase 3A]: 1차 발췌 및 중복 제거
        col1, col2 = st.columns([1, 4])
        with col1:
            if st.button("1️⃣ 원문 스크랩 및 1차 발췌", disabled=st.session_state.step3_extracted, use_container_width=True):
                st.session_state.step3_extracted = True
                active_queries = st.session_state.df_combined[st.session_state.df_combined["선택"]]["검색어"].tolist()
                test_queries = active_queries[:3] 
                
                progress_bar = st.progress(0, text="0% 완료 - 구글 검색 준비 중...")
                results_list = []
                
                for i, query in enumerate(test_queries):
                    percent = int(((i) / len(test_queries)) * 100)
                    progress_bar.progress(percent / 100, text=f"{percent}% 완료 - 🔍 검색 중: {query}")
                    urls_data = search_target_urls(query)
                    
                    for u_data in urls_data:
                        url = u_data['link']
                        raw_text = scrape_raw_text(url)
                        if raw_text:
                            time.sleep(4) # 🚨 API Rate Limit(429) 방지를 위한 강제 휴식
                            award_name = extract_initial_award_name(raw_text)
                            if award_name and "관련 없음" not in award_name:
                                results_list.append({"시상명": award_name, "URL": url})
                
                progress_bar.progress(1.0, text="100% 완료!")
                
                # 중복 기관명 합치기 로직
                if results_list:
                    df = pd.DataFrame(results_list)
                    # 동일한 시상명끼리 묶고 URL은 콤마로 이어붙임
                    df_grouped = df.groupby('시상명', as_index=False).agg({'URL': lambda x: '\n'.join(x)})
                    df_grouped.insert(0, '선택', True)
                    st.session_state.df_urls = df_grouped
                st.rerun()

        with col2:
            if st.session_state.step3_extracted:
                if st.button("1차 발췌 취소", use_container_width=False):
                    st.session_state.step3_extracted = False
                    st.session_state.df_urls = pd.DataFrame(columns=["선택", "시상명", "URL"])
                    st.rerun()

        if st.session_state.step3_extracted:
            st.success("1차 발췌 및 중복 제거가 완료되었습니다. 교차 검증을 진행할 기관을 체크해 주세요.")
            st.session_state.df_urls = st.data_editor(st.session_state.df_urls, hide_index=False, use_container_width=True)

            st.divider()
            
            # [Phase 3B]: 딥서치 교차 검증
            c1, c2 = st.columns([1, 4])
            with c1:
                if st.button("2️⃣ 심층 교차 검증 시작", disabled=st.session_state.step3_verified, type="primary", use_container_width=True):
                    st.session_state.step3_verified = True
                    targets = st.session_state.df_urls[st.session_state.df_urls["선택"]]["시상명"].tolist()
                    
                    pb_verify = st.progress(0, text="0% - 교차 검증 준비 중...")
                    verified_data = []
                    
                    for i, award in enumerate(targets):
                        percent = int((i / len(targets)) * 100)
                        pb_verify.progress(percent / 100, text=f"{percent}% 진행중 - 🔍 딥서치 중: {award}")
                        
                        bg_context = search_award_background(award)
                        # 원문 1개만 샘플로 가져옴
                        sample_url = st.session_state.df_urls[st.session_state.df_urls["시상명"] == award]["URL"].values[0].split('\n')[0]
                        orig_text = scrape_raw_text(sample_url)
                        
                        time.sleep(4) # 🚨 API 에러 방지용 휴식
                        org_info = verify_and_extract_org_info(orig_text, bg_context, sample_url)
                        org_info['선택'] = True
                        verified_data.append(org_info)
                    
                    pb_verify.progress(1.0, text="100% 완료!")
                    st.session_state.df_verified_orgs = pd.DataFrame(verified_data)
                    # 보기 좋게 열 순서 재배치
                    st.session_state.df_verified_orgs = st.session_state.df_verified_orgs[['선택', '시상/프로그램명', '주최/관련 기관', '시상 주제', '출처 유형', 'URL']]
                    st.rerun()
            
            with c2:
                if st.session_state.step3_verified:
                    if st.button("검증 결과 취소", use_container_width=False):
                        st.session_state.step3_verified = False
                        st.session_state.df_verified_orgs = pd.DataFrame()
                        st.rerun()

            if st.session_state.step3_verified:
                st.info("✅ 팩트체크가 완료된 확정 기관 명단입니다.")
                st.session_state.df_verified_orgs = st.data_editor(st.session_state.df_verified_orgs, hide_index=False, use_container_width=True)
                
                st.divider()
                if st.button("✨ 기관 검증 완료! 다음 단계로 이동", type="primary"):
                    go_to_step("Step 4. 수상자 발굴 및 전송")
                    st.rerun()

# --- STEP 4 ---
elif menu == "Step 4. 수상자 발굴 및 전송":
    st.header("Step 4. 수상자 발굴 및 노션 전송")
    st.caption("📌 **[목적]** 확정된 기관명으로 구글 OSINT 검색을 수행하여 뉴스 기사 등에 숨어있는 후보자/수상자를 색출하고 DB로 보냅니다.")
    st.caption("👉 **[가이드]** '후보자 탐색 시작' 클릭 ➡️ 명단 확인 ➡️ '노션으로 일괄 전송' 클릭")

    if not st.session_state.step3_verified:
        st.warning("Step 3에서 기관 교차 검증을 먼저 완료해 주세요.")
    else:
        final_targets = st.session_state.df_verified_orgs[st.session_state.df_verified_orgs["선택"]]
        st.info(f"현재 대기 중인 타겟 기관 수: {len(final_targets)}개")
        
        col1, col2 = st.columns([1, 4])
        with col1:
            if st.button("🚀 후보자 탐색 시작", disabled=st.session_state.is_running, type="primary", use_container_width=True):
                st.session_state.is_running = True
                st.rerun()
        with col2:
            if st.session_state.is_running:
                if st.button("🛑 중지 (Stop)", type="secondary"):
                    st.session_state.is_running = False
                    st.warning("작업이 중지되었습니다.")
                    st.rerun()

        if st.session_state.is_running:
            st.divider()
            all_candidates = []
            pb_cand = st.progress(0, text="수상자 수색을 준비 중입니다...")
            
            for idx, row in final_targets.iterrows():
                if not st.session_state.is_running: break # 중지 버튼 체크
                
                award_name = row['시상/프로그램명']
                percent = int((idx / len(final_targets)) * 100)
                pb_cand.progress(percent / 100, text=f"{percent}% 진행중 - 🕵️ [{award_name}] 수상자 수색 중...")
                
                with st.expander(f"🔍 [탐색 결과] {award_name}", expanded=True):
                    winner_urls = search_award_winners(award_name)
                    temp_cands = []
                    
                    for w_data in winner_urls:
                        w_text = scrape_raw_text(w_data['link'])
                        if w_text:
                            time.sleep(4) # 🚨 API 에러 방지용 휴식
                            cands = extract_candidate_info(w_text)
                            temp_cands.extend(cands)
                    
                    if temp_cands:
                        st.success(f"총 {len(temp_cands)}명의 명단 발견!")
                        st.dataframe(pd.DataFrame(temp_cands))
                        all_candidates.extend(temp_cands)
                    else:
                        st.warning("관련 뉴스 및 발표문에서 후보자를 찾지 못했습니다.")
            
            if st.session_state.is_running:
                pb_cand.progress(1.0, text="100% 탐색 완료!")
                st.session_state.is_running = False
                st.session_state.step4_done = True
                st.session_state.all_candidates = all_candidates

        if st.session_state.step4_done:
            st.divider()
            st.subheader("최종 수집된 후보자 통합 명단")
            if 'all_candidates' in st.session_state and st.session_state.all_candidates:
                st.dataframe(pd.DataFrame(st.session_state.all_candidates), use_container_width=True)
                
                # 노션 이송 버튼 (시뮬레이션)
                if st.button("💾 이 명단을 노션(Notion) DB로 일괄 전송", type="primary", use_container_width=True):
                    with st.spinner("노션 API로 데이터를 전송하고 있습니다..."):
                        time.sleep(2)
                        st.success("✅ 전송 성공! (이곳에 notion_sync.py 로직이 연결될 예정입니다.)")
            else:
                st.info("수집된 명단이 없습니다.")

# --- STEP 5 ---
elif menu == "Step 5. 시스템 디버깅":
    st.header("시스템 디버깅 및 실시간 로그")
    if st.button("로그 새로고침"): st.rerun()
    try:
        with open('system.log', 'r') as f:
            st.text_area("Log Output", f.read()[-3000:], height=400)
    except FileNotFoundError:
        st.info("system.log 파일이 아직 생성되지 않았습니다.")