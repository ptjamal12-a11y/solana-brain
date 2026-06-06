from flask import Flask
import os
import requests

app = Flask(__name__)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

text = """
🧠 Solana Brain

📅 التاريخ: اليوم

✅ Render متصل
✅ Telegram متصل
✅ GitHub متصل

📊 حالة التعلم:
لم يبدأ جمع البيانات بعد

🎯 المرحلة الحالية:
إعداد مصادر البيانات

🚀 النظام يعمل بنجاح
"""

if BOT_TOKEN and CHAT_ID:
    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={
                "chat_id": CHAT_ID,
                "text": text
            }
        )
    except Exception as e:
        print(e)

@app.route("/")
def home():
    return "Solana Brain is running"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
