from flask import Flask
from collectors.solana_collector import get_solana_pairs
from database import init_db, save_market_snapshot
import os
import requests
import time

app = Flask(__name__)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def send_telegram(message):
    if not BOT_TOKEN or not CHAT_ID:
        print("Telegram env not set", flush=True)
        return

    requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={
            "chat_id": CHAT_ID,
            "text": message,
            "disable_web_page_preview": True
        },
        timeout=15
    )


def safe_float(value, default=0):
    try:
        if value is None:
            return default
        return float(value)
    except:
        return default


def classify_pair(pair):
    liquidity = safe_float(pair.get("liquidity"))
    volume = safe_float(pair.get("volume_24h"))
    change = safe_float(pair.get("change_24h"))

    if liquidity == 0:
        return "🟡 مبكر جداً / Pump.fun بدون سيولة"

    if liquidity < 5000:
        return "🔴 سيولة ضعيفة جداً"

    if change < -50:
        return "🔴 انهيار قوي"

    if change > 300:
        return "🔴 ارتفع كثيراً - احتمال دخول متأخر"

    if volume > 50000 and liquidity > 10000 and 10 <= change <= 200:
        return "🟢 قابل للمتابعة"

    return "⚪ مراقبة فقط"


@app.route("/")
def home():
    return "Solana Brain is running"


@app.route("/debug")
def debug():
    pairs = get_solana_pairs()
    return {
        "count": len(pairs),
        "pairs": pairs[:3]
    }


@app.route("/init-db")
def init_database():
    init_db()
    return "Database initialized"


@app.route("/scan")
def scan():
    pairs = get_solana_pairs()
    count = len(pairs)

    message = f"🧠 تقرير فحص سوق سولانا\n"
    message += f"🕒 Scan time: {int(time.time())}\n"
    message += f"📊 عدد النتائج: {count}\n\n"

    if count == 0:
        message += "لا توجد بيانات حالياً."
    else:
        saved_count = 0

        for pair in pairs:
            classification = classify_pair(pair)

            try:
                save_market_snapshot(pair, classification)
                saved_count += 1
            except Exception as e:
                print("DB save error:", e, flush=True)

            message += (
                f"📌 {pair.get('symbol', 'Unknown')} - {pair.get('name', 'Unknown')}\n"
                f"💵 السعر: {pair.get('price', 'N/A')}\n"
                f"💰 السيولة: {pair.get('liquidity', 0)}\n"
                f"📊 حجم 24h: {pair.get('volume_24h', 0)}\n"
                f"📈 تغير 24h: {pair.get('change_24h', 'N/A')}%\n"
                f"🧪 التصنيف: {classification}\n"
                f"🏦 DEX: {pair.get('dex', 'unknown')}\n"
                f"🔗 {pair.get('pair_url', '')}\n\n"
            )

        message += f"💾 تم حفظ {saved_count} سجل في قاعدة البيانات."

    send_telegram(message)

    return {
        "sent": True,
        "count": count
    }

from database import get_connection

@app.route("/stats")
def stats():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT COUNT(*) AS total
        FROM market_snapshots
    """)
    total = cur.fetchone()["total"]

    cur.execute("""
        SELECT COUNT(DISTINCT token_address) AS unique_tokens
        FROM market_snapshots
    """)
    unique_tokens = cur.fetchone()["unique_tokens"]

    cur.execute("""
        SELECT symbol, name, COUNT(*) AS appearances
        FROM market_snapshots
        GROUP BY symbol, name
        ORDER BY appearances DESC
        LIMIT 10
    """)
    top_tokens = cur.fetchall()

    cur.close()
    conn.close()

    html = f"""
    <h1>🧠 Solana Brain Stats</h1>
    <p><b>💾 Total Records:</b> {total}</p>
    <p><b>🪙 Unique Tokens:</b> {unique_tokens}</p>

    <h2>🔥 Most Tracked Tokens</h2>
    """

    for token in top_tokens:
        html += (
            f"<p>{token['symbol']} - "
            f"{token['name']} "
            f"({token['appearances']} مرات)</p>"
        )

    return html
    @app.route("/top")
def top():
    return "<h1>Top Tokens</h1>"
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
