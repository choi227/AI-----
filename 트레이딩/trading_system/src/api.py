import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import pandas as pd

from collector import load_stock_data, collect_stock_data, get_fundamentals, get_news, SYMBOLS
from rag import store_market_summaries
from agent import signal_agent, risk_agent, strategy_agent, chat_agent
from processor import calculate_indicators, price_forecast
from backtest import run_backtest

last_collected: Optional[datetime] = None

# symbol → {result, cached_at} 형태로 저장
_strategy_cache: dict = {}
CACHE_TTL_MINUTES = 60


def _run_collection():
    """데이터 수집 + Vector DB 갱신"""
    global last_collected
    print(f"[수집 시작] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    collect_stock_data()
    store_market_summaries()
    last_collected = datetime.now()
    print(f"[수집 완료] {last_collected.strftime('%Y-%m-%d %H:%M:%S')}")


def _collect_if_stale():
    """데이터가 하루 이상 오래됐으면 서버 시작 시 자동 수집"""
    data = load_stock_data()
    if not data:
        _run_collection()
        return

    symbol = next(iter(data))
    last_date = data[symbol].index[-1].date()
    today = datetime.now().date()

    if (today - last_date).days >= 1:
        _run_collection()


@asynccontextmanager
async def lifespan(app: FastAPI):
    _collect_if_stale()
    yield


# ── FastAPI 앱 ────────────────────────────────────

app = FastAPI(
    title="반도체 트레이딩 AI API",
    description="AI 기반 반도체 주식 분석 및 트레이딩 전략 추천 시스템",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── 요청/응답 스키마 ──────────────────────────────

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    answer: str

class SignalResponse(BaseModel):
    symbol: str
    name: str
    signal: str
    reason: str

class RiskResponse(BaseModel):
    symbol: str
    name: str
    risk: str
    reason: str

class StrategyResponse(BaseModel):
    symbol: str
    name: str
    signal: str
    risk: str
    strategy: str

class PriceItem(BaseModel):
    symbol: str
    name: str
    price: float
    change_pct: Optional[float]

class SymbolItem(BaseModel):
    symbol: str
    name: str


# ── 유효성 검사 헬퍼 ──────────────────────────────

def _validate_symbol(symbol: str) -> str:
    symbol = symbol.upper()
    if symbol not in SYMBOLS:
        raise HTTPException(
            status_code=404,
            detail=f"지원하지 않는 종목입니다: {symbol}. /symbols 에서 지원 종목을 확인하세요.",
        )
    return symbol


def _check_data(symbol: str) -> None:
    data = load_stock_data()
    if symbol not in data:
        raise HTTPException(
            status_code=503,
            detail=f"{symbol} 데이터가 없습니다. /collect 로 데이터를 수집하세요.",
        )


# ── 엔드포인트 ────────────────────────────────────

@app.get("/", tags=["상태"])
def root():
    """서버 상태 및 마지막 수집 시간 확인"""
    return {
        "status": "ok",
        "service": "반도체 트레이딩 AI API",
        "version": "1.0.0",
        "last_collected": last_collected.strftime("%Y-%m-%d %H:%M:%S") if last_collected else "서버 시작 시 수집됨",
        "next_auto_collect": "매일 오전 07:00",
        "docs": "/docs",
    }


@app.post("/collect", tags=["데이터 수집"])
def collect():
    """
    주가 데이터 수집 + Vector DB 갱신 (수동 실행)

    전체 종목 최신 데이터를 수집하고 AI 분석용 Vector DB를 갱신합니다.
    """
    try:
        _run_collection()
        return {
            "status": "ok",
            "message": f"{len(SYMBOLS)}개 종목 데이터 수집 완료",
            "collected_at": last_collected.strftime("%Y-%m-%d %H:%M:%S"),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"수집 실패: {e}")


@app.get("/symbols", response_model=list[SymbolItem], tags=["종목"])
def get_symbols():
    """지원하는 종목 목록 반환"""
    return [{"symbol": sym, "name": name} for sym, name in SYMBOLS.items()]


@app.get("/prices", response_model=list[PriceItem], tags=["종목"])
def get_prices():
    """전체 종목 최신 가격 및 등락률 반환"""
    data = load_stock_data()
    if not data:
        raise HTTPException(status_code=503, detail="데이터가 없습니다. /collect 를 먼저 실행하세요.")

    result = []
    for symbol, df in data.items():
        if df.empty or len(df) < 2:
            continue
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        change_pct = (latest["Close"] - prev["Close"]) / prev["Close"] * 100
        result.append(PriceItem(
            symbol=symbol,
            name=SYMBOLS.get(symbol, symbol),
            price=round(float(latest["Close"]), 2),
            change_pct=round(change_pct, 2),
        ))
    return result


@app.get("/signal/{symbol}", response_model=SignalResponse, tags=["AI 분석"])
def get_signal(symbol: str):
    """매수 / 매도 / 관망 신호 반환"""
    symbol = _validate_symbol(symbol)
    _check_data(symbol)
    result = signal_agent(symbol)
    return SignalResponse(**{k: result[k] for k in ["symbol", "name", "signal", "reason"]})


@app.get("/risk/{symbol}", response_model=RiskResponse, tags=["AI 분석"])
def get_risk(symbol: str):
    """투자 리스크 수준 반환 (낮음 / 중간 / 높음)"""
    symbol = _validate_symbol(symbol)
    _check_data(symbol)
    result = risk_agent(symbol)
    return RiskResponse(**{k: result[k] for k in ["symbol", "name", "risk", "reason"]})


@app.get("/strategy/{symbol}", response_model=StrategyResponse, tags=["AI 분석"])
def get_strategy(symbol: str, force: bool = False):
    """
    Signal + Risk 종합 트레이딩 전략 반환

    - **force=true** 쿼리 추가 시 캐시 무시하고 새로 분석
    - 기본값: 1시간 내 동일 종목 재분석 시 캐시 반환 (API 절약)
    """
    symbol = _validate_symbol(symbol)
    _check_data(symbol)

    cached = _strategy_cache.get(symbol)
    if not force and cached:
        elapsed = (datetime.now() - cached["cached_at"]).total_seconds() / 60
        if elapsed < CACHE_TTL_MINUTES:
            return StrategyResponse(**cached["result"])

    result = strategy_agent(symbol)
    _strategy_cache[symbol] = {"result": {k: result[k] for k in ["symbol", "name", "signal", "risk", "strategy"]}, "cached_at": datetime.now()}
    return StrategyResponse(**_strategy_cache[symbol]["result"])


@app.get("/fundamentals/{symbol}", tags=["종목"])
def get_fundamentals_data(symbol: str):
    """종목 펀더멘털 데이터 반환 (PER, PBR, ROE, 성장률 등)"""
    symbol = _validate_symbol(symbol)
    data = get_fundamentals(symbol)
    data["symbol"] = symbol
    data["name"] = SYMBOLS.get(symbol, symbol)
    return data


@app.get("/news/{symbol}", tags=["종목"])
def get_news_data(symbol: str, max_items: int = 10):
    """종목 최신 뉴스 반환"""
    symbol = _validate_symbol(symbol)
    news = get_news(symbol, max_items=max_items)
    return {"symbol": symbol, "name": SYMBOLS.get(symbol, symbol), "news": news}


@app.get("/backtest/{symbol}", tags=["AI 분석"])
def get_backtest(symbol: str):
    """
    MA5/MA20 골든크로스 전략 백테스팅

    5년치 과거 데이터 기반 — 전략 수익률 / 매수보유 수익률 / 승률 / 최대 낙폭 반환
    """
    symbol = _validate_symbol(symbol)
    _check_data(symbol)
    data = load_stock_data()
    df = calculate_indicators(data[symbol])
    return run_backtest(symbol, df)


@app.get("/compare", tags=["종목"])
def get_compare():
    """전체 종목 수익률 비교 및 상관관계 매트릭스"""
    data = load_stock_data()
    if not data:
        raise HTTPException(status_code=503, detail="데이터가 없습니다.")

    performance = []
    for symbol, df in data.items():
        if df.empty or len(df) < 30:
            continue
        close = df["Close"].dropna()
        current = float(close.iloc[-1])

        def ret(days, c=close, cur=current):
            if len(c) >= days:
                prev = float(c.iloc[-days])
                return round((cur - prev) / prev * 100, 1) if prev else None
            return None

        performance.append({
            "symbol":        symbol,
            "name":          SYMBOLS.get(symbol, symbol),
            "current_price": round(current, 2),
            "return_1w":     ret(5),
            "return_1m":     ret(21),
            "return_3m":     ret(63),
            "return_1y":     ret(252),
        })

    close_df = pd.DataFrame({sym: df["Close"] for sym, df in data.items() if not df.empty})
    returns_df = close_df.pct_change()
    corr = returns_df.corr().round(3)

    corr_data = {
        s1: {s2: (float(corr.loc[s1, s2]) if not pd.isna(corr.loc[s1, s2]) else None) for s2 in corr.columns}
        for s1 in corr.index
    }

    return {"performance": performance, "correlation": corr_data}


@app.get("/forecast/{symbol}", tags=["AI 분석"])
def get_forecast(symbol: str):
    """
    30일 주가 예측 (몬테카를로 시뮬레이션 10,000회)

    과거 변동성 기반 통계 모델 — 상승/중립/하락 시나리오별 예상 가격 및 확률 반환
    """
    symbol = _validate_symbol(symbol)
    _check_data(symbol)
    data = load_stock_data()
    df = calculate_indicators(data[symbol])
    return price_forecast(symbol, df)


@app.post("/chat", response_model=ChatResponse, tags=["챗봇"])
def chat(request: ChatRequest):
    """트레이더 자유 질의응답 챗봇"""
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="메시지를 입력하세요.")
    return ChatResponse(answer=chat_agent(request.message))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
