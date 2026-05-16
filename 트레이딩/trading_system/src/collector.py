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


def collect_stock_data(period: str = "6mo") -> dict[str, pd.DataFrame]:
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


if __name__ == "__main__":
    collect_stock_data(period="6mo")

    print("\n[최신 가격 요약]")
    print(get_latest_prices().to_string(index=False))
