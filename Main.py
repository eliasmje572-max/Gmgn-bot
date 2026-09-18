import os
import time
import threading
import requests
from flask import Flask

# ==========================================
# FLASK WEBB SERVER (FÖR GRATIS RENDER)
# ==========================================
app = Flask(__name__)

@app.route('/')
def home():
    return "GMGN Bot is running!"

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# ==========================================
# KONFIGURATION
# ==========================================
TELEGRAM_BOT_TOKEN = "8652036515:AAGbRQafmDHgcCRAbF2JV75beaqF9GptdgM"
TELEGRAM_CHAT_ID = "8405852294"

CHECK_INTERVAL = 10
MAX_AGE_MINUTES = 15.0

seen_tokens = set()

# ==========================================
# 1. HÄMTA GMGN HOT SEARCHES
# ==========================================
def fetch_gmgn_hot_searches():
    url = "https://gmgn.ai/defi/quotation/v1/rank/sol/wallets/5m?limit=40&orderby=swaps&direction=desc"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
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
                
                if age_minutes <= MAX_AGE_MINUTES:
                    is_paid = t.get("is_paid", False) or t.get("has_socials", False)
                    swaps = t.get("swaps", 0)
                    volume = t.get("volume", 0)
                    liquidity = t.get("liquidity", 0)
                    is_circled = t.get("hot_level", 0) > 1 or swaps > 300
                    
                    parsed_tokens.append({
                        "address": t.get("address"),
                        "symbol": t.get("name", "Unknown"),
                        "ticker": t.get("symbol", "MEME"),
                        "liquidity": liquidity,
                        "volume_5m": volume,
                        "swaps_5m": swaps,
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
# 2. EVALUATE RARITY (UTAN AI)
# ==========================================
def evaluate_coin(token):
    # Minimum-krav för att skicka notis överhuvudtaget
    if token["liquidity"] < 1500 or token["swaps_5m"] < 30:
        return None

    # Bestäm raritet baserat på GMGN-data
    if token["is_paid"] and token["is_circled"] and token["swaps_5m"] > 250:
        rarity = "LEGENDARY"
        score = "10/10"
        reason = "Galen köpvåg! Både Paid status och Circled/High Hype på GMGN."
    elif token["is_paid"] or token["volume_5m"] > 15000:
        rarity = "RARE"
        score = "8/10"
        reason = "Stark volym och bekräftade socials/Paid badge på GMGN."
    else:
        rarity = "COMMON"
        score = "6/10"
        reason = "Tidigt momentum med stabilt antal swaps på 5 minuter."

    return {
        "rarity": rarity,
        "score": score,
        "reason": reason
    }

# ==========================================
# 3. TELEGRAM ALERT
# ==========================================
def send_telegram_alert(token, eval_res):
    rarity = eval_res["rarity"]
    
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
        f"⭐ *Score:* {eval_res['score']}\n"
        f"{badge}\n\n"
        f"💧 *Likviditet:* ${token['liquidity']:,}\n"
        f"📈 *5m Volym:* ${token['volume_5m']:,}\n"
        f"🔄 *5m Swaps:* {token['swaps_5m']}\n\n"
        f"🧠 *Analys:*\n_{eval_res['reason']}_\n\n"
        f"📋 *Contract Address:*\n"
        f"`{token['address']}`\n\n"
        f"🔗 [Öppna på GMGN.ai]({token['gmgn_url']})"
    )
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"Telegram Error: {e}")

# ==========================================
# 4. SKANNER-LOOP
# ==========================================
def scanner_loop():
    print("🚀 Boten skannar GMGN (100% gratis läge)...")
    while True:
        tokens = fetch_gmgn_hot_searches()
        for t in tokens:
            addr = t["address"]
            if not addr or addr in seen_tokens:
                continue
            
            seen_tokens.add(addr)
            eval_res = evaluate_coin(t)
            
            if eval_res:
                send_telegram_alert(t, eval_res)

        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    t = threading.Thread(target=scanner_loop)
    t.daemon = True
    t.start()
    
    run_web_server()
