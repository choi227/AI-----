import pandas as pd
import numpy as np
import os
from collector import load_stock_data, get_fundamentals, SYMBOLS

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """주가 데이터에 기술 지표 추가"""
    df = df.copy()

    df["MA5"]  = df["Close"].rolling(window=5).mean()
    df["MA20"] = df["Close"].rolling(window=20).mean()
    df["MA60"] = df["Close"].rolling(window=60).mean()

    delta = df["Close"].diff()
    gain  = delta.clip(lower=0)
    loss  = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=14).mean()
    avg_loss = loss.rolling(window=14).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    df["RSI"] = 100 - (100 / (1 + rs))

    df["BB_mid"]   = df["Close"].rolling(window=20).mean()
    df["BB_upper"] = df["BB_mid"] + 2 * df["Close"].rolling(window=20).std()
    df["BB_lower"] = df["BB_mid"] - 2 * df["Close"].rolling(window=20).std()

    df["Volume_MA20"] = df["Volume"].rolling(window=20).mean()

    return df


def summarize_fundamentals(symbol: str) -> str:
    """펀더멘털 데이터를 LLM이 읽을 수 있는 텍스트로 변환"""
    f = get_fundamentals(symbol)

    if "error" in f:
        return f"[펀더멘털] 데이터 수집 실패: {f['error']}"

    def fmt_pct(v):
        return f"{v*100:.1f}%" if v is not None else "N/A"

    def fmt_num(v, decimals=2):
        return f"{v:,.{decimals}f}" if v is not None else "N/A"

    def fmt_cap(v):
        if v is None:
            return "N/A"
        if v >= 1e12:
            return f"{v/1e12:.2f}조 달러"
        if v >= 1e9:
            return f"{v/1e9:.1f}십억 달러"
        return f"{v:,.0f}"

    per = f.get("per")
    if per is None:
        per_signal = "PER 데이터 없음"
    elif per < 15:
        per_signal = f"저평가 구간 (PER {per:.1f})"
    elif per > 40:
        per_signal = f"고평가 구간 (PER {per:.1f}) - 성장 기대 반영"
    else:
        per_signal = f"적정 구간 (PER {per:.1f})"

    high = f.get("week52_high")
    low  = f.get("week52_low")
    if high and low and high != low:
        close_data = load_stock_data()
        if symbol in close_data:
            current = float(close_data[symbol].iloc[-1]["Close"])
            pct_from_high = (current - high) / high * 100
            pct_from_low  = (current - low)  / low  * 100
            week52_signal = (
                f"52주 고가 대비 {pct_from_high:.1f}% / "
                f"52주 저가 대비 +{pct_from_low:.1f}%"
            )
        else:
            week52_signal = f"고가 {fmt_num(high)} / 저가 {fmt_num(low)}"
    else:
        week52_signal = "N/A"

    return f"""
[펀더멘털 분석]
시가총액: {fmt_cap(f.get('market_cap'))}
베타(변동성): {fmt_num(f.get('beta'))}

[밸류에이션]
{per_signal}
선행 PER: {fmt_num(f.get('forward_per'))}
PBR: {fmt_num(f.get('pbr'))}
EPS: {fmt_num(f.get('eps'))}

[수익성]
ROE: {fmt_pct(f.get('roe'))}
매출총이익률: {fmt_pct(f.get('gross_margin'))}
영업이익률: {fmt_pct(f.get('operating_margin'))}
순이익률: {fmt_pct(f.get('profit_margin'))}

[성장성]
매출 성장률(YoY): {fmt_pct(f.get('revenue_growth'))}
이익 성장률(YoY): {fmt_pct(f.get('earnings_growth'))}

[재무 안정성]
부채비율(D/E): {fmt_num(f.get('debt_to_equity'))}
유동비율: {fmt_num(f.get('current_ratio'))}

[52주 가격 범위]
{week52_signal}
배당 수익률: {fmt_pct(f.get('dividend_yield'))}
""".strip()


def summarize_for_llm(symbol: str, df: pd.DataFrame) -> str:
    """기술 지표 + 펀더멘털을 LLM이 읽을 수 있는 텍스트로 변환"""
    latest = df.iloc[-1]
    name   = SYMBOLS.get(symbol, symbol)

    if pd.isna(latest["MA20"]):
        trend = "추세 판단 불가 (데이터 부족)"
    elif latest["Close"] > latest["MA20"]:
        trend = "상승 추세 (현재가 > 20일 이동평균)"
    else:
        trend = "하락 추세 (현재가 < 20일 이동평균)"

    rsi = latest["RSI"]
    if pd.isna(rsi):
        rsi_signal = "RSI 계산 불가 (데이터 부족)"
    elif rsi >= 70:
        rsi_signal = f"과매수 구간 ({rsi:.1f}) - 조정 가능성"
    elif rsi <= 30:
        rsi_signal = f"과매도 구간 ({rsi:.1f}) - 반등 가능성"
    else:
        rsi_signal = f"중립 구간 ({rsi:.1f})"

    close = latest["Close"]
    if pd.isna(latest["BB_upper"]):
        bb_signal = "볼린저 밴드 계산 불가 (데이터 부족)"
    elif close > latest["BB_upper"]:
        bb_signal = "볼린저 밴드 상단 돌파 - 강한 상승 or 과열"
    elif close < latest["BB_lower"]:
        bb_signal = "볼린저 밴드 하단 이탈 - 강한 하락 or 과매도"
    else:
        bb_signal = "볼린저 밴드 중간 구간"

    if pd.isna(latest["Volume_MA20"]) or latest["Volume_MA20"] == 0:
        vol_signal = "거래량 분석 불가 (데이터 부족)"
    else:
        vol_ratio = latest["Volume"] / latest["Volume_MA20"]
        if vol_ratio > 1.5:
            vol_signal = f"거래량 급증 ({vol_ratio:.1f}배) - 강한 움직임 예상"
        elif vol_ratio < 0.5:
            vol_signal = f"거래량 감소 ({vol_ratio:.1f}배) - 관망세"
        else:
            vol_signal = f"거래량 보통 ({vol_ratio:.1f}배)"

    technical = f"""
[{name} ({symbol}) 시장 분석 요약]
기준일: {df.index[-1].strftime('%Y-%m-%d')}
현재가: {close:,.2f}
전일 대비: {((close - df.iloc[-2]['Close']) / df.iloc[-2]['Close'] * 100):.2f}%

[추세]
{trend}
- MA5:  {latest['MA5']:,.2f}
- MA20: {latest['MA20']:,.2f}
- MA60: {latest['MA60']:,.2f}

[RSI 신호]
{rsi_signal}

[볼린저 밴드]
{bb_signal}
- 상단: {latest['BB_upper']:,.2f}
- 중간: {latest['BB_mid']:,.2f}
- 하단: {latest['BB_lower']:,.2f}

[거래량]
{vol_signal}
""".strip()

    return technical + "\n\n" + summarize_fundamentals(symbol)


def price_forecast(symbol: str, df: pd.DataFrame, days: int = 30, simulations: int = 10000) -> dict:
    """몬테카를로 시뮬레이션 기반 주가 예측 (상승/중립/하락 시나리오)"""
    closes = df["Close"].dropna()
    if len(closes) < 60:
        return {"error": "데이터 부족 (최소 60일 필요)"}

    log_returns = np.log(closes / closes.shift(1)).dropna()
    mu    = float(log_returns.mean())
    sigma = float(log_returns.std())
    current_price = float(closes.iloc[-1])

    np.random.seed(42)
    random_shocks = np.random.normal(mu, sigma, (simulations, days))
    final_prices  = current_price * np.exp(np.sum(random_shocks, axis=1))

    p30 = float(np.percentile(final_prices, 30))
    p70 = float(np.percentile(final_prices, 70))

    bear = final_prices[final_prices <= p30]
    base = final_prices[(final_prices > p30) & (final_prices < p70)]
    bull = final_prices[final_prices >= p70]

    def chg(v):
        return round((float(v) - current_price) / current_price * 100, 1)

    return {
        "symbol": symbol,
        "name": SYMBOLS.get(symbol, symbol),
        "current_price": round(current_price, 2),
        "days": days,
        "simulations": simulations,
        "scenarios": [
            {"label": "상승", "price": round(float(np.mean(bull)), 2), "change_pct": chg(np.mean(bull)), "probability": round(len(bull) / simulations * 100, 1)},
            {"label": "중립", "price": round(float(np.mean(base)), 2), "change_pct": chg(np.mean(base)), "probability": round(len(base) / simulations * 100, 1)},
            {"label": "하락", "price": round(float(np.mean(bear)), 2), "change_pct": chg(np.mean(bear)), "probability": round(len(bear) / simulations * 100, 1)},
        ],
        "distribution": [round(float(p), 2) for p in final_prices[::10].tolist()],
    }


def process_all() -> dict[str, pd.DataFrame]:
    """전체 종목 지표 계산 및 CSV 저장"""
    data = load_stock_data()
    processed = {}

    print("[지표 계산 시작]")

    for symbol, df in data.items():
        df_with_indicators = calculate_indicators(df)

        filename = f"{symbol.replace('.', '_')}_processed.csv"
        filepath = os.path.join(DATA_DIR, filename)
        df_with_indicators.to_csv(filepath)

        processed[symbol] = df_with_indicators
        print(f"  [OK] {SYMBOLS.get(symbol, symbol)} ({symbol})")

    print(f"\n[완료] {len(processed)}개 종목 처리")
    return processed


if __name__ == "__main__":
    processed = process_all()

    print("\n[LLM 입력용 텍스트 샘플 - NVDA]")
    print("-" * 50)
    print(summarize_for_llm("NVDA", processed["NVDA"]))
