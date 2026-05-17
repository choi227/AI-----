import chromadb
import os
from processor import process_all, summarize_for_llm, calculate_indicators
from collector import load_stock_data, get_news, SYMBOLS

DB_DIR = os.path.join(os.path.dirname(__file__), "..", "database")


def get_collection():
    """ChromaDB 컬렉션 연결"""
    client = chromadb.PersistentClient(path=DB_DIR)
    collection = client.get_or_create_collection(
        name="semiconductor_market",
        metadata={"description": "반도체 시장 분석 데이터"}
    )
    return collection


def store_market_summaries():
    """전체 종목 분석 요약을 Vector DB에 저장"""
    collection = get_collection()

    data = load_stock_data()
    stored_count = 0

    print("[Vector DB 저장 시작]")

    for symbol, df in data.items():
        df_with_indicators = calculate_indicators(df)
        summary = summarize_for_llm(symbol, df_with_indicators)

        date_str = df_with_indicators.index[-1].strftime("%Y-%m-%d")
        doc_id = f"{symbol}_{date_str}"

        collection.upsert(
            documents=[summary],
            ids=[doc_id],
            metadatas=[{
                "symbol": symbol,
                "name": SYMBOLS.get(symbol, symbol),
                "date": date_str,
                "type": "market_summary"
            }]
        )

        stored_count += 1
        print(f"  [OK] {SYMBOLS.get(symbol, symbol)} ({symbol}) - {date_str}")

    # 뉴스도 함께 저장
    news_count = store_news_all()
    stored_count += news_count

    print(f"\n[완료] 총 {stored_count}개 문서 저장 (시장요약 + 뉴스)")
    return stored_count


def store_news_all() -> int:
    """전체 종목 최신 뉴스를 Vector DB에 저장"""
    collection = get_collection()
    stored_count = 0

    print("\n[뉴스 저장 시작]")

    for symbol in SYMBOLS:
        news_list = get_news(symbol, max_items=10)

        for i, news in enumerate(news_list):
            if "error" in news or not news.get("title"):
                continue

            doc_id  = f"news_{symbol}_{i}"
            content = (
                f"[뉴스] {SYMBOLS.get(symbol, symbol)} ({symbol})\n"
                f"제목: {news['title']}\n"
                f"출처: {news['publisher']}\n"
                f"시간: {news['pub_time']}"
            )

            collection.upsert(
                documents=[content],
                ids=[doc_id],
                metadatas=[{
                    "symbol":    symbol,
                    "name":      SYMBOLS.get(symbol, symbol),
                    "type":      "news",
                    "pub_time":  news["pub_time"],
                    "publisher": news["publisher"],
                    "link":      news["link"],
                }]
            )
            stored_count += 1

        if news_list and "error" not in news_list[0]:
            print(f"  [OK] {SYMBOLS.get(symbol, symbol)} ({symbol}) - {len(news_list)}건")

    return stored_count


def search_similar(query: str, n_results: int = 3) -> list[dict]:
    """
    쿼리와 관련된 시장 분석 문서 검색
    예: "RSI 과매수 구간인 종목" 검색 시 관련 문서 반환
    """
    collection = get_collection()

    total = collection.count()
    if total == 0:
        return []

    results = collection.query(
        query_texts=[query],
        n_results=min(n_results, total)
    )

    documents = []
    for i in range(len(results["ids"][0])):
        documents.append({
            "id": results["ids"][0][i],
            "content": results["documents"][0][i],
            "metadata": results["metadatas"][0][i],
        })

    return documents


def get_market_context(query: str) -> str:
    """AI 에이전트에게 넘길 시장 컨텍스트 생성"""
    docs = search_similar(query, n_results=3)

    if not docs:
        return "관련 시장 데이터를 찾을 수 없습니다."

    context = f"[관련 시장 데이터 - '{query}' 검색 결과]\n\n"
    for i, doc in enumerate(docs, 1):
        context += f"--- 참고 {i}: {doc['metadata']['name']} ({doc['metadata']['symbol']}) ---\n"
        context += doc["content"]
        context += "\n\n"

    return context.strip()


if __name__ == "__main__":
    # 데이터 저장
    store_market_summaries()

    # 검색 테스트
    print("\n[검색 테스트]")
    print("=" * 50)

    queries = [
        "RSI 과매수 구간 종목",
        "하락 추세인 반도체 종목",
        "거래량 급증 종목",
    ]

    for query in queries:
        print(f"\n검색어: '{query}'")
        print("-" * 40)
        docs = search_similar(query, n_results=2)
        for doc in docs:
            print(f"  -> {doc['metadata']['name']} ({doc['metadata']['symbol']})")
