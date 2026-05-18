import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import pandas as pd
import numpy as np
from collector import SYMBOLS


def run_backtest(symbol: str, df: pd.DataFrame) -> dict:
    """MA5/MA20 골든크로스 전략 백테스팅"""
    df = df.copy().dropna(subset=["MA5", "MA20", "Close"])
    if len(df) < 60:
        return {"error": "데이터 부족 (최소 60일 필요)"}

    # MA5 > MA20 → 보유(1), 아니면 현금(0), 다음날 실행 (look-ahead bias 방지)
    df["holding"]      = (df["MA5"] > df["MA20"]).astype(int).shift(1).fillna(0)
    df["daily_ret"]    = df["Close"].pct_change().fillna(0)
    df["strategy_ret"] = df["daily_ret"] * df["holding"]

    df["bh_cum"]  = (1 + df["daily_ret"]).cumprod()
    df["str_cum"] = (1 + df["strategy_ret"]).cumprod()

    # 거래 횟수 & 승률
    trades = []
    in_trade, entry = False, 0.0
    for _, row in df.iterrows():
        if row["holding"] == 1 and not in_trade:
            in_trade, entry = True, float(row["Close"])
        elif row["holding"] == 0 and in_trade:
            in_trade = False
            trades.append((float(row["Close"]) - entry) / entry * 100)

    total_trades = len(trades)
    win_rate = round(sum(1 for t in trades if t > 0) / total_trades * 100, 1) if total_trades else 0

    # 최대 낙폭
    peak   = df["str_cum"].cummax()
    max_dd = round(float(((df["str_cum"] - peak) / peak).min() * 100), 1)

    # 누적 수익률 곡선 (5일 단위 샘플링으로 데이터 최소화)
    sampled = df.iloc[::5].dropna(subset=["str_cum", "bh_cum"])
    equity_curve = [
        {
            "date":     str(idx.date()),
            "strategy": round(float(row["str_cum"]), 4),
            "buy_hold": round(float(row["bh_cum"]), 4),
        }
        for idx, row in sampled.iterrows()
    ]

    return {
        "symbol":          symbol,
        "name":            SYMBOLS.get(symbol, symbol),
        "strategy":        "MA5/MA20 골든크로스",
        "period_start":    str(df.index[0].date()),
        "period_end":      str(df.index[-1].date()),
        "strategy_return": round((float(df["str_cum"].iloc[-1]) - 1) * 100, 1),
        "buyhold_return":  round((float(df["bh_cum"].iloc[-1]) - 1) * 100, 1),
        "total_trades":    total_trades,
        "win_rate":        win_rate,
        "max_drawdown":    max_dd,
        "equity_curve":    equity_curve,
    }
