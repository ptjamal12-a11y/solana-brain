from flask import Flask
from collectors.solana_collector import get_solana_pairs
import os
import requests

app = Flask(__name__)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


@app.route("/")
def home():
    return "Solana Brain is running"


@app.route("/scan")
def scan():
    pairs = get_solana_pairs()

    message = "🧠 تقرير فحص سولانا\n\n"

    for pair in pairs:
        symbol = pair.get("baseToken", {}).get("symbol", "Unknown")
        price = pair.get("priceUsd", "N/A")
        liquidity = pair.get("liquidity", {}).get("usd", "N/A")

        message += (
            f"📌 {symbol}\n"
            f"💵 السعر: {price}\n"
            f"💰 السيولة: {liquidity}\n\n"
        )

    if BOT_TOKEN and CHAT_ID:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={
                "chat_id": CHAT_ID,
                "text": message
            }
        )

    return "Report sent to Telegram"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
