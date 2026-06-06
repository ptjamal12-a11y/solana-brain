from flask import Flask
from collectors.solana_collector import get_solana_pairs
import os
import requests

app = Flask(__name__)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def send_telegram(message):
    if not BOT_TOKEN or not CHAT_ID:
        print("Telegram env not set")
        return

    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={
                "chat_id": CHAT_ID,
                "text": message,
                "disable_web_page_preview": True
            },
            timeout=15
        )
    except Exception as e:
        print("Telegram error:", e)


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


@app.route("/scan")
def scan():
    pairs = get_solana_pairs()

    message = "🧠 تقرير فحص سوق سولانا\n\n"

    if not pairs:
        message += "لا توجد بيانات حالياً."
    else:
        for pair in pairs:
            message += (
                f"📌 {pair.get('symbol', 'Unknown')} - {pair.get('name', 'Unknown')}\n"
                f"💵 السعر: {pair.get('price', 'N/A')}\n"
                f"💰 السيولة: {pair.get('liquidity', 0)}\n"
                f"📊 حجم 24h: {pair.get('volume_24h', 0)}\n"
                f"📈 تغير 24h: {pair.get('change_24h', 'N/A')}%\n"
                f"🧪 التصنيف: {classify_pair(pair)}\n"
                f"🏦 DEX: {pair.get('dex', 'unknown')}\n"
                f"🔗 {pair.get('pair_url', '')}\n\n"
            )

    send_telegram(message)
    return "Smart report sent to Telegram"


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
