# AI-Driven Award Nominee Discovery & Verification System (Hybrid Architecture)

## Abstract

This project implements an automated, AI-driven data pipeline to discover, scrape, and evaluate global award nominees based on specific thematic criteria. By decoupling the administrative control panel (Streamlit) from the staff collaboration workspace (Notion), the system prevents API rate-limiting and provides a seamless user experience. The architecture leverages a local edge server (Raspberry Pi 5 via Docker) as an orchestration node, outsourcing heavy LLM processing to Google Gemini 2.5 Flash and search operations to Serper API. This ensures a lightweight, zero-operation-cost system while achieving high-fidelity, bias-free candidate verification through a rigorous 3-Phase Human-AI Cross-Validation workflow.

---

## 1. 개요 (Overview)

본 프로젝트는 수개월이 소요되던 기존의 수작업 기반 수상 후보자 발굴 및 검증 프로세스를 자동화하는 **AI 기반 인물 데이터 수집 및 교차 검증 시스템**입니다.
단순한 웹 크롤링을 넘어, 업로드된 시상 테마(PDF)를 AI가 분석하여 타겟 기관을 스스로 탐색하고, 수집된 비정형 텍스트 데이터를 정형화된 JSON 형태로 정제합니다. 특히, 심사 과정에서 발생할 수 있는 인간의 선입견을 배제하기 위해 **AI의 정량 평가와 실무자의 정성 평가를 블라인드 테스트 방식으로 분리**하여 시스템의 공신력과 업무 효율성을 극대화했습니다.

## 2. 시스템 아키텍처 (System Architecture)

시스템은 부하 분산과 사용자 접근성을 고려하여 역할에 따라 4개의 계층(Layer)으로 분리되어 동작합니다.

| 계층 (Layer) | 구성 요소 (Components) | 주요 역할 (Roles) |
| --- | --- | --- |
| **Control & Admin Layer** | Streamlit (Python) | 관리자용 웹 대시보드 호스팅. 시상 테마(PDF) 업로드, 크롤링 파이프라인 트리거 및 실시간 시스템 디버깅/로그 모니터링 |
| **AI & Search Layer** | Gemini 2.5 Flash, Serper API | PDF 문맥 분석 및 검색 쿼리 도출, 구글 검색 우회 라우팅(URL 수집), 비정형 HTML 텍스트 데이터의 영문 JSON 정제 |
| **Data & Automation Layer** | PostgreSQL, n8n (Docker on RPi 5) | 정규화된 11개 테이블 기반의 원본/평가 데이터 영구 저장. 스케줄링 및 Notion API 연동을 위한 백그라운드 자동화 워크플로우 실행 |
| **Collaboration Layer** | Notion API, Notion Workspace | 실무자용 1차 블라인드 심사 뷰(View) 제공 및 최종 인간-AI 교차 검증 결과(Fast Track 등) 동기화 |

## 3. 기술 스택 (Technology Stack)

* **Infrastructure:** Raspberry Pi 5 (Linux), Docker
* **Frontend (Admin UI):** Streamlit (Python)
* **Backend & Web Scraping:** Python (BeautifulSoup, PyPDF2, requests)
* **AI & External APIs:** Google Gemini 2.5 Flash API, Serper API, Notion API
* **Database & Workflow Engine:** PostgreSQL, n8n
* **Networking & CI/CD:** Tailscale (Remote VS Code SSH & Virtual IP Routing)

## 4. 핵심 기술 명세 및 엔지니어링 전략 (Technical Highlights)

### 4.1 3단계 교차 검증 파이프라인 (3-Phase Cross-Validation)

인간과 기계의 상호 보완을 위해 심사 프로세스를 분리 설계했습니다.

* **Phase 1 (블라인드 배포):** AI가 수집/평가한 데이터 중 점수와 추천 여부를 내부 DB(PostgreSQL)에 은닉하고, 객관적 팩트(요약, 국가 등)만 Notion으로 전송합니다.
* **Phase 2 (인간의 영역):** 실무자가 Notion 워크스페이스에서 순수 정성적 판단으로 Top 100을 선정합니다.
* **Phase 3 (결과 동기화):** n8n 워크플로우를 트리거하여 숨겨둔 AI 점수를 Notion에 업데이트하고, 🟢일치(Fast Track), 🟡실무자 단독, 🟠AI 단독 추천 그룹으로 자동 분류합니다.

### 4.2 하이브리드 인터페이스 분리 (DB Buffering)

대량의 크롤링 데이터를 Notion으로 즉시 전송할 경우 발생하는 API Rate Limit (429 Error) 및 실무자 피로도 문제를 해결했습니다.

* 크롤링된 Raw Data는 일차적으로 로컬 PostgreSQL에 버퍼링(Buffering)되며, Streamlit 관리자 패널의 제어를 통해 검증된 데이터만 Notion으로 일괄(Batch) 푸시하는 하이브리드 전송 아키텍처를 채택했습니다.

### 4.3 엣지 노드 최적화 및 제로 코스트(Zero-Cost) 운영

* 무거운 연산(LLM 추론)과 네트워크 부하(검색)는 외부 API(Gemini, Serper)로 위임하고, 로컬 하드웨어(Raspberry Pi 5)는 API 응답 대기 및 데이터 라우팅을 담당하는 가벼운 '통신 노드'로 활용하여 메모리 초과(OOM)를 방지했습니다.
* 유료 SaaS 자동화 툴(Make, Zapier) 대신 온프레미스 n8n을 구축하여 운영 유지보수 비용을 0원으로 수렴시켰습니다.

### 4.4 봇 방어 우회 및 데이터 정제 (Anti-Bot & Parsing)

* 타겟 기관 웹사이트의 스크래핑 차단을 우회하기 위해 파이썬 크롤러에 User-Agent 위장 헤더를 적용했습니다. `BeautifulSoup`을 활용해 DOM 트리에서 불필요한 JS/CSS 노드를 제거하고 순수 텍스트만 추출하여 LLM의 컨텍스트 윈도우(Context Window) 낭비를 최소화했습니다.

## 5. 한계점 및 향후 개선 과제 (Limitations & Future Work)

* **동적 웹페이지(SPA) 크롤링 한계:** 현재의 정적 스크래핑(Requests+BS4) 방식은 React/Vue 등으로 렌더링되는 최신 SPA 웹사이트의 텍스트를 읽어오는 데 한계가 있습니다. 향후 `Selenium`의 Headless 모드를 도입하되, 라즈베리파이의 RAM 부하를 고려하여 n8n에서 배치(Batch) 단위로 크롤링 속도를 조절하는 로직을 추가할 예정입니다.
* **Notion API 병목 현상:** 100명 이상의 후보자 속성을 동시에 업데이트할 때 전송 지연이 발생할 수 있습니다. n8n 워크플로우 내에 Split In Batches 노드와 Delay 노드를 추가하여 트래픽 셰이핑(Traffic Shaping)을 적용할 계획입니다.
* **SaaS 확장 (V2 Multi-tenant):** 단일 노션 워크스페이스 연동을 넘어, Streamlit 웹 UI에서 실무자가 자신의 Notion Integration Token과 DB ID를 직접 입력하면, 시스템이 해당 실무자의 개인 노션으로 데이터를 클로닝(Cloning)해주는 멀티 테넌트(Multi-tenant) 기능 확장을 기획하고 있습니다.
