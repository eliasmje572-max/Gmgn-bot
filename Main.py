import os
import time
import json
import requests
from openai import OpenAI

# ==========================================
# KONFIGURATION
# ==========================================
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "DIN_OPENAI_API_KEY_HÄR")
TELEGRAM_BOT_TOKEN = "8652036515:AAGbRQafmDHgcCRAbF2JV75beaqF9GptdgM"
TELEGRAM_CHAT_ID = "8405852294"

CHECK_INTERVAL = 10    # Skanna var 10:e sekund
MAX_AGE_MINUTES = 15.0 # ÄNDRAT: Max 15 minuter gamla mynt

client = OpenAI(api_key=OPENAI_API_KEY)
seen_tokens = set()

# ==========================================
# 1. HÄMTA GMGN HOT SEARCHES & TRENDING
# ==========================================
def fetch_gmgn_hot_searches():
    # GMGN Trending API för Solana (Smart Money / Swaps / Trending)
    url = "https://gmgn.ai/defi/quotation/v1/rank/sol/wallets/5m?limit=40&orderby=swaps&direction=desc"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
        "Accept": "application/json"
    }

    try:
        response = requests.get(url, headers=headers, timeout=8)
        if response.status_code == 200:
            data = response.json()
            raw_tokens = data.get("data", {}).get("rank", [])
            parsed_tokens = []
            now_ts = time.time()
            
            for t in raw_tokens:
                created_at = t.get("creation_timestamp", now_ts)
                age_minutes = (now_ts - created_at) / 60.0
                
                # Filtrera på max 15 minuter
                if age_minutes <= MAX_AGE_MINUTES:
                    is_paid = t.get("is_paid", False) or t.get("has_socials", False)
                    is_circled = t.get("hot_level", 0) > 1 or t.get("swaps", 0) > 300
                    
                    parsed_tokens.append({
                        "address": t.get("address"),
                        "symbol": t.get("name", "Unknown"),
                        "ticker": t.get("symbol", "MEME"),
                        "liquidity": t.get("liquidity", 0),
                        "volume_5m": t.get("volume", 0),
                        "swaps_5m": t.get("swaps", 0),
                        "age_minutes": round(age_minutes, 1),
                        "is_paid": is_paid,
                        "is_circled": is_circled,
                        "gmgn_url": f"https://gmgn.ai/sol/token/{t.get('address')}"
                    })
            return parsed_tokens
    except Exception as e:
        print(f"GMGN Fetch Error: {e}")
    
    return []

# ==========================================
# 2. AI ANALYS & RARITETS-BEDÖMNING
# ==========================================
def analyze_coin_with_ai(token):
    prompt = f"""
Du är en elit memecoin-trader på Solana som letar efter nästa 100x gem på GMGN Hot Searches.
Utvärdera följande token (Ålder: {token['age_minutes']} min):

- Ticker: ${token['ticker']}
- Namn: {token['symbol']}
- Likviditet: ${token['liquidity']:,} - 5m Volym:${token['volume_5m']:,}
- 5m Swaps/Köp: {token['swaps_5m']}
- GMGN Paid/Socials: {token['is_paid']}
- GMGN High Hype (Circled): {token['is_circled']}

Bestäm om myntet har hög potential och ge det en raritet (COMMON, RARE, LEGENDARY):
- COMMON: Bra första tryck/swaps, nyligen startad (< 15 min).
- RARE: Stark volym/likviditet, har Paid badge/verifierat eller mycket aktiv köpvåg.
- LEGENDARY: Galen köpvåg, Paid/Circled, perfekt viral narrative (som gstock, meta-trend eller kändis-hype).

Svara BARA i giltigt JSON:
{{
  "is_good": true/false,
  "rarity": "COMMON" / "RARE" / "LEGENDARY",
  "narrative_score": 1-10,
  "analysis": "Kort motivering på svenska varför myntet är bra/dåligt."
}}
"""
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"AI Error: {e}")
        return None

# ==========================================
# 3. TELEGRAM NOTIS MED BILDER & RARITET
# ==========================================
def send_telegram_alert(token, ai_res):
    rarity = ai_res.get("rarity", "COMMON").upper()
    
    if rarity == "LEGENDARY":
        header = "🟡🟡 **LEGENDARY GMGN GEM FOUND** 🟡🟡"
        badge = "🔥 **STATUS: PAID & CIRCLED / ULTRA HYPE**"
    elif rarity == "RARE":
        header = "🔵🔵 **RARE GMGN GEM FOUND** 🔵🔵"
        badge = "⚡ **STATUS: HIGH VOLUME / PAID BADGE**"
    else:
        header = "🟢 **COMMON GMGN ALERT** 🟢"
        badge = "📊 **STATUS: EARLY MOMENTUM**"

    message = (
        f"{header}\n\n"
        f"💎 *Ticker:* `${token['ticker']}`\n"
        f"🏷 *Namn:* {token['symbol']}\n"
        f"⏱ *Ålder:* {token['age_minutes']} minuter gammal\n"
        f"⭐ *AI Score:* {ai_res.get('narrative_score')}/10\n"
        f"{badge}\n\n"
        f"💧 *Likviditet:* ${token['liquidity']:,}\n"
        f"📈 *5m Volym:* ${token['volume_5m']:,}\n"
        f"🔄 *5m Swaps:* {token['swaps_5m']}\n\n"
        f"🧠 *AI Analys:*\n_{ai_res.get('analysis')}_\n\n"
        f"📋 *Contract Address (Tryck för att kopiera):*\n"
        f"`{token['address']}`\n\n"
        f"🔗 [Öppna direkt på GMGN.ai]({token['gmgn_url']})"
    )
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    
    try:
        res = requests.post(url, json=payload, timeout=5)
        if res.status_code == 200:
            print(f"✅ [{rarity}] Notis skickad för ${token['ticker']}")
        else:
            print(f"❌ Telegram API Fel: {res.text}")
    except Exception as e:
        print(f"❌ Telegram Error: {e}")

# ==========================================
# 4. SKANNINGSLOOP
# ==========================================
def main():
    print("🚀 Boten skannar nu GMGN Hot Searches efter mynt < 15 minuter...")
    
    while True:
        tokens = fetch_gmgn_hot_searches()
        for t in tokens:
            addr = t["address"]
            if not addr or addr in seen_tokens:
                continue
            
            seen_tokens.add(addr)
            print(f"🔍 Utvärderar: ${t['ticker']} ({t['symbol']}) - {t['age_minutes']}m gammal")

            ai_eval = analyze_coin_with_ai(t)
            
            if ai_eval and ai_eval.get("is_good"):
                send_telegram_alert(t, ai_eval)
            else:
                reason = ai_eval.get("analysis") if ai_eval else "Svagt narrativ"
                print(f"❌ PASS: {reason}")

        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
