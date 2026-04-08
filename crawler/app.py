import streamlit as st
import pandas as pd
import time
import logging
import urllib3
import json
from google import genai
from dotenv import load_dotenv

# 1. 환경변수 로드 및 시스템 세팅
load_dotenv()
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logging.basicConfig(filename='system.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 2. 백엔드 엔진 모듈 임포트
from targeting_agent import extract_text_from_pdf, get_search_keywords_from_ai, search_target_urls, search_award_background, search_award_winners
from raw_scraper import scrape_raw_text
from ai_refiner import extract_initial_award_name, verify_and_extract_org_info, extract_candidate_info
from notion_sync import send_data_to_n8n

st.set_page_config(page_title="후보자 검증 AI 시스템", layout="wide")

AI_VENDOR = "Google"
AI_MODEL = "gemini-2.5-flash"
PRICING_INPUT_PER_1M_USD = 0.30
PRICING_OUTPUT_PER_1M_USD = 2.50
EST_CHARS_PER_TOKEN = 4
MODEL_TOKEN_LIMIT = 1_000_000
MODEL_TOKEN_REFILL = "요청 단위로 리셋 (컨텍스트 윈도우 기준)"

# ==========================================
# 3. Session State (전역 메모리) 초기화
# ==========================================
# 💡 수정됨: 공식 홈페이지 타겟팅을 위한 서브 키워드(website, homepage 등) 대거 추가
SUB1_KEYWORDS = [
    "award", "prize", "fellowship", "foundation", "program", "initiative", "organization", 
    "annual award", "international award", "global award", 
    "website", "homepage", "official website", "official homepage"
]
SUB2_KEYWORDS = ["global", "africa", "asia", "europe", "korea", "kenya", "south africa", "ngo", "nonprofit", "youth", "women", "environment", "climate"]

if 'theme_text' not in st.session_state: st.session_state.theme_text = ""
if 'user_gemini_api_key' not in st.session_state: st.session_state.user_gemini_api_key = ""
if 'user_gemini_api_key_input' not in st.session_state: st.session_state.user_gemini_api_key_input = ""
if 'use_user_gemini_api_key' not in st.session_state: st.session_state.use_user_gemini_api_key = False
if 'user_key_validated' not in st.session_state: st.session_state.user_key_validated = False
if 'last_validated_key' not in st.session_state: st.session_state.last_validated_key = ""
if 'current_step' not in st.session_state: st.session_state.current_step = "Step 1. 시상 주제 분석"

if 'df_main_kw' not in st.session_state: st.session_state.df_main_kw = pd.DataFrame(columns=["선택", "주제 키워드"])
if 'df_sub1_kw' not in st.session_state: st.session_state.df_sub1_kw = pd.DataFrame({"선택": [True]*len(SUB1_KEYWORDS), "서브 키워드 1": SUB1_KEYWORDS})
if 'df_sub2_kw' not in st.session_state: st.session_state.df_sub2_kw = pd.DataFrame({"선택": [False]*len(SUB2_KEYWORDS), "서브 키워드 2": SUB2_KEYWORDS})
if 'df_combined' not in st.session_state: st.session_state.df_combined = pd.DataFrame(columns=["선택", "검색어"])
if 'df_urls' not in st.session_state: st.session_state.df_urls = pd.DataFrame(columns=["선택", "시상명", "URL"])
if 'df_verified_orgs' not in st.session_state: st.session_state.df_verified_orgs = pd.DataFrame()
if 'all_candidates' not in st.session_state: st.session_state.all_candidates = []
if 'candidate_batches' not in st.session_state: st.session_state.candidate_batches = []
if 'usage_stats' not in st.session_state:
    st.session_state.usage_stats = {
        "api_calls": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "estimated_cost_usd": 0.0
    }

if 'step1_done' not in st.session_state: st.session_state.step1_done = False
if 'step2_done' not in st.session_state: st.session_state.step2_done = False
if 'step3_extracted' not in st.session_state: st.session_state.step3_extracted = False
if 'step3_verified' not in st.session_state: st.session_state.step3_verified = False
if 'step4_done' not in st.session_state: st.session_state.step4_done = False
if 'is_running' not in st.session_state: st.session_state.is_running = False

def go_to_step(step_name):
    st.session_state.current_step = step_name

def get_active_gemini_api_key():
    if not st.session_state.use_user_gemini_api_key:
        return None
    api_key = st.session_state.user_gemini_api_key.strip()
    return api_key if api_key else None

def validate_gemini_api_key(api_key):
    key = (api_key or "").strip()
    if not key:
        return False, "API 키가 비어 있습니다."
    try:
        temp_client = genai.Client(api_key=key)
        temp_client.models.generate_content(
            model=AI_MODEL,
            contents="health check"
        )
        return True, "정상 등록되었습니다."
    except Exception as e:
        err = str(e)
        lower = err.lower()
        if "api key not valid" in lower or "invalid" in lower:
            return False, "API 키가 유효하지 않습니다."
        if "permission" in lower:
            return False, "해당 키에 모델 호출 권한이 없습니다."
        if "quota" in lower or "rate limit" in lower:
            return False, "쿼터 또는 호출 한도에 도달했습니다."
        if "model" in lower and "not found" in lower:
            return False, f"모델({AI_MODEL}) 접근이 불가능합니다."
        return False, f"검증 실패: {err[:160]}"

def _as_text_length(value):
    if value is None:
        return 0
    if isinstance(value, str):
        return len(value)
    try:
        return len(json.dumps(value, ensure_ascii=False))
    except Exception:
        return len(str(value))

def _estimate_tokens(char_len):
    if char_len <= 0:
        return 0
    return max(1, int(round(char_len / EST_CHARS_PER_TOKEN)))

def track_usage(input_payload=None, output_payload=None):
    in_chars = _as_text_length(input_payload)
    out_chars = _as_text_length(output_payload)
    in_tokens = _estimate_tokens(in_chars)
    out_tokens = _estimate_tokens(out_chars)
    in_cost = (in_tokens / 1_000_000) * PRICING_INPUT_PER_1M_USD
    out_cost = (out_tokens / 1_000_000) * PRICING_OUTPUT_PER_1M_USD

    st.session_state.usage_stats["api_calls"] += 1
    st.session_state.usage_stats["input_tokens"] += in_tokens
    st.session_state.usage_stats["output_tokens"] += out_tokens
    st.session_state.usage_stats["estimated_cost_usd"] += (in_cost + out_cost)

# ==========================================
# 4. 사이드바 (내비게이션)
# ==========================================
st.sidebar.title("시스템 컨트롤 패널")
menu = st.sidebar.radio(
    "진행 단계를 선택하세요:",
    ("Step 0. API 설정", "Step 1. 시상 주제 분석", "Step 2. 검색어 최종 조합", "Step 3. URL 수집 및 교차 검증", "Step 4. 수상자 발굴 및 전송", "Step 5. 시스템 디버깅"),
    key="current_step"
)

# ==========================================
# 5. 메인 화면 로직 (라우팅)
# ==========================================

# --- STEP 0 ---
if menu == "Step 0. API 설정":
    st.header("Step 0. 개인 Gemini API 키 설정")
    st.info("기본값은 서버(.env) 토큰입니다. 사용자가 키를 입력하면 이후부터 현재 세션에서는 사용자 키가 우선 적용됩니다.")

    key_col, toggle_col = st.columns([5, 1.6])
    with key_col:
        st.text_input(
            "Gemini API Key",
            type="password",
            key="user_gemini_api_key_input",
            placeholder="AIza... 형태의 Gemini API 키를 입력하세요."
        )
    with toggle_col:
        st.toggle("입력 키 사용", key="use_user_gemini_api_key")

    if st.session_state.use_user_gemini_api_key:
        candidate_key = st.session_state.user_gemini_api_key_input.strip() or st.session_state.user_gemini_api_key.strip()
        if not candidate_key:
            st.session_state.use_user_gemini_api_key = False
            st.session_state.user_key_validated = False
            st.toast("API 키를 먼저 입력해 주세요.", icon="⚠️")
            st.warning("현재 모드: 서버 기본 Gemini 키 사용")
        elif (not st.session_state.user_key_validated) or (candidate_key != st.session_state.last_validated_key):
            with st.spinner("API 키 검증 중..."):
                is_valid, message = validate_gemini_api_key(candidate_key)
            if is_valid:
                st.session_state.user_gemini_api_key = candidate_key
                st.session_state.last_validated_key = candidate_key
                st.session_state.user_key_validated = True
                st.toast("Gemini API 키가 정상 등록되었습니다.", icon="✅")
                masked_key = candidate_key
                st.success(f"현재 모드: 사용자 입력 키 사용 중 ({masked_key[:6]}...{masked_key[-4:]})")
            else:
                st.session_state.use_user_gemini_api_key = False
                st.session_state.user_key_validated = False
                st.toast("Gemini API 키 등록에 실패했습니다.", icon="❌")
                st.error(f"등록 실패 사유: {message}")
                st.warning("현재 모드: 서버 기본 Gemini 키 사용")
        else:
            masked_key = st.session_state.user_gemini_api_key
            st.success(f"현재 모드: 사용자 입력 키 사용 중 ({masked_key[:6]}...{masked_key[-4:]})")
    else:
        st.warning("현재 모드: 서버 기본 Gemini 키 사용")

    btn1, btn2 = st.columns(2)
    with btn1:
        if st.button("기본 API로 돌아가기", use_container_width=True):
            st.session_state.use_user_gemini_api_key = False
            st.toast("서버 기본 API 키 모드로 전환했습니다.", icon="ℹ️")
            st.rerun()
    with btn2:
        if st.button("입력 키 완전 삭제", use_container_width=True):
            st.session_state.user_gemini_api_key = ""
            st.session_state.user_gemini_api_key_input = ""
            st.session_state.user_key_validated = False
            st.session_state.last_validated_key = ""
            st.session_state.use_user_gemini_api_key = False
            st.toast("저장된 사용자 API 키를 삭제했습니다.", icon="🧹")
            st.rerun()

    st.divider()
    st.subheader("현재 사용 모델 상태")
    used_tokens = st.session_state.usage_stats["input_tokens"] + st.session_state.usage_stats["output_tokens"]
    remaining_tokens = max(0, int(MODEL_TOKEN_LIMIT - used_tokens))
    used_cost = st.session_state.usage_stats["estimated_cost_usd"]
    current_cost_label = "무료" if used_cost <= 0 else f"${used_cost:.6f} (추정)"

    status_df = pd.DataFrame([{
        "현재 사용 모델": AI_MODEL,
        "토큰 한도": f"{MODEL_TOKEN_LIMIT:,} tokens",
        "토큰 주기": MODEL_TOKEN_REFILL,
        "현재까지 비용": current_cost_label
    }])
    st.dataframe(status_df, use_container_width=True, hide_index=True)

    s1, s2, s3 = st.columns(3)
    s1.metric("세션 호출 수", f'{st.session_state.usage_stats["api_calls"]}회')
    s2.metric("누적 사용 토큰(추정)", f"{used_tokens:,}")
    s3.metric("남은 토큰(추정)", f"{remaining_tokens:,}")

    p1 = min(1.0, used_tokens / max(1, MODEL_TOKEN_LIMIT))
    st.progress(p1, text=f"모델 컨텍스트 한도 대비 사용률(추정): {p1*100:.2f}%")

    st.divider()
    st.subheader("모델 요금 안내")
    pricing_df = pd.DataFrame([
        {"브랜드": "OpenAI", "모델": "GPT-5.4", "무료 여부": "유료", "입력 비용": "$2.50 / 1M (=$0.0000025/토큰)", "출력 비용": "$15.00 / 1M (=$0.000015/토큰)"},
        {"브랜드": "OpenAI", "모델": "GPT-5.4 mini", "무료 여부": "유료", "입력 비용": "$0.75 / 1M", "출력 비용": "$4.50 / 1M"},
        {"브랜드": "OpenAI", "모델": "GPT-5.4 nano", "무료 여부": "유료", "입력 비용": "$0.20 / 1M", "출력 비용": "$1.25 / 1M"},
        {"브랜드": "Google Gemini Developer API", "모델": "Gemini 3 Flash Preview", "무료 여부": "무료 등급 있음", "입력 비용": "무료 / 유료 $0.50 / 1M", "출력 비용": "무료 / 유료 $3.00 / 1M"},
        {"브랜드": "Google Gemini Developer API", "모델": "Gemini 3.1 Flash-Lite Preview", "무료 여부": "무료 등급 있음", "입력 비용": "무료 / 유료 $0.25 / 1M", "출력 비용": "무료 / 유료 $1.50 / 1M"},
        {"브랜드": "Google Gemini Developer API", "모델": "Gemini 3.1 Flash Live Preview", "무료 여부": "무료 등급 있음", "입력 비용": "무료 / 유료 텍스트 $0.75 / 1M", "출력 비용": "무료 / 유료 텍스트 $4.50 / 1M"},
        {"브랜드": "Anthropic", "모델": "Claude Opus 4.6", "무료 여부": "유료", "입력 비용": "$5 / 1M", "출력 비용": "$25 / 1M"},
        {"브랜드": "Anthropic", "모델": "Claude Sonnet 4.6", "무료 여부": "유료", "입력 비용": "$3 / 1M", "출력 비용": "$15 / 1M"},
        {"브랜드": "Anthropic", "모델": "Claude Haiku 4.5", "무료 여부": "유료", "입력 비용": "$1 / 1M", "출력 비용": "$5 / 1M"},
        {"브랜드": "Mistral", "모델": "Mistral Large 3", "무료 여부": "유료", "입력 비용": "$0.50 / 1M", "출력 비용": "$1.50 / 1M"},
        {"브랜드": "Mistral", "모델": "Mistral Medium 3 / 3.1", "무료 여부": "유료", "입력 비용": "$0.40 / 1M", "출력 비용": "$2.00 / 1M"},
        {"브랜드": "Mistral", "모델": "Mistral Small 4", "무료 여부": "유료", "입력 비용": "$0.15 / 1M", "출력 비용": "$0.60 / 1M"},
        {"브랜드": "Cohere", "모델": "Command A", "무료 여부": "유료", "입력 비용": "$2.50 / 1M", "출력 비용": "$10 / 1M"},
        {"브랜드": "Cohere", "모델": "Trial API key", "무료 여부": "무료(평가용)", "입력 비용": "무료", "출력 비용": "무료"},
        {"브랜드": "DeepSeek", "모델": "deepseek-chat", "무료 여부": "유료", "입력 비용": "캐시히트/미스가 다름", "출력 비용": "출력 별도"},
        {"브랜드": "DeepSeek", "모델": "deepseek-reasoner", "무료 여부": "유료", "입력 비용": "캐시히트/미스가 다름", "출력 비용": "출력 별도"},
    ])
    st.dataframe(pricing_df, use_container_width=True, hide_index=True)

    st.button("✨ 다음 단계로 이동", type="primary", key="next0", on_click=go_to_step, args=("Step 1. 시상 주제 분석",))

# --- STEP 1 ---
elif menu == "Step 1. 시상 주제 분석":
    st.header("Step 1. 시상 주제 분석 및 키워드 셋업")
    
    uploaded_file = st.file_uploader("심사 기준 PDF 문서를 업로드해 주세요.", type="pdf")
    if uploaded_file is not None:
        with st.spinner("PDF 텍스트 추출 중..."):
            with open("temp_theme.pdf", "wb") as f: f.write(uploaded_file.getbuffer())
            st.session_state.theme_text = extract_text_from_pdf("temp_theme.pdf")
            st.success("PDF 업로드 성공!")

    st.divider()
    
    # 🚨 여기에 [🛠️ 테스트 키워드 주입] 버튼이 위치해야 합니다!
    col1, col2, col3 = st.columns([2, 2, 1]) 
    
    with col1:
        if st.button("🚀 AI 주제 키워드 추출", disabled=st.session_state.step1_done, use_container_width=True):
            if not st.session_state.theme_text:
                st.warning("PDF를 먼저 업로드 해주세요!")
            else:
                with st.spinner("AI 분석 중..."):
                    st.session_state.step1_done = True
                    main_kw_list = get_search_keywords_from_ai(
                        st.session_state.theme_text,
                        gemini_api_key=get_active_gemini_api_key()
                    )
                    track_usage(
                        input_payload=st.session_state.theme_text[:5000],
                        output_payload=main_kw_list
                    )
                    
                    if not main_kw_list:
                        st.error("⚠️ 구글 API 할당량 초과! 테스트용 임시 키워드를 삽입합니다.")
                        main_kw_list = ["climate change", "grassroots innovation", "environmental activism"]
                        
                    st.session_state.df_main_kw = pd.DataFrame({"선택": [True]*len(main_kw_list), "주제 키워드": main_kw_list})
                    st.rerun()
                    
    with col2:
        # 💡 가주님을 위한 토큰 절약용 테스트 버튼
        if st.button("🛠️ 테스트 키워드 주입 (토큰 절약)", disabled=st.session_state.step1_done, use_container_width=True):
            st.session_state.step1_done = True
            test_kw = ["Intergenerational Justice"]
            st.session_state.df_main_kw = pd.DataFrame({"선택": [True]*len(test_kw), "주제 키워드": test_kw})
            st.success("✅ 테스트 키워드가 주입되었습니다! (토큰 소모 없음)")
            st.rerun()

    with col3:
        if st.session_state.step1_done:
            if st.button("초기화", use_container_width=True):
                st.session_state.step1_done = False
                st.rerun()

    if st.session_state.step1_done:
        c1, c2, c3 = st.columns(3)
        with c1: st.session_state.df_main_kw = st.data_editor(st.session_state.df_main_kw, hide_index=True, key="de_main")
        with c2: st.session_state.df_sub1_kw = st.data_editor(st.session_state.df_sub1_kw, hide_index=True, key="de_sub1")
        with c3: st.session_state.df_sub2_kw = st.data_editor(st.session_state.df_sub2_kw, hide_index=True, key="de_sub2")
        
        st.button("✨ 다음 단계로 이동", type="primary", key="next1", on_click=go_to_step, args=("Step 2. 검색어 최종 조합",))

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
            st.button("✨ 다음 단계로 이동", type="primary", key="next2", on_click=go_to_step, args=("Step 3. URL 수집 및 교차 검증",))

# --- STEP 3 ---
elif menu == "Step 3. URL 수집 및 교차 검증":
    st.header("Step 3. URL 수집 및 교차 검증")
    if not st.session_state.step2_done: st.warning("Step 2를 먼저 완료해 주세요.")
    else:
        # Phase 3A: 1차 발췌
        if st.button("1️⃣ 원문 스크랩 및 1차 발췌", disabled=st.session_state.step3_extracted):
            active_queries = st.session_state.df_combined[st.session_state.df_combined["선택"]]["검색어"].tolist()
            test_queries = active_queries[:3] # 테스트용 제한
            if not test_queries:
                st.warning("선택된 검색어가 없습니다. Step 2에서 최소 1개를 선택해 주세요.")
                st.stop()

            st.session_state.step3_extracted = True
            progress_bar = st.progress(0, text="검색 준비 중...")
            results_list = []
            
            for i, query in enumerate(test_queries):
                progress_bar.progress((i / len(test_queries)), text=f"검색 중: {query}")
                urls_data = search_target_urls(query) 
                
                for u_data in urls_data:
                    url = u_data['link']
                    raw_text = scrape_raw_text(url) 
                    if raw_text:
                        time.sleep(4) 
                        award_name = extract_initial_award_name(
                            raw_text,
                            gemini_api_key=get_active_gemini_api_key()
                        )
                        track_usage(
                            input_payload=raw_text[:8000],
                            output_payload=award_name
                        )
                        if award_name and "관련 없음" not in award_name:
                            results_list.append({"시상명": award_name, "URL": url})
            
            if results_list:
                df = pd.DataFrame(results_list)
                df_grouped = df.groupby('시상명', as_index=False).agg({'URL': lambda x: '\n'.join(x)})
                df_grouped.insert(0, '선택', True)
                st.session_state.df_urls = df_grouped
            progress_bar.progress(1.0, text="1차 발췌 완료")
            st.rerun()

        if st.session_state.step3_extracted:
            st.session_state.df_urls = st.data_editor(st.session_state.df_urls, use_container_width=True)
            st.divider()
            
            # Phase 3B: 딥서치 교차 검증
            if st.button("2️⃣ 심층 교차 검증 시작", disabled=st.session_state.step3_verified, type="primary"):
                targets = st.session_state.df_urls[st.session_state.df_urls["선택"]]["시상명"].tolist()
                if not targets:
                    st.warning("교차 검증 대상이 없습니다. Step 3의 1차 발췌 결과를 확인해 주세요.")
                    st.stop()

                st.session_state.step3_verified = True
                pb_verify = st.progress(0, text="교차 검증 준비 중...")
                verified_data = []
                
                for i, award in enumerate(targets):
                    pb_verify.progress((i / len(targets)), text=f"딥서치 중: {award}")
                    bg_context = search_award_background(award)
                    sample_url = st.session_state.df_urls[st.session_state.df_urls["시상명"] == award]["URL"].values[0].split('\n')[0]
                    orig_text = scrape_raw_text(sample_url)
                    
                    time.sleep(4)
                    org_info = verify_and_extract_org_info(
                        orig_text,
                        bg_context,
                        sample_url,
                        gemini_api_key=get_active_gemini_api_key()
                    )
                    track_usage(
                        input_payload=f"{orig_text[:5000]}\n{bg_context[:5000]}",
                        output_payload=org_info
                    )
                    org_info['선택'] = True
                    verified_data.append(org_info)
                
                st.session_state.df_verified_orgs = pd.DataFrame(verified_data)
                pb_verify.progress(1.0, text="교차 검증 완료")
                st.rerun()

            if st.session_state.step3_verified:
                st.session_state.df_verified_orgs = st.data_editor(st.session_state.df_verified_orgs, use_container_width=True)
                st.button("✨ 다음 단계로 이동", type="primary", key="next3", on_click=go_to_step, args=("Step 4. 수상자 발굴 및 전송",))

# --- STEP 4 ---
elif menu == "Step 4. 수상자 발굴 및 전송":
    st.header("Step 4. 수상자 발굴 및 n8n/Notion 전송")
    if not st.session_state.step3_verified: st.warning("Step 3를 완료해 주세요.")
    else:
        final_targets = st.session_state.df_verified_orgs[st.session_state.df_verified_orgs["선택"]]
        if final_targets.empty:
            st.warning("선택된 검증 대상이 없습니다. Step 3에서 최소 1개를 선택해 주세요.")
            st.stop()
        
        # 🚨 원래 Step 4의 올바른 로직 복구
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
            candidate_batches = []
            for idx, row in final_targets.iterrows():
                if not st.session_state.is_running: break
                award_name = row.get('시상/프로그램명', '')
                org_name = row.get('주최/주관 기관명', 'N/A')
                theme = row.get('시상 주제(Theme)', 'N/A')
                with st.expander(f"🔍 [탐색 결과] {award_name}", expanded=True):
                    winner_urls = search_award_winners(award_name)
                    temp_cands = []
                    for w_data in winner_urls:
                        w_text = scrape_raw_text(w_data['link'])
                        if w_text:
                            time.sleep(4)
                            cands = extract_candidate_info(
                                w_text,
                                gemini_api_key=get_active_gemini_api_key()
                            )
                            track_usage(
                                input_payload=w_text[:8000],
                                output_payload=cands
                            )
                            temp_cands.extend(cands)
                    
                    if temp_cands:
                        st.dataframe(pd.DataFrame(temp_cands))
                        all_candidates.extend(temp_cands)
                        candidate_batches.append({
                            "award_name": award_name,
                            "org_name": org_name,
                            "theme": theme,
                            "candidates": temp_cands
                        })
            
            if st.session_state.is_running:
                st.session_state.is_running = False
                st.session_state.step4_done = True
                st.session_state.all_candidates = all_candidates
                st.session_state.candidate_batches = candidate_batches

        if st.session_state.step4_done:
            st.dataframe(pd.DataFrame(st.session_state.all_candidates), use_container_width=True)
            if st.button("💾 n8n Webhook으로 노션(Notion) 전송", type="primary"):
                if not st.session_state.candidate_batches:
                    st.warning("전송할 후보자 데이터가 없습니다.")
                    st.stop()

                success_count = 0
                fail_count = 0
                for batch in st.session_state.candidate_batches:
                    is_sent = send_data_to_n8n(
                        candidates_list=batch["candidates"],
                        award_name=batch["award_name"],
                        org_name=batch["org_name"],
                        theme=batch["theme"]
                    )
                    if is_sent:
                        success_count += 1
                    else:
                        fail_count += 1

                if fail_count == 0:
                    st.success(f"✅ n8n 전송 성공! 총 {success_count}건 완료")
                else:
                    st.error(f"🚫 일부 전송 실패: 성공 {success_count}건 / 실패 {fail_count}건")

# --- STEP 5 ---
elif menu == "Step 5. 시스템 디버깅":
    st.header("시스템 로그")
    if st.button("로그 새로고침"): st.rerun()
    try:
        with open('system.log', 'r') as f: st.text_area("Log", f.read()[-3000:], height=400)
    except Exception: st.info("로그 파일 없음.")
