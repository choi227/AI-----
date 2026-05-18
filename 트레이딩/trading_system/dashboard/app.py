import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import requests

from collector import SYMBOLS

API_BASE = "http://localhost:8000"

st.set_page_config(
    page_title="반도체 트레이딩 AI",
    page_icon="📈",
    layout="wide",
)

# ── 스타일 ──────────────────────────────────────
st.markdown("""
<style>
.signal-box {
    padding: 16px 24px;
    border-radius: 10px;
    text-align: center;
    font-size: 1.4rem;
    font-weight: bold;
}
.buy   { background: #d4edda; color: #155724; }
.sell  { background: #f8d7da; color: #721c24; }
.hold  { background: #fff3cd; color: #856404; }
.risk-low  { background: #d4edda; color: #155724; }
.risk-mid  { background: #fff3cd; color: #856404; }
.risk-high { background: #f8d7da; color: #721c24; }
</style>
""", unsafe_allow_html=True)


# ── 유틸 ──────────────────────────────────────

def api_get(path: str, timeout: int = 30):
    try:
        res = requests.get(f"{API_BASE}{path}", timeout=timeout)
        res.raise_for_status()
        return res.json()
    except requests.exceptions.ConnectionError:
        st.error("API 서버에 연결할 수 없습니다. `python src/api.py` 를 먼저 실행하세요.")
        st.stop()
    except requests.exceptions.Timeout:
        st.error("응답 시간이 초과됐습니다. API 서버 상태를 확인하거나 잠시 후 다시 시도하세요.")
        return None
    except Exception as e:
        st.error(f"API 오류: {e}")
        return None


def api_post(path: str, body: dict, timeout: int = 30):
    try:
        res = requests.post(f"{API_BASE}{path}", json=body, timeout=timeout)
        res.raise_for_status()
        return res.json()
    except requests.exceptions.ConnectionError:
        st.error("API 서버에 연결할 수 없습니다.")
        st.stop()
    except requests.exceptions.Timeout:
        st.error("응답 시간이 초과됐습니다. 잠시 후 다시 시도하세요.")
        return None
    except Exception as e:
        st.error(f"API 오류: {e}")
        return None


def signal_color(signal: str) -> str:
    if signal == "매수":
        return "buy"
    if signal == "매도":
        return "sell"
    return "hold"


def risk_color(risk: str) -> str:
    if risk == "낮음":
        return "risk-low"
    if risk == "높음":
        return "risk-high"
    return "risk-mid"


# ── 사이드바 ──────────────────────────────────

st.sidebar.title("📈 반도체 트레이딩 AI")
st.sidebar.markdown("---")

symbol_options = list(SYMBOLS.keys())
symbol_labels  = [f"{SYMBOLS[s]} ({s})" for s in symbol_options]

selected_idx = st.sidebar.selectbox(
    "분석할 종목 선택",
    range(len(symbol_options)),
    format_func=lambda i: symbol_labels[i],
)
selected_symbol = symbol_options[selected_idx]
selected_name   = SYMBOLS[selected_symbol]

st.sidebar.markdown("---")

# 데이터 수집 버튼
if st.sidebar.button("🔄 데이터 수집", use_container_width=True):
    with st.sidebar:
        with st.spinner("수집 중... (30초~1분 소요)"):
            result = api_post("/collect", {})
        if result:
            st.success(f"수집 완료!\n{result.get('collected_at', '')}")

# 마지막 수집 시간 표시
status = api_get("/")
if status and status.get("last_collected"):
    st.sidebar.caption(f"마지막 수집: {status['last_collected']}")

st.sidebar.markdown("---")
run_analysis = st.sidebar.button("🤖 AI 분석 실행", use_container_width=True, type="primary")

st.sidebar.markdown("---")
st.sidebar.markdown("**지원 종목**")
for sym, name in SYMBOLS.items():
    st.sidebar.markdown(f"- {name} `{sym}`")


# ── 메인 헤더 ────────────────────────────────

st.title(f"반도체 트레이딩 AI 대시보드")
st.markdown(f"**분석 종목:** {selected_name} (`{selected_symbol}`)")
st.markdown("---")


# ── 탭 구성 ──────────────────────────────────

tab_chart, tab_fundamental, tab_news, tab_compare, tab_ai, tab_chat = st.tabs(["📊 주가 차트", "📋 펀더멘털", "📰 뉴스", "🔍 비교 분석", "🤖 AI 분석", "💬 챗봇"])


# ── 탭 1: 주가 차트 ──────────────────────────

with tab_chart:
    prices_data = api_get("/prices")
    if prices_data:
        df_prices = pd.DataFrame(prices_data)

        st.subheader("전체 종목 현황")
        cols = st.columns(4)
        for i, row in df_prices.iterrows():
            col = cols[i % 4]
            change = row["change_pct"]
            color  = "green" if change >= 0 else "red"
            arrow  = "▲" if change >= 0 else "▼"
            col.metric(
                label=f"{row['name']} ({row['symbol']})",
                value=f"{row['price']:,.2f}",
                delta=f"{arrow} {abs(change):.2f}%",
            )

    st.markdown("---")
    st.subheader(f"{selected_name} 주가 차트")

    from collector import load_stock_data
    from processor import calculate_indicators

    raw_data = load_stock_data()
    if selected_symbol in raw_data:
        df = calculate_indicators(raw_data[selected_symbol])

        fig = go.Figure()

        fig.add_trace(go.Candlestick(
            x=df.index,
            open=df["Open"],
            high=df["High"],
            low=df["Low"],
            close=df["Close"],
            name="주가",
            increasing_line_color="#26a69a",
            decreasing_line_color="#ef5350",
        ))

        fig.add_trace(go.Scatter(
            x=df.index, y=df["MA5"],
            name="MA5", line=dict(color="#FFA726", width=1),
        ))
        fig.add_trace(go.Scatter(
            x=df.index, y=df["MA20"],
            name="MA20", line=dict(color="#42A5F5", width=1.5),
        ))
        fig.add_trace(go.Scatter(
            x=df.index, y=df["MA60"],
            name="MA60", line=dict(color="#AB47BC", width=1.5),
        ))

        fig.add_trace(go.Scatter(
            x=df.index, y=df["BB_upper"],
            name="볼린저 상단", line=dict(color="gray", width=1, dash="dot"),
        ))
        fig.add_trace(go.Scatter(
            x=df.index, y=df["BB_lower"],
            name="볼린저 하단", line=dict(color="gray", width=1, dash="dot"),
            fill="tonexty", fillcolor="rgba(128,128,128,0.05)",
        ))

        fig.update_layout(
            height=500,
            xaxis_rangeslider_visible=False,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(l=0, r=0, t=40, b=0),
        )
        st.plotly_chart(fig, use_container_width=True)

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("RSI (14일)")
            df_rsi = df[["RSI"]].dropna()
            fig_rsi = go.Figure()
            fig_rsi.add_trace(go.Scatter(x=df_rsi.index, y=df_rsi["RSI"], name="RSI", line=dict(color="#42A5F5")))
            fig_rsi.add_hline(y=70, line_dash="dash", line_color="red", annotation_text="과매수(70)")
            fig_rsi.add_hline(y=30, line_dash="dash", line_color="green", annotation_text="과매도(30)")
            fig_rsi.update_layout(height=250, margin=dict(l=0, r=0, t=20, b=0), yaxis=dict(range=[0, 100]))
            st.plotly_chart(fig_rsi, use_container_width=True)

        with col2:
            st.subheader("거래량")
            fig_vol = go.Figure()
            fig_vol.add_trace(go.Bar(x=df.index, y=df["Volume"], name="거래량", marker_color="#78909C"))
            fig_vol.add_trace(go.Scatter(x=df.index, y=df["Volume_MA20"], name="20일 평균", line=dict(color="#FFA726")))
            fig_vol.update_layout(height=250, margin=dict(l=0, r=0, t=20, b=0))
            st.plotly_chart(fig_vol, use_container_width=True)
    else:
        st.warning("데이터가 없습니다. `python src/collector.py`를 먼저 실행하세요.")


# ── 탭 2: 펀더멘털 ───────────────────────────

with tab_fundamental:
    st.subheader(f"{selected_name} 펀더멘털 분석")

    f = api_get(f"/fundamentals/{selected_symbol}")

    if f:
        def fmt_pct(v):
            if v is None:
                return "N/A"
            return f"{v*100:.1f}%"

        def fmt_num(v, decimals=2):
            if v is None:
                return "N/A"
            return f"{v:,.{decimals}f}"

        def fmt_cap(v):
            if v is None:
                return "N/A"
            if v >= 1e12:
                return f"{v/1e12:.2f}조 달러"
            if v >= 1e9:
                return f"{v/1e9:.1f}십억 달러"
            return f"{v:,.0f}"

        # ── 시장 정보 ──
        st.markdown("#### 시장 정보")
        c1, c2, c3 = st.columns(3)
        c1.metric("시가총액", fmt_cap(f.get("market_cap")))
        c2.metric("베타 (변동성)", fmt_num(f.get("beta")))
        c3.metric("배당 수익률", fmt_pct(f.get("dividend_yield")))

        # 52주 범위 바
        high52 = f.get("week52_high")
        low52  = f.get("week52_low")
        prices_raw = load_stock_data() if True else {}

        from collector import load_stock_data as _load
        _raw = _load()
        if selected_symbol in _raw and high52 and low52:
            current_price = float(_raw[selected_symbol].iloc[-1]["Close"])
            pct = (current_price - low52) / (high52 - low52) * 100
            st.markdown(f"**52주 가격 범위** &nbsp;&nbsp; 저가 `{fmt_num(low52)}` — 현재가 `{fmt_num(current_price)}` — 고가 `{fmt_num(high52)}`")
            st.progress(min(max(int(pct), 0), 100))

        st.markdown("---")

        # ── 밸류에이션 ──
        st.markdown("#### 밸류에이션")
        c1, c2, c3, c4 = st.columns(4)
        per = f.get("per")
        per_label = "PER (Trailing)"
        per_delta = None
        if per is not None:
            if per < 15:
                per_delta = "저평가"
            elif per > 40:
                per_delta = "고평가"
            else:
                per_delta = "적정"
        c1.metric(per_label, fmt_num(per), per_delta)
        c2.metric("PER (Forward)", fmt_num(f.get("forward_per")))
        c3.metric("PBR", fmt_num(f.get("pbr")))
        c4.metric("EPS", fmt_num(f.get("eps")))

        st.markdown("---")

        # ── 수익성 ──
        st.markdown("#### 수익성")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("ROE", fmt_pct(f.get("roe")))
        c2.metric("매출총이익률", fmt_pct(f.get("gross_margin")))
        c3.metric("영업이익률", fmt_pct(f.get("operating_margin")))
        c4.metric("순이익률", fmt_pct(f.get("profit_margin")))

        st.markdown("---")

        # ── 성장성 ──
        st.markdown("#### 성장성 (YoY)")
        c1, c2 = st.columns(2)
        rev_growth = f.get("revenue_growth")
        earn_growth = f.get("earnings_growth")
        c1.metric(
            "매출 성장률",
            fmt_pct(rev_growth),
            "성장" if rev_growth and rev_growth > 0 else ("역성장" if rev_growth else None),
        )
        c2.metric(
            "이익 성장률",
            fmt_pct(earn_growth),
            "성장" if earn_growth and earn_growth > 0 else ("역성장" if earn_growth else None),
        )

        # 성장률 막대 차트
        growth_labels = ["매출 성장률", "이익 성장률"]
        growth_values = [
            (rev_growth or 0) * 100,
            (earn_growth or 0) * 100,
        ]
        fig_growth = go.Figure(go.Bar(
            x=growth_labels,
            y=growth_values,
            marker_color=["#26a69a" if v >= 0 else "#ef5350" for v in growth_values],
            text=[f"{v:.1f}%" for v in growth_values],
            textposition="outside",
        ))
        fig_growth.update_layout(
            height=280,
            margin=dict(l=0, r=0, t=20, b=0),
            yaxis_title="%",
        )
        st.plotly_chart(fig_growth, use_container_width=True)

        st.markdown("---")

        # ── 재무 안정성 ──
        st.markdown("#### 재무 안정성")
        c1, c2 = st.columns(2)
        de = f.get("debt_to_equity")
        cr = f.get("current_ratio")
        de_delta = None
        if de is not None:
            de_delta = "안정" if de < 100 else "주의"
        cr_delta = None
        if cr is not None:
            cr_delta = "양호" if cr >= 1.5 else "주의"
        c1.metric("부채비율 (D/E)", fmt_num(de), de_delta)
        c2.metric("유동비율", fmt_num(cr), cr_delta)


# ── 탭 3: 뉴스 ───────────────────────────────

with tab_news:
    st.subheader(f"{selected_name} 최신 뉴스")

    news_data = api_get(f"/news/{selected_symbol}")

    if news_data and news_data.get("news"):
        news_list = news_data["news"]
        valid_news = [n for n in news_list if "error" not in n and n.get("title")]

        if not valid_news:
            st.info("현재 수집된 뉴스가 없습니다.")
        else:
            st.markdown(f"**{len(valid_news)}건** 뉴스 수집됨")
            st.markdown("---")

            for news in valid_news:
                sent = news.get("sentiment", {})
                sent_label = sent.get("label", "중립")
                sent_icon  = {"긍정": "🟢", "부정": "🔴", "중립": "⚪"}.get(sent_label, "⚪")

                with st.container():
                    col1, col2, col3 = st.columns([4, 1, 1])
                    with col1:
                        if news.get("link"):
                            st.markdown(f"**[{news['title']}]({news['link']})**")
                        else:
                            st.markdown(f"**{news['title']}**")
                    with col2:
                        st.markdown(f"{sent_icon} **{sent_label}**")
                    with col3:
                        st.caption(news.get("pub_time", ""))

                    st.caption(f"출처: {news.get('publisher', 'N/A')}")
                    st.markdown("---")
    else:
        st.info("뉴스를 불러올 수 없습니다.")


# ── 탭 4: 비교 분석 ────────────────────────────

with tab_compare:
    st.subheader("반도체 섹터 비교 분석")

    compare_data = api_get("/compare")

    if compare_data and compare_data.get("performance"):
        perf = compare_data["performance"]

        # ── 수익률 히트맵 ──
        st.markdown("#### 기간별 수익률 (%)")

        names   = [p["name"] for p in perf]
        periods = ["1주", "1개월", "3개월", "1년"]
        keys    = ["return_1w", "return_1m", "return_3m", "return_1y"]

        z    = [[p.get(k) or 0 for k in keys] for p in perf]
        text = [[f"{p.get(k):+.1f}%" if p.get(k) is not None else "N/A" for k in keys] for p in perf]

        fig_heat = go.Figure(go.Heatmap(
            z=z, x=periods, y=names,
            text=text, texttemplate="%{text}",
            colorscale="RdYlGn", zmid=0,
            colorbar=dict(title="%"),
        ))
        fig_heat.update_layout(height=320, margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(fig_heat, use_container_width=True)

        st.markdown("---")

        # ── 상관관계 매트릭스 ──
        corr_data = compare_data.get("correlation", {})
        if corr_data:
            st.markdown("#### 종목 간 상관관계")
            st.caption("1에 가까울수록 함께 움직이는 경향이 강합니다.")

            sym_keys  = list(corr_data.keys())
            sym_names = [SYMBOLS.get(s, s) for s in sym_keys]
            z_corr    = [[corr_data[s1].get(s2) or 0 for s2 in sym_keys] for s1 in sym_keys]
            text_corr = [
                [f"{corr_data[s1].get(s2):.2f}" if corr_data[s1].get(s2) is not None else "" for s2 in sym_keys]
                for s1 in sym_keys
            ]

            fig_corr = go.Figure(go.Heatmap(
                z=z_corr, x=sym_names, y=sym_names,
                text=text_corr, texttemplate="%{text}",
                colorscale="Blues", zmin=0, zmax=1,
                colorbar=dict(title="상관계수"),
            ))
            fig_corr.update_layout(height=360, margin=dict(l=0, r=0, t=10, b=0))
            st.plotly_chart(fig_corr, use_container_width=True)
    else:
        st.info("데이터를 불러올 수 없습니다. 사이드바에서 🔄 데이터 수집을 먼저 실행하세요.")


# ── 탭 4: AI 분석 ──────────────────────────────

with tab_ai:
    st.subheader(f"{selected_name} AI 종합 분석")

    if run_analysis:
        with st.spinner("AI가 분석 중입니다... (최대 3분 소요, 비율 제한 시 자동 재시도)"):
            strategy_data = api_get(f"/strategy/{selected_symbol}", timeout=300)

        if strategy_data:
            col1, col2 = st.columns(2)

            with col1:
                css = signal_color(strategy_data["signal"])
                st.markdown(
                    f'<div class="signal-box {css}">매매 신호<br>{strategy_data["signal"]}</div>',
                    unsafe_allow_html=True,
                )

            with col2:
                css = risk_color(strategy_data["risk"])
                st.markdown(
                    f'<div class="signal-box {css}">리스크 수준<br>{strategy_data["risk"]}</div>',
                    unsafe_allow_html=True,
                )

            st.markdown("---")
            st.subheader("트레이딩 전략")
            st.markdown(strategy_data["strategy"])

            st.session_state["last_analysis"] = strategy_data

    elif "last_analysis" in st.session_state and st.session_state["last_analysis"]["symbol"] == selected_symbol:
        strategy_data = st.session_state["last_analysis"]
        col1, col2 = st.columns(2)

        with col1:
            css = signal_color(strategy_data["signal"])
            st.markdown(
                f'<div class="signal-box {css}">매매 신호<br>{strategy_data["signal"]}</div>',
                unsafe_allow_html=True,
            )
        with col2:
            css = risk_color(strategy_data["risk"])
            st.markdown(
                f'<div class="signal-box {css}">리스크 수준<br>{strategy_data["risk"]}</div>',
                unsafe_allow_html=True,
            )

        st.markdown("---")
        st.subheader("트레이딩 전략")
        st.markdown(strategy_data["strategy"])

    else:
        st.info("왼쪽 사이드바에서 종목을 선택하고 **AI 분석 실행** 버튼을 클릭하세요.")

    # ── 30일 주가 예측 ──────────────────────────
    st.markdown("---")
    st.subheader("📊 30일 주가 예측")
    st.caption("⚠️ 과거 변동성 기반 통계 모델입니다. 실제 미래 가격을 보장하지 않습니다.")

    forecast_data = api_get(f"/forecast/{selected_symbol}")

    if forecast_data and "scenarios" in forecast_data:
        current = forecast_data["current_price"]
        st.markdown(
            f"**현재가** `{current:,.2f}` &nbsp;|&nbsp; "
            f"**예측 기간** {forecast_data['days']}일 &nbsp;|&nbsp; "
            f"**시뮬레이션** {forecast_data['simulations']:,}회"
        )
        st.markdown("")

        cols = st.columns(3)
        scenario_styles = [("buy", "📈"), ("hold", "➡️"), ("sell", "📉")]

        for col, scenario, (css, emoji) in zip(cols, forecast_data["scenarios"], scenario_styles):
            with col:
                sign = "+" if scenario["change_pct"] >= 0 else ""
                st.markdown(
                    f'<div class="signal-box {css}" style="font-size:1rem; padding:14px;">'
                    f'{emoji} <b>{scenario["label"]} 시나리오</b><br>'
                    f'<span style="font-size:1.6rem; font-weight:bold;">{scenario["price"]:,.2f}</span><br>'
                    f'<span>{sign}{scenario["change_pct"]}%</span><br>'
                    f'<small>확률 {scenario["probability"]}%</small>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

        if forecast_data.get("distribution"):
            dist = forecast_data["distribution"]
            fig_dist = go.Figure()
            fig_dist.add_trace(go.Histogram(
                x=dist,
                nbinsx=60,
                marker_color="#42A5F5",
                opacity=0.75,
            ))
            fig_dist.add_vline(
                x=current,
                line_dash="dash",
                line_color="orange",
                line_width=2,
                annotation_text=f"현재가 {current:,.2f}",
                annotation_position="top right",
            )
            fig_dist.update_layout(
                height=240,
                margin=dict(l=0, r=0, t=30, b=0),
                xaxis_title="30일 후 예상 가격",
                yaxis_title="빈도",
                showlegend=False,
            )
            st.plotly_chart(fig_dist, use_container_width=True)

    elif forecast_data and "error" in forecast_data:
        st.warning(forecast_data["error"])

    # ── 백테스팅 ───────────────────────────────
    st.markdown("---")
    st.subheader("📈 백테스팅 결과")
    st.caption("MA5/MA20 골든크로스 전략을 5년치 과거 데이터에 적용한 시뮬레이션입니다.")

    bt_data = api_get(f"/backtest/{selected_symbol}")

    if bt_data and "equity_curve" in bt_data:
        c1, c2, c3, c4 = st.columns(4)
        str_ret = bt_data["strategy_return"]
        bh_ret  = bt_data["buyhold_return"]
        diff    = round(str_ret - bh_ret, 1)
        c1.metric("전략 수익률", f"{str_ret:+.1f}%", f"매수보유 대비 {diff:+.1f}%")
        c2.metric("승률", f"{bt_data['win_rate']}%", f"총 {bt_data['total_trades']}회 거래")
        c3.metric("최대 낙폭", f"{bt_data['max_drawdown']:.1f}%")
        c4.metric("매수보유 수익률", f"{bh_ret:+.1f}%")

        eq = bt_data["equity_curve"]
        fig_bt = go.Figure()
        fig_bt.add_trace(go.Scatter(
            x=[e["date"] for e in eq], y=[e["strategy"] for e in eq],
            name="골든크로스 전략", line=dict(color="#42A5F5", width=2),
        ))
        fig_bt.add_trace(go.Scatter(
            x=[e["date"] for e in eq], y=[e["buy_hold"] for e in eq],
            name="매수보유", line=dict(color="#78909C", width=1.5, dash="dot"),
        ))
        fig_bt.add_hline(y=1.0, line_dash="dash", line_color="gray", line_width=0.8)
        fig_bt.update_layout(
            height=280,
            margin=dict(l=0, r=0, t=30, b=0),
            yaxis_title="누적 수익 배수 (시작=1)",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        st.plotly_chart(fig_bt, use_container_width=True)

    elif bt_data and "error" in bt_data:
        st.warning(bt_data["error"])


# ── 탭 3: 챗봇 ───────────────────────────────

with tab_chat:
    st.subheader("반도체 시장 AI 챗봇")
    st.markdown("반도체 주식에 관한 무엇이든 질문하세요.")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("질문을 입력하세요..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("답변 생성 중... (비율 제한 시 자동 재시도)"):
                result = api_post("/chat", {"message": prompt}, timeout=300)

            if result:
                answer = result.get("answer", "응답을 받지 못했습니다.")
                st.markdown(answer)
                st.session_state.messages.append({"role": "assistant", "content": answer})
