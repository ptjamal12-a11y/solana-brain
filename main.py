from flask import Flask, request
from collectors.solana_collector import get_solana_pairs
from database import init_db, save_market_snapshot, get_connection
import os
import requests
import time

app = Flask(__name__)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def send_telegram(message):
    if not BOT_TOKEN or not CHAT_ID:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": CHAT_ID, "text": message, "disable_web_page_preview": True},
            timeout=15
        )
    except Exception as e:
        print("Telegram error:", e, flush=True)


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


def calculate_signal_score(pair):
    liquidity = safe_float(pair.get("liquidity"))
    volume = safe_float(pair.get("volume_24h"))
    change = safe_float(pair.get("change_24h"))

    score = 0

    if liquidity >= 100000:
        score += 35
    elif liquidity >= 10000:
        score += 25
    elif liquidity > 0:
        score += 10

    if volume >= 200000:
        score += 35
    elif volume >= 50000:
        score += 25
    elif volume >= 10000:
        score += 10

    if 10 <= change <= 120:
        score += 30
    elif 120 < change <= 200:
        score += 15
    elif change > 300:
        score -= 25
    elif change < -50:
        score -= 30

    if liquidity == 0:
        score = min(score, 40)

    return max(0, min(100, score))


def moonshot_score(appearances, volume, liquidity, change):
    appearances = safe_float(appearances)
    volume = safe_float(volume)
    liquidity = safe_float(liquidity)
    change = safe_float(change)

    score = 0

    if appearances >= 5:
        score += 30
    elif appearances >= 3:
        score += 20
    else:
        score += 10

    if volume >= 200000:
        score += 35
    elif volume >= 100000:
        score += 30
    elif volume >= 50000:
        score += 20
    elif volume >= 30000:
        score += 10

    if liquidity >= 100000:
        score += 25
    elif liquidity >= 10000:
        score += 20
    elif liquidity > 0:
        score += 10
    else:
        score -= 30

    if 20 <= change <= 120:
        score += 20
    elif 120 < change <= 200:
        score += 10
    elif change > 300:
        score -= 15
    elif change < -50:
        score -= 20

    if liquidity == 0:
        score = min(score, 40)

    return max(0, min(100, score))


@app.route("/")
def home():
    return """
    <h1>Solana Brain is running</h1>
    <p><a href="/scan">Run Scan</a></p>
    <p><a href="/debug">Debug</a></p>
    <p><a href="/stats">Stats</a></p>
    <p><a href="/top">Top Tokens</a></p>
    <p><a href="/winners">Winners</a></p>
    <p><a href="/signals">Signals</a></p>
    <p><a href="/early">Early Gems</a></p>
    <p><a href="/moonshots">Moonshots</a></p>
    <p><a href="/alerts">Alerts</a></p>
    <p><a href="/init-ai">Init AI</a></p>
    <p><a href="/brain">Brain</a></p>
    <p><a href="/learn">Learn</a></p>
    <p><a href="/recommendations">Recommendations</a></p>
    <p><a href="/source-ranking">Source Ranking</a></p>
    """


@app.route("/debug")
def debug():
    pairs = get_solana_pairs()
    return {"count": len(pairs), "pairs": pairs[:3]}


@app.route("/init-db")
def init_database():
    init_db()
    return "Database initialized"


@app.route("/init-ai")
def init_ai():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS model_settings (
            id SERIAL PRIMARY KEY,
            liquidity_weight FLOAT DEFAULT 25,
            volume_weight FLOAT DEFAULT 30,
            change_weight FLOAT DEFAULT 20,
            appearances_weight FLOAT DEFAULT 25,
            updated_at TIMESTAMP DEFAULT NOW()
        )
    """)

    cur.execute("""
        INSERT INTO model_settings (
            liquidity_weight,
            volume_weight,
            change_weight,
            appearances_weight
        )
        SELECT 25, 30, 20, 25
        WHERE NOT EXISTS (SELECT 1 FROM model_settings)
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS recommendations (
            id SERIAL PRIMARY KEY,
            source TEXT,
            symbol TEXT,
            token_name TEXT,
            token_address TEXT,
            recommendation_text TEXT,
            price_at_recommendation NUMERIC,
            pair_url TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)

    conn.commit()
    cur.close()
    conn.close()

    return "AI + recommendations initialized"


@app.route("/scan")
def scan():
    pairs = get_solana_pairs()
    count = len(pairs)

    message = f"🧠 تقرير فحص سوق سولانا\n"
    message += f"🕒 Scan time: {int(time.time())}\n"
    message += f"📊 عدد النتائج: {count}\n\n"

    signal_messages = []

    if count == 0:
        message += "لا توجد بيانات
