import streamlit as st

# 1. 웹페이지 기본 설정 (제목, 레이아웃 넓게 쓰기)
st.set_page_config(page_title="후보자 검증 AI 시스템", page_icon="🏆", layout="wide")

# 2. 좌측 사이드바 메뉴 만들기
st.sidebar.title("🛠️ 시스템 컨트롤 패널")
menu = st.sidebar.radio(
    "메뉴를 선택하세요:",
    ("1. 시상 주제 업로드", "2. 타겟 기관 탐색", "3. 후보자 스크랩 및 전송", "4. 시스템 디버깅")
)

# 3. 각 메뉴별 화면 구성 (뼈대)
if menu == "1. 시상 주제 업로드":
    st.header("📄 올해의 시상 테마 업로드")
    st.write("심사 기준이 담긴 PDF 문서를 업로드해 주세요.")
    uploaded_file = st.file_uploader("PDF 파일 선택", type="pdf")
    if uploaded_file is not None:
        st.success("파일이 성공적으로 업로드되었습니다!")

elif menu == "2. 타겟 기관 탐색":
    st.header("🔍 1차: AI 타겟 기관 탐색")
    st.write("AI가 테마를 분석하여 크롤링할 대상 웹사이트를 찾습니다.")
    if st.button("기관 탐색 시작 (약 1분 소요)"):
        st.info("여기에 모듈 1(targeting_agent.py)이 실행되는 로직이 들어갈 예정입니다.")

elif menu == "3. 후보자 스크랩 및 전송":
    st.header("🗄️ 2차: 후보자 수집 및 노션 전송")
    st.write("수집된 기관에서 인물 데이터를 긁어오고 AI 평가를 진행한 뒤 노션으로 보냅니다.")
    if st.button("수집 및 AI 평가 시작 (약 20분 소요)"):
        st.warning("여기에 모듈 2와 3이 실행되고, DB에 저장되는 로직이 들어갈 예정입니다.")
        
elif menu == "4. 시스템 디버깅":
    st.header("🐛 시스템 디버깅 및 로그")
    st.write("백그라운드에서 실행 중인 시스템의 상태와 에러 로그를 확인합니다.")
    st.code("System is running normally...\nNo errors found yet.")