# 반도체 트레이딩 AI 시스템

> AI 기반 반도체 주식 시장 분석 및 트레이딩 전략 추천 시스템

---

## 프로젝트 개요

전 세계 주요 반도체 종목(NVDA, AMD, INTC, ASML, TSM, SK하이닉스)의 주가 데이터를 자동 수집하고,
AI가 **기술 지표 + 펀더멘털 + 뉴스**를 종합 분석해 트레이더에게 **매수/매도 신호, 리스크 수준, 트레이딩 전략**을 제공하는 에이전트 기반 시스템입니다.

단순한 데이터 시각화 도구가 아닌, **AI가 스스로 판단하고 추천하는 Multi-Agent 구조**로 설계되었습니다.

---

## 시스템 아키텍처

```
[yfinance — 반도체 주가(5년) + 펀더멘털 + 뉴스 자동 수집]
            ↓
[기술 지표 계산 — MA, RSI, 볼린저 밴드, 거래량]
[펀더멘털 분석 — PER, PBR, ROE, 성장률, 부채비율 등]
            ↓
[Vector DB (ChromaDB RAG) — 시장 분석 + 뉴스 의미 기반 저장]
            ↓
[Multi-Agent — 신호 판단 / 리스크 감지 / 전략 추천]
            ↓
[FastAPI 백엔드 REST API]
            ↓
[Streamlit 대시보드 — 차트 / 펀더멘털 / 뉴스 / AI 분석 / 챗봇]
```

---

## 버전 히스토리

### v260518.1 (2026-05-18)

**분석 고도화 버전 — 주가 예측 / 백테스팅 / 섹터 비교 / 뉴스 감성 분석 추가**

#### 추가된 기능

**1. 몬테카를로 주가 예측 (`src/processor.py`, `src/api.py`)**
- `price_forecast()`: 5년치 일별 로그 수익률 기반 10,000회 시뮬레이션
- 상승(상위 30%) / 중립(중간 40%) / 하락(하위 30%) 3가지 시나리오별 예상 가격 + 확률 반환
- 시뮬레이션 결과 분포 히스토그램 + 현재가 기준선 차트
- AI 분석 탭 내 항상 표시 (AI 분석 실행 없이도 확인 가능)
- 새 엔드포인트: `GET /forecast/{symbol}`

**2. 백테스팅 (`src/backtest.py` 신규, `src/api.py`)**
- MA5/MA20 골든크로스 전략을 5년치 과거 데이터에 시뮬레이션
- Look-ahead bias 방지 (신호 발생 다음날 체결 적용)
- 반환 지표: 전략 수익률 / 매수보유 수익률 / 승률 / 총 거래 횟수 / 최대 낙폭
- 전략 vs 매수보유 누적 수익률 비교 차트
- 새 엔드포인트: `GET /backtest/{symbol}`

**3. 섹터 비교 분석 탭 (`dashboard/app.py`, `src/api.py`)**
- 기간별 수익률 히트맵 (1주 / 1개월 / 3개월 / 1년), 빨강-초록 색상 스케일
- 전체 종목 간 일별 수익률 상관관계 매트릭스
- 새 탭: 🔍 비교 분석 (총 6탭으로 확장)
- 새 엔드포인트: `GET /compare`

**4. 뉴스 감성 분석 (`src/collector.py`, `dashboard/app.py`)**
- 긍정/부정 키워드 기반 점수 산출 (외부 API 없이 로컬 처리)
- `get_news()` 반환값에 `sentiment: {score, label}` 필드 추가
- 뉴스 탭 각 기사에 🟢 긍정 / ⚪ 중립 / 🔴 부정 배지 표시

#### 업데이트된 API 엔드포인트

| 메서드 | 경로 | 기능 |
|--------|------|------|
| GET | `/forecast/{symbol}` | 몬테카를로 30일 주가 예측 |
| GET | `/backtest/{symbol}` | MA5/MA20 전략 백테스팅 |
| GET | `/compare` | 전체 종목 수익률 비교 + 상관관계 |

---

### v260517.1 (2026-05-17)

**풀스택 완성 버전 — FastAPI 백엔드 + Streamlit 대시보드 + 펀더멘털 + 뉴스 기능 추가**

#### 추가된 기능

**1. FastAPI 백엔드 (`src/api.py`)**
- REST API 서버 구축 (Swagger UI 자동 생성)
- 주요 엔드포인트:

| 메서드 | 경로 | 기능 |
|--------|------|------|
| GET | `/` | 서버 상태 + 마지막 수집 시간 |
| POST | `/collect` | 데이터 수집 + Vector DB 갱신 |
| GET | `/symbols` | 지원 종목 목록 |
| GET | `/prices` | 전체 종목 최신 가격 및 등락률 |
| GET | `/signal/{symbol}` | AI 매수/매도/관망 신호 |
| GET | `/risk/{symbol}` | AI 리스크 수준 |
| GET | `/strategy/{symbol}` | AI 종합 트레이딩 전략 |
| GET | `/fundamentals/{symbol}` | 펀더멘털 데이터 |
| GET | `/news/{symbol}` | 최신 뉴스 목록 |
| POST | `/chat` | 챗봇 질의응답 |

- 서버 시작 시 데이터가 오래됐으면 **자동 수집**
- AI 분석 결과 **1시간 캐싱** (불필요한 API 호출 방지)
- 429 Rate Limit 발생 시 **자동 재시도** (최대 3회)

**2. Streamlit 대시보드 (`dashboard/app.py`)**
- 6개 탭 구성:
  - 📊 **주가 차트**: 캔들차트 + MA5/20/60 + 볼린저 밴드 + RSI + 거래량
  - 📋 **펀더멘털**: 밸류에이션 / 수익성 / 성장성 / 재무 안정성 카드
  - 📰 **뉴스**: 최신 뉴스 제목 + 출처 + 링크 + 감성 배지 (🟢/⚪/🔴)
  - 🔍 **비교 분석**: 기간별 수익률 히트맵 + 종목 간 상관관계 매트릭스
  - 🤖 **AI 분석**: 매매 신호 + 리스크 + 전략 텍스트 + 30일 주가 예측 + 백테스팅
  - 💬 **챗봇**: 자유 질의응답 채팅 UI
- 사이드바 🔄 데이터 수집 버튼 (클릭 한 번으로 전체 종목 갱신)
- 마지막 수집 시간 표시

**3. 펀더멘털 분석 (`src/collector.py`, `src/processor.py`)**
- `get_fundamentals()`: PER, Forward PER, PBR, EPS, ROE, 영업이익률, 순이익률, 매출/이익 성장률(YoY), 부채비율, 유동비율, 시가총액, 베타, 52주 고저가, 배당수익률 수집
- `summarize_fundamentals()`: 펀더멘털 데이터를 LLM 입력용 자연어 텍스트로 변환
- AI 에이전트가 **기술적 분석 + 펀더멘털을 동시에 반영**하여 판단

**4. 뉴스 수집 및 RAG 통합 (`src/collector.py`, `src/rag.py`)**
- `get_news()`: yfinance 기반 종목별 최신 뉴스 수집 (무료)
- 뉴스 제목/출처/링크/발행시간 파싱
- `store_news_all()`: 뉴스를 ChromaDB Vector DB에 임베딩 저장
- AI 에이전트 분석 시 **관련 뉴스 컨텍스트 자동 참고**

**5. 데이터 수집 기간 확장**
- 기존 6개월 → **5년치** 일봉 데이터 수집
- MA60 등 장기 지표 정확도 향상, 장기 추세 파악 가능

---

### v260516.1 (2026-05-16)

**최초 구현 버전 — 데이터 수집 / 지표 계산 / RAG / Multi-Agent 핵심 기능 완성**

**1. 데이터 수집 모듈 (`src/collector.py`)**
- yfinance 기반 반도체 종목 주가 자동 수집 (API 키 불필요, 무료)
- 수집 종목: NVDA, AMD, INTC, ASML, TSM, SK하이닉스(000660.KS), SOXX ETF, SMH ETF
- CSV 파일 자동 저장 및 최신 가격 요약 기능

**2. 기술 지표 계산 모듈 (`src/processor.py`)**
- 이동평균선 (MA5 / MA20 / MA60)
- RSI 14일 (과매수/과매도/중립 자동 해석)
- 볼린저 밴드 (상단/중간/하단)
- 거래량 이동평균 (20일) 및 급등/감소 감지
- 지표 결과를 LLM 입력용 자연어 텍스트로 자동 변환

**3. RAG 시스템 (`src/rag.py`)**
- ChromaDB 기반 로컬 Vector DB 구축
- 시장 분석 요약을 임베딩하여 저장
- 키워드가 아닌 **의미 기반 시장 데이터 검색** 구현
- AI 에이전트에게 전달할 관련 컨텍스트 자동 생성

**4. Multi-Agent AI 시스템 (`src/agent.py`)**
- Google Gemini API 연동
- **Signal Agent**: 매수 / 매도 / 관망 신호 판단 + 근거 생성
- **Risk Agent**: 리스크 수준(낮음/중간/높음) 평가
- **Strategy Agent**: Signal + Risk 결과를 종합한 트레이딩 전략 추천
- **Chat Agent**: 트레이더 자유 질의응답 챗봇

---

## 기술 스택

| 분류 | 기술 |
|------|------|
| 언어 | Python 3.x |
| LLM | Google Gemini API |
| Vector DB | ChromaDB |
| 데이터 수집 | yfinance |
| 데이터 처리 | pandas, numpy |
| 백엔드 | FastAPI + uvicorn |
| 대시보드 | Streamlit + Plotly |

---

## 프로젝트 구조

```
trading_system/
├── .env                    ← API 키 (git 제외)
├── .gitignore
├── requirements.txt
├── README.md
├── data/                   ← 수집 데이터 CSV (git 제외)
├── database/               ← ChromaDB 저장소 (git 제외)
├── src/
│   ├── collector.py        ← 주가 / 펀더멘털 / 뉴스 수집 + 감성 분석
│   ├── processor.py        ← 기술 지표 + 펀더멘털 + 몬테카를로 예측
│   ├── backtest.py         ← MA5/MA20 골든크로스 백테스팅
│   ├── rag.py              ← RAG 시스템 (시장 요약 + 뉴스)
│   ├── agent.py            ← Multi-Agent AI
│   └── api.py              ← FastAPI 백엔드
└── dashboard/
    └── app.py              ← Streamlit 대시보드 (6탭)
```

---

## 설치 및 실행

### 1. 환경 세팅

```bash
python -m venv venv
venv\Scripts\activate       # Windows
pip install -r requirements.txt
```

### 2. API 키 설정

`.env` 파일 생성 후 Gemini API 키 입력:
```
GEMINI_API_KEY=발급받은키
```

### 3. 서버 실행

**터미널 1 — FastAPI 백엔드:**
```bash
cd src
python api.py
# → http://localhost:8000 (Swagger UI: /docs)
```

**터미널 2 — Streamlit 대시보드:**
```bash
streamlit run dashboard/app.py
# → http://localhost:8501
```

> 서버 시작 시 데이터가 오래됐으면 자동 수집됩니다.
> 대시보드 사이드바의 🔄 버튼으로 언제든 수동 수집 가능합니다.

---

## 개발 목적

퍼블릭에이아이(PublicAI) AI 인턴십 포트폴리오 프로젝트
- RAG, Multi-Agent 아키텍처, Vector DB 등 최신 AI 기술 스택 실전 적용
- 반도체 도메인 특화 금융 AI 시스템 구축 경험
- 기술적 분석 + 펀더멘털 + 뉴스를 통합한 종합 분석 AI 구현
