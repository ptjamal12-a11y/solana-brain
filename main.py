from flask import Flask
from collectors.solana_collector import get_solana_pairs
import os
import requests

app = Flask(__name__)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_telegram(message):
    if BOT_TOKEN and CHAT_ID:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": CHAT_ID, "text": message}
        )

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
                f"📌 {pair['symbol']} - {pair['name']}\n"
                f"💵 السعر: {pair['price']}\n"
                f"💰 السيولة: {pair['liquidity']}\n"
                f"📊 حجم 24h: {pair['volume_24h']}\n"
                f"📈 تغير 24h: {pair['change_24h']}%\n\n"
            )

    send_telegram(message)
    return "Smart report sent to Telegram"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
