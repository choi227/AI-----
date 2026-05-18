import yfinance as yf
import pandas as pd
import os

# 수집할 반도체 종목 및 ETF
SYMBOLS = {
    "NVDA": "엔비디아",
    "AMD": "AMD",
    "INTC": "인텔",
    "ASML": "ASML",
    "TSM": "TSMC",
    "000660.KS": "SK하이닉스",
    "SOXX": "반도체 ETF (SOXX)",
    "SMH": "반도체 ETF (SMH)",
}

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

_SENT_POS = {
    "beat", "record", "growth", "strong", "upgrade", "buy", "outperform",
    "rally", "surge", "profit", "gain", "rise", "bullish", "positive",
    "success", "expand", "improve", "exceed", "robust", "boost", "high",
}
_SENT_NEG = {
    "miss", "decline", "loss", "downgrade", "sell", "underperform", "cut",
    "warning", "concern", "risk", "fall", "drop", "bearish", "negative",
    "weak", "reduce", "decrease", "lower", "disappointing", "recession",
}


def _analyze_sentiment(text: str) -> dict:
    words = set(text.lower().split())
    pos = len(words & _SENT_POS)
    neg = len(words & _SENT_NEG)
    total = pos + neg
    score = round((pos - neg) / total, 2) if total else 0.0
    label = "긍정" if score > 0.15 else ("부정" if score < -0.15 else "중립")
    return {"score": score, "label": label}


def collect_stock_data(period: str = "5y") -> dict[str, pd.DataFrame]:
    """
    반도체 종목 주가 데이터 수집
    period: 수집 기간 (1mo, 3mo, 6mo, 1y, 2y)
    """
    os.makedirs(DATA_DIR, exist_ok=True)
    result = {}

    print(f"[데이터 수집 시작] 기간: {period}")

    for symbol, name in SYMBOLS.items():
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period)

            if df.empty:
                print(f"  [FAIL] {name} ({symbol}) - 데이터 없음")
                continue

            # 필요한 컬럼만 유지
            df = df[["Open", "High", "Low", "Close", "Volume"]]
            df.index = pd.to_datetime(df.index).tz_localize(None)

            # CSV 저장
            filename = f"{symbol.replace('.', '_')}.csv"
            filepath = os.path.join(DATA_DIR, filename)
            df.to_csv(filepath)

            result[symbol] = df
            print(f"  [OK] {name} ({symbol}) - {len(df)}일치 수집 완료")

        except Exception as e:
            print(f"  [FAIL] {name} ({symbol}) - 오류: {e}")

    print(f"\n[수집 완료] {len(result)}/{len(SYMBOLS)} 종목 성공")
    return result


def load_stock_data() -> dict[str, pd.DataFrame]:
    """저장된 CSV 파일에서 데이터 불러오기"""
    result = {}

    for symbol in SYMBOLS:
        filename = f"{symbol.replace('.', '_')}.csv"
        filepath = os.path.join(DATA_DIR, filename)

        if os.path.exists(filepath):
            df = pd.read_csv(filepath, index_col=0, parse_dates=True)
            result[symbol] = df

    return result


def get_latest_prices() -> pd.DataFrame:
    """각 종목의 최신 가격 요약 반환"""
    data = load_stock_data()
    rows = []

    for symbol, df in data.items():
        if df.empty:
            continue
        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) >= 2 else latest
        change_pct = (latest["Close"] - prev["Close"]) / prev["Close"] * 100

        rows.append({
            "종목": SYMBOLS.get(symbol, symbol),
            "심볼": symbol,
            "현재가": round(latest["Close"], 2),
            "전일대비(%)": round(change_pct, 2),
            "거래량": int(latest["Volume"]),
            "기준일": df.index[-1].strftime("%Y-%m-%d"),
        })

    return pd.DataFrame(rows)


def get_news(symbol: str, max_items: int = 10) -> list[dict]:
    """
    종목 최신 뉴스 수집 (yfinance 기반, 무료)
    반환: 제목, 출처, URL, 발행시간 리스트
    """
    import time

    try:
        ticker = yf.Ticker(symbol)
        raw_news = ticker.news or []
    except Exception as e:
        return [{"error": str(e)}]

    result = []
    for item in raw_news[:max_items]:
        content = item.get("content", {})
        if isinstance(content, dict):
            title     = content.get("title", item.get("title", ""))
            publisher = content.get("provider", {}).get("displayName", item.get("publisher", ""))
            link      = content.get("canonicalUrl", {}).get("url", item.get("link", ""))
            pub_time  = content.get("pubDate", "")
            if pub_time:
                try:
                    from datetime import datetime
                    pub_time = datetime.strptime(pub_time[:19], "%Y-%m-%dT%H:%M:%S").strftime("%Y-%m-%d %H:%M")
                except Exception:
                    pass
        else:
            title     = item.get("title", "")
            publisher = item.get("publisher", "")
            link      = item.get("link", "")
            ts        = item.get("providerPublishTime")
            pub_time  = time.strftime("%Y-%m-%d %H:%M", time.localtime(ts)) if ts else ""

        if title:
            result.append({
                "title":     title,
                "publisher": publisher,
                "link":      link,
                "pub_time":  pub_time,
                "symbol":    symbol,
                "sentiment": _analyze_sentiment(title),
            })

    return result


def get_fundamentals(symbol: str) -> dict:
    """
    종목 펀더멘털 데이터 수집 (yfinance .info 기반)
    반환: PER, PBR, EPS, ROE, 부채비율, 매출성장률, 영업이익률 등
    """
    try:
        info = yf.Ticker(symbol).info
    except Exception as e:
        return {"error": str(e)}

    def safe(key, default=None):
        val = info.get(key, default)
        return val if val not in (None, "N/A", float("inf")) else None

    return {
        "market_cap":        safe("marketCap"),
        "per":               safe("trailingPE"),
        "forward_per":       safe("forwardPE"),
        "pbr":               safe("priceToBook"),
        "eps":               safe("trailingEps"),
        "roe":               safe("returnOnEquity"),
        "debt_to_equity":    safe("debtToEquity"),
        "current_ratio":     safe("currentRatio"),
        "revenue_growth":    safe("revenueGrowth"),
        "earnings_growth":   safe("earningsGrowth"),
        "gross_margin":      safe("grossMargins"),
        "operating_margin":  safe("operatingMargins"),
        "profit_margin":     safe("profitMargins"),
        "beta":              safe("beta"),
        "week52_high":       safe("fiftyTwoWeekHigh"),
        "week52_low":        safe("fiftyTwoWeekLow"),
        "dividend_yield":    safe("dividendYield"),
    }


if __name__ == "__main__":
    collect_stock_data(period="6mo")

    print("\n[최신 가격 요약]")
    print(get_latest_prices().to_string(index=False))

    print("\n[펀더멘털 테스트 - NVDA]")
    f = get_fundamentals("NVDA")
    for k, v in f.items():
        print(f"  {k}: {v}")
