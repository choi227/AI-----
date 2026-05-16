# 반도체 트레이딩 AI 시스템

> AI 기반 반도체 주식 시장 분석 및 트레이딩 전략 추천 시스템

---

## 프로젝트 개요

전 세계 주요 반도체 종목(NVDA, AMD, INTC, ASML, TSM, SK하이닉스)의 주가 데이터를 자동 수집하고,
AI가 기술 지표를 분석해 트레이더에게 **매수/매도 신호, 리스크 수준, 트레이딩 전략**을 제공하는 에이전트 기반 시스템입니다.

단순한 데이터 시각화 도구가 아닌, **AI가 스스로 판단하고 추천하는 Multi-Agent 구조**로 설계되었습니다.

---

## 시스템 아키텍처

```
[yfinance — 반도체 주가 데이터 자동 수집]
            ↓
[기술 지표 계산 — MA, RSI, 볼린저 밴드, 거래량]
            ↓
[Vector DB (ChromaDB RAG) — 시장 분석 지식 저장]
            ↓
[Multi-Agent — 신호 판단 / 리스크 감지 / 전략 추천]
            ↓
[FastAPI 백엔드 + Streamlit 대시보드] (개발 예정)
```

---

## 버전 히스토리

### v260516.1 (2026-05-16)

**최초 구현 버전 — 데이터 수집 / 지표 계산 / RAG / Multi-Agent 핵심 기능 완성**

#### 추가된 기능

**1. 데이터 수집 모듈 (`src/collector.py`)**
- yfinance 기반 반도체 종목 주가 자동 수집 (API 키 불필요, 무료)
- 수집 종목: NVDA, AMD, INTC, ASML, TSM, SK하이닉스(000660.KS), SOXX ETF, SMH ETF
- 수집 기간 설정 가능 (기본 6개월)
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
| 백엔드 | FastAPI (예정) |
| 대시보드 | Streamlit (예정) |

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
│   ├── collector.py        ← 주가 데이터 수집
│   ├── processor.py        ← 기술 지표 계산
│   ├── rag.py              ← RAG 시스템
│   ├── agent.py            ← Multi-Agent AI
│   └── api.py              ← FastAPI 백엔드 (예정)
└── dashboard/
    └── app.py              ← Streamlit 대시보드 (예정)
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

### 3. 데이터 수집 및 AI 분석 실행

```bash
# 반도체 주가 데이터 수집
python src/collector.py

# 기술 지표 계산
python src/processor.py

# Vector DB 저장 및 검색 테스트
python src/rag.py

# AI 에이전트 분석 실행
python src/agent.py
```

---

## 다음 버전 예정 (v260516.2~)

- [ ] FastAPI 백엔드 REST API 구현
- [ ] Streamlit 대시보드 (실시간 차트 + AI 신호 표시)
- [ ] 챗봇 인터페이스 UI
- [ ] 전체 파이프라인 통합 테스트

---

## 개발 목적

퍼블릭에이아이(PublicAI) AI 인턴십 포트폴리오 프로젝트
- RAG, Multi-Agent 아키텍처, Vector DB 등 최신 AI 기술 스택 실전 적용
- 반도체 도메인 특화 금융 AI 시스템 구축 경험
