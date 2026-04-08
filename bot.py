import sys
import random
import requests
import yfinance as yf
import os
from bs4 import BeautifulSoup

period = sys.argv[1] if len(sys.argv) > 1 else "Market Update"

def send_groupme_message(text):
    bot_id = os.environ["GROUPME_BOT_ID"]
    url = "https://api.groupme.com/v3/bots/post"
    payload = {"bot_id": bot_id, "text": text}
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 201:
            print("✅ Message sent to GroupMe")
        else:
            print(f"❌ Error: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"❌ Request failed: {e}")

# === Get S&P 500 tickers without pandas/lxml ===
def get_sp500_tickers():
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    headers = {"User-Agent": "Mozilla/5.0"}
    resp = requests.get(url, headers=headers)
    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.find("table", {"class": "wikitable"})
    tickers = []
    for row in table.find_all("tr")[1:]:  # skip header
        cols = row.find_all("td")
        if len(cols) > 0:
            ticker = cols[0].text.strip()
            tickers.append(ticker)
    return tickers[:200]  # limit for speed

# === Stock selection ===
def get_candidates():
    tickers = get_sp500_tickers()
    extra = ["AMC", "GME", "RIVN", "SOFI", "PLTR", "COIN"]
    tickers = list(dict.fromkeys(tickers + extra))

    tickers_obj = yf.Tickers(" ".join(tickers))
    candidates = []

    for t in tickers_obj.tickers:
        try:
            info = tickers_obj.tickers[t].info
            fast = tickers_obj.tickers[t].fast_info
            current = fast.get("lastPrice") or info.get("currentPrice")
            high_52 = info.get("fiftyTwoWeekHigh")
            low_52 = info.get("fiftyTwoWeekLow")
            beta = info.get("beta")
            market_cap = info.get("marketCap")
            name = info.get("longName") or t

            if not all([current, high_52, low_52, current > low_52]):
                continue

            upside = (high_52 - current) / current
            downside = (current - low_52) / current
            rr = round(upside / downside, 1) if downside > 0 else 0

            if rr >= 5.0:
                candidates.append({
                    "ticker": t,
                    "name": name,
                    "price": round(current, 2),
                    "rr": rr,
                    "beta": beta or 1.0,
                    "market_cap": market_cap or 0,
                    "upside_pct": round(upside * 100, 1)
                })
        except:
            continue
    return candidates

candidates = get_candidates()

if not candidates:
    msg = f"⚠️ {period} – No 1:5 RR setups found today\nthis is just a suggestion use at your own risk"
    send_groupme_message(msg)
    sys.exit(0)

low_risk = [c for c in candidates if c["market_cap"] > 100_000_000_000 and c["beta"] < 1.2]
high_risk = [c for c in candidates if c["market_cap"] < 100_000_000_000 or c["beta"] > 1.5]

low_pick = max(low_risk, key=lambda x: x["rr"]) if low_risk else max(candidates, key=lambda x: x["rr"])
high_pick = max(high_risk, key=lambda x: x["rr"]) if high_risk else random.choice(candidates)

# Global market context
try:
    market = yf.Ticker("SPY")
    global_news = market.news[:3]
    context_lines = [f"- {item.get('title', '')}" for item in global_news]
    context = "\n".join(context_lines)
except:
    context = "Market news temporarily unavailable"

msg = f"""{period} – 1:5 RR Picks

🌍 Global Market Context:
{context}

🟢 Low Risk
{low_pick['name']} ({low_pick['ticker']})
${low_pick['price']} • Upside {low_pick['upside_pct']}% • RR 1:{low_pick['rr']}

🔴 High Risk / Reward
{high_pick['name']} ({high_pick['ticker']})
${high_pick['price']} • Upside {high_pick['upside_pct']}% • RR 1:{high_pick['rr']}

this is just a suggestion use at your own risk"""

send_groupme_message(msg)
print(f"✅ Sent {period} message")
