from google import genai
import os
import time
from dotenv import load_dotenv
from rag import get_market_context, store_market_summaries
from processor import calculate_indicators, summarize_for_llm
from collector import load_stock_data, SYMBOLS

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


def _ask_gemini(prompt: str, retries: int = 3) -> str:
    """Gemini API 호출 — 429 발생 시 최대 3회 재시도"""
    for attempt in range(retries):
        try:
            response = client.models.generate_content(
                model="gemini-flash-latest",
                contents=prompt,
            )
            return response.text.strip()
        except Exception as e:
            err = str(e)
            if "429" in err and attempt < retries - 1:
                wait = 60 * (attempt + 1)  # 60초, 120초 순으로 대기
                print(f"[429 Rate Limit] {wait}초 대기 후 재시도 ({attempt + 1}/{retries - 1})")
                time.sleep(wait)
            else:
                return f"[AI 응답 오류] {e}"


# ──────────────────────────────────────────────
# Agent 1: 시장 진입 신호 판단
# ──────────────────────────────────────────────
def signal_agent(symbol: str) -> dict:
    """
    매수 / 매도 / 관망 신호를 판단하는 에이전트
    """
    data = load_stock_data()
    if symbol not in data:
        return {"symbol": symbol, "signal": "데이터 없음", "reason": ""}

    df = calculate_indicators(data[symbol])
    market_summary = summarize_for_llm(symbol, df)
    context = get_market_context(f"{SYMBOLS.get(symbol, symbol)} 매수 매도 신호")

    prompt = f"""
당신은 반도체 주식 전문 트레이딩 AI입니다.
아래 시장 데이터를 분석해서 {SYMBOLS.get(symbol, symbol)} ({symbol})의 매매 신호를 판단하세요.

[현재 시장 데이터]
{market_summary}

[참고: 관련 종목 시장 상황]
{context}

다음 형식으로 답변하세요:
신호: [매수 / 매도 / 관망] 중 하나만
근거: 2~3줄로 핵심 이유 설명
""".strip()

    response = _ask_gemini(prompt)

    signal = "관망"
    reason = response

    for line in response.splitlines():
        if line.startswith("신호:"):
            signal_text = line.replace("신호:", "").strip()
            if "매수" in signal_text:
                signal = "매수"
            elif "매도" in signal_text:
                signal = "매도"
            else:
                signal = "관망"
        elif line.startswith("근거:"):
            reason = line.replace("근거:", "").strip()

    return {
        "symbol": symbol,
        "name": SYMBOLS.get(symbol, symbol),
        "signal": signal,
        "reason": reason,
        "raw": response,
    }


# ──────────────────────────────────────────────
# Agent 2: 리스크 감지
# ──────────────────────────────────────────────
def risk_agent(symbol: str) -> dict:
    """
    투자 리스크 수준을 판단하는 에이전트
    """
    data = load_stock_data()
    if symbol not in data:
        return {"symbol": symbol, "risk": "알 수 없음", "reason": ""}

    df = calculate_indicators(data[symbol])
    market_summary = summarize_for_llm(symbol, df)

    prompt = f"""
당신은 반도체 주식 리스크 분석 전문가입니다.
아래 데이터를 보고 {SYMBOLS.get(symbol, symbol)} ({symbol})의 현재 투자 리스크를 평가하세요.

[시장 데이터]
{market_summary}

다음 형식으로 답변하세요:
리스크: [낮음 / 중간 / 높음] 중 하나만
근거: 2~3줄로 핵심 이유 설명
""".strip()

    response = _ask_gemini(prompt)

    risk = "중간"
    reason = response

    for line in response.splitlines():
        if line.startswith("리스크:"):
            risk_text = line.replace("리스크:", "").strip()
            if "낮음" in risk_text:
                risk = "낮음"
            elif "높음" in risk_text:
                risk = "높음"
            else:
                risk = "중간"
        elif line.startswith("근거:"):
            reason = line.replace("근거:", "").strip()

    return {
        "symbol": symbol,
        "name": SYMBOLS.get(symbol, symbol),
        "risk": risk,
        "reason": reason,
        "raw": response,
    }


# ──────────────────────────────────────────────
# Agent 3: 트레이딩 전략 추천 (종합)
# ──────────────────────────────────────────────
def strategy_agent(symbol: str) -> dict:
    """
    Signal + Risk 결과를 종합해 최종 트레이딩 전략을 추천하는 에이전트
    """
    signal_result   = signal_agent(symbol)
    risk_result     = risk_agent(symbol)
    context         = get_market_context(f"{SYMBOLS.get(symbol, symbol)} 트레이딩 전략")

    prompt = f"""
당신은 반도체 섹터 전문 트레이딩 전략가입니다.
아래 분석 결과를 종합해서 {SYMBOLS.get(symbol, symbol)} ({symbol})에 대한 구체적인 트레이딩 전략을 제안하세요.

[매매 신호 분석 결과]
신호: {signal_result['signal']}
근거: {signal_result['reason']}

[리스크 분석 결과]
리스크: {risk_result['risk']}
근거: {risk_result['reason']}

[참고: 관련 시장 데이터]
{context}

다음 형식으로 답변하세요:
전략: 한 줄 요약 (예: 분할 매수 후 단기 보유)
행동: 구체적인 행동 방안 3가지를 번호로
주의: 주의해야 할 리스크 1가지
""".strip()

    response = _ask_gemini(prompt)

    return {
        "symbol": symbol,
        "name": SYMBOLS.get(symbol, symbol),
        "signal": signal_result["signal"],
        "risk": risk_result["risk"],
        "strategy": response,
    }


# ──────────────────────────────────────────────
# 챗봇: 자유 질의응답
# ──────────────────────────────────────────────
def chat_agent(user_message: str) -> str:
    """
    트레이더의 자유 질문에 답하는 챗봇 에이전트
    """
    context = get_market_context(user_message)

    prompt = f"""
당신은 반도체 주식 시장 전문 AI 어시스턴트입니다.
트레이더의 질문에 시장 데이터를 바탕으로 명확하고 실용적으로 답변하세요.

[참고: 관련 시장 데이터]
{context}

[트레이더 질문]
{user_message}

3~5줄 이내로 핵심만 답변하세요.
""".strip()

    return _ask_gemini(prompt)


if __name__ == "__main__":
    print("[Vector DB 최신화 중...]")
    store_market_summaries()

    test_symbol = "NVDA"
    name = SYMBOLS[test_symbol]

    print(f"\n{'='*50}")
    print(f"[{name} ({test_symbol}) 종합 분석]")
    print("=" * 50)

    result = strategy_agent(test_symbol)
    print(f"매매 신호 : {result['signal']}")
    print(f"리스크    : {result['risk']}")
    print(f"\n[트레이딩 전략]")
    print(result["strategy"])

    print(f"\n{'='*50}")
    print("[챗봇 테스트]")
    print("=" * 50)
    question = "지금 반도체 섹터에서 가장 주목할 종목은 어디야?"
    print(f"질문: {question}")
    print(f"답변: {chat_agent(question)}")
