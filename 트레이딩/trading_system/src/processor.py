import pandas as pd
import numpy as np
import os
from collector import load_stock_data, SYMBOLS

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """주가 데이터에 기술 지표 추가"""
    df = df.copy()

    # 이동평균선
    df["MA5"]  = df["Close"].rolling(window=5).mean()
    df["MA20"] = df["Close"].rolling(window=20).mean()
    df["MA60"] = df["Close"].rolling(window=60).mean()

    # RSI (14일)
    delta = df["Close"].diff()
    gain  = delta.clip(lower=0)
    loss  = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=14).mean()
    avg_loss = loss.rolling(window=14).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    df["RSI"] = 100 - (100 / (1 + rs))

    # 볼린저 밴드 (20일, 2 표준편차)
    df["BB_mid"]   = df["Close"].rolling(window=20).mean()
    df["BB_upper"] = df["BB_mid"] + 2 * df["Close"].rolling(window=20).std()
    df["BB_lower"] = df["BB_mid"] - 2 * df["Close"].rolling(window=20).std()

    # 거래량 이동평균
    df["Volume_MA20"] = df["Volume"].rolling(window=20).mean()

    return df


def summarize_for_llm(symbol: str, df: pd.DataFrame) -> str:
    """최신 지표를 LLM이 읽을 수 있는 텍스트로 변환"""
    latest = df.iloc[-1]
    name   = SYMBOLS.get(symbol, symbol)

    # 추세 판단 (MA20 NaN 대비)
    if pd.isna(latest["MA20"]):
        trend = "추세 판단 불가 (데이터 부족)"
    elif latest["Close"] > latest["MA20"]:
        trend = "상승 추세 (현재가 > 20일 이동평균)"
    else:
        trend = "하락 추세 (현재가 < 20일 이동평균)"

    # RSI 해석 (NaN 대비)
    rsi = latest["RSI"]
    if pd.isna(rsi):
        rsi_signal = "RSI 계산 불가 (데이터 부족)"
    elif rsi >= 70:
        rsi_signal = f"과매수 구간 ({rsi:.1f}) - 조정 가능성"
    elif rsi <= 30:
        rsi_signal = f"과매도 구간 ({rsi:.1f}) - 반등 가능성"
    else:
        rsi_signal = f"중립 구간 ({rsi:.1f})"

    # 볼린저 밴드 위치 (NaN 대비)
    close = latest["Close"]
    if pd.isna(latest["BB_upper"]):
        bb_signal = "볼린저 밴드 계산 불가 (데이터 부족)"
    elif close > latest["BB_upper"]:
        bb_signal = "볼린저 밴드 상단 돌파 - 강한 상승 or 과열"
    elif close < latest["BB_lower"]:
        bb_signal = "볼린저 밴드 하단 이탈 - 강한 하락 or 과매도"
    else:
        bb_signal = "볼린저 밴드 중간 구간"

    # 거래량 분석 (NaN 대비)
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

    summary = f"""
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

    return summary


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
