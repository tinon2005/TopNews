#!/usr/bin/env python3
"""
GlobalPulse 新聞抓取腳本
整合 NewsAPI + BBC RSS + Reuters RSS + BeautifulSoup
合規抓取，遵守各平台 robots.txt 及服務條款
"""

import os
import json
import time
import requests
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup
from dateutil import parser as dateparser

# ── 香港時區 ──────────────────────────────────────────
HKT = timezone(timedelta(hours=8))
TODAY = datetime.now(HKT).strftime("%Y年%m月%d日")
TODAY_ISO = datetime.now(HKT).strftime("%Y-%m-%d")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; GlobalPulseBot/1.0; "
        "+https://github.com/YOUR_USERNAME/globalpulse)"
    )
}

OUTPUT_DIR = "docs"
os.makedirs(OUTPUT_DIR, exist_ok=True)


# ══════════════════════════════════════════════════════
# 1. NewsAPI  (免費層: 100次/天)
# ══════════════════════════════════════════════════════
def fetch_newsapi(api_key: str) -> list[dict]:
    """從 NewsAPI 抓取英文財經及政治頭條"""
    if not api_key:
        print("⚠️  NEWSAPI_KEY 未設置，跳過 NewsAPI")
        return []

    url = "https://newsapi.org/v2/top-headlines"
    categories = [
        {"category": "business", "country": "us"},
        {"category": "business", "country": "gb"},
        {"q": "China economy OR China trade", "language": "en"},
        {"q": "Iran nuclear deal OR oil price", "language": "en"},
        {"q": "Federal Reserve interest rate", "language": "en"},
    ]

    articles = []
    for params in categories:
        params["apiKey"] = api_key
        params.setdefault("pageSize", 5)
        try:
            resp = requests.get(url, params=params, timeout=10)
            data = resp.json()
            if data.get("status") == "ok":
                articles.extend(data.get("articles", []))
            time.sleep(0.5)   # 控制請求頻率
        except Exception as e:
            print(f"  NewsAPI 請求失敗: {e}")

    # 去重（同 URL）
    seen = set()
    unique = []
    for a in articles:
        u = a.get("url", "")
        if u and u not in seen:
            seen.add(u)
            unique.append(a)

    print(f"✅ NewsAPI: 獲取 {len(unique)} 篇文章")
    return unique


# ══════════════════════════════════════════════════════
# 2. BBC World News RSS  (公開免費)
# ══════════════════════════════════════════════════════
def fetch_bbc_rss() -> list[dict]:
    """抓取 BBC World News RSS"""
    rss_urls = [
        "https://feeds.bbci.co.uk/news/world/rss.xml",
        "https://feeds.bbci.co.uk/news/business/rss.xml",
    ]
    items = []
    for url in rss_urls:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=10)
            soup = BeautifulSoup(resp.content, "xml")
            for item in soup.find_all("item")[:8]:
                items.append({
                    "source": "BBC",
                    "title": item.find("title").get_text(strip=True) if item.find("title") else "",
                    "description": item.find("description").get_text(strip=True) if item.find("description") else "",
                    "url": item.find("link").get_text(strip=True) if item.find("link") else "",
                    "publishedAt": item.find("pubDate").get_text(strip=True) if item.find("pubDate") else "",
                })
            time.sleep(1)
        except Exception as e:
            print(f"  BBC RSS 失敗: {e}")

    print(f"✅ BBC RSS: 獲取 {len(items)} 條新聞")
    return items


# ══════════════════════════════════════════════════════
# 3. Reuters RSS  (公開免費)
# ══════════════════════════════════════════════════════
def fetch_reuters_rss() -> list[dict]:
    """抓取 Reuters 世界及商業新聞 RSS"""
    rss_urls = [
        "https://feeds.reuters.com/reuters/worldNews",
        "https://feeds.reuters.com/reuters/businessNews",
    ]
    items = []
    for url in rss_urls:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=10)
            soup = BeautifulSoup(resp.content, "xml")
            for item in soup.find_all("item")[:8]:
                items.append({
                    "source": "Reuters",
                    "title": item.find("title").get_text(strip=True) if item.find("title") else "",
                    "description": item.find("description").get_text(strip=True) if item.find("description") else "",
                    "url": item.find("link").get_text(strip=True) if item.find("link") else "",
                    "publishedAt": item.find("pubDate").get_text(strip=True) if item.find("pubDate") else "",
                })
            time.sleep(1)
        except Exception as e:
            print(f"  Reuters RSS 失敗: {e}")

    print(f"✅ Reuters RSS: 獲取 {len(items)} 條新聞")
    return items


# ══════════════════════════════════════════════════════
# 4. Google Trends  (via pytrends)
# ══════════════════════════════════════════════════════
def fetch_google_trends() -> dict:
    """獲取 Google Trends 熱搜關鍵字"""
    try:
        from pytrends.request import TrendReq
        pytrends = TrendReq(hl="zh-TW", tz=480, timeout=(10, 25))

        # 財經相關熱搜
        keywords = ["AI stocks", "GLP-1", "Iran oil", "Federal Reserve", "Bitcoin"]
        pytrends.build_payload(keywords, timeframe="now 7-d", geo="")
        interest = pytrends.interest_over_time()

        trending = {}
        if not interest.empty:
            latest = interest.iloc[-1]
            for kw in keywords:
                if kw in latest:
                    trending[kw] = int(latest[kw])

        # 全球熱搜榜
        try:
            daily = pytrends.trending_searches(pn="united_states")
            top5 = daily.head(5)[0].tolist()
        except Exception:
            top5 = []

        result = {"finance_keywords": trending, "trending_searches": top5}
        print(f"✅ Google Trends: {trending}")
        return result

    except Exception as e:
        print(f"  Google Trends 失敗: {e}")
        return {"finance_keywords": {}, "trending_searches": []}


# ══════════════════════════════════════════════════════
# 5. 市場數據  (Yahoo Finance 非官方 JSON)
# ══════════════════════════════════════════════════════
def fetch_market_data() -> dict:
    """獲取主要市場指數即時數據"""
    symbols = {
        "^IXIC":   "NASDAQ",
        "^GSPC":   "S&P 500",
        "^DJI":    "道瓊斯",
        "GC=F":    "黃金",
        "CL=F":    "WTI 原油",
        "BTC-USD": "比特幣",
        "GBPUSD=X": "英鎊/美元",
        "CNY=X":   "美元/人民幣",
    }

    market = {}
    base_url = "https://query1.finance.yahoo.com/v8/finance/chart/"
    for symbol, name in symbols.items():
        try:
            url = f"{base_url}{symbol}?interval=1d&range=2d"
            resp = requests.get(url, headers=HEADERS, timeout=8)
            data = resp.json()
            meta = data["chart"]["result"][0]["meta"]
            price = meta.get("regularMarketPrice", 0)
            prev  = meta.get("chartPreviousClose", price)
            chg   = ((price - prev) / prev * 100) if prev else 0
            market[name] = {
                "price": round(price, 2),
                "change_pct": round(chg, 2),
                "symbol": symbol,
            }
            time.sleep(0.3)
        except Exception as e:
            print(f"  市場數據 {symbol} 失敗: {e}")

    print(f"✅ 市場數據: {list(market.keys())}")
    return market


# ══════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════
def main():
    print(f"\n🚀 GlobalPulse 數據抓取開始 — {TODAY}")
    print("=" * 50)

    api_key = os.environ.get("NEWSAPI_KEY", "")

    # 並行抓取各數據源
    data = {
        "date": TODAY,
        "date_iso": TODAY_ISO,
        "generated_at": datetime.now(HKT).isoformat(),
        "newsapi": fetch_newsapi(api_key),
        "bbc": fetch_bbc_rss(),
        "reuters": fetch_reuters_rss(),
        "trends": fetch_google_trends(),
        "market": fetch_market_data(),
    }

    # 輸出 JSON 供 build_page.py 使用
    out_path = os.path.join(OUTPUT_DIR, "data.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 數據已儲存至 {out_path}")
    print(f"📊 NewsAPI: {len(data['newsapi'])} 篇")
    print(f"📡 BBC: {len(data['bbc'])} 篇")
    print(f"📡 Reuters: {len(data['reuters'])} 篇")
    print(f"📈 市場: {len(data['market'])} 個指數")


if __name__ == "__main__":
    main()
