from flask import Flask
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
        print("Telegram env not set", flush=True)
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
    """


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

    signal_messages = []

    if count == 0:
        message += "لا توجد بيانات حالياً."
    else:
        saved_count = 0

        for pair in pairs:
            classification = classify_pair(pair)
            signal_score = calculate_signal_score(pair)

            try:
                save_market_snapshot(pair, classification)
                saved_count += 1
            except Exception as e:
                print("DB save error:", e, flush=True)

            if signal_score >= 75:
                signal_messages.append(
                    f"🚨 إشارة قوية\n"
                    f"📌 {pair.get('symbol')} - {pair.get('name')}\n"
                    f"Score: {signal_score}/100\n"
                    f"💰 السيولة: {pair.get('liquidity')}\n"
                    f"📊 الحجم 24h: {pair.get('volume_24h')}\n"
                    f"📈 التغير 24h: {pair.get('change_24h')}%\n"
                    f"🔗 {pair.get('pair_url')}"
                )

            message += (
                f"📌 {pair.get('symbol', 'Unknown')} - {pair.get('name', 'Unknown')}\n"
                f"💵 السعر: {pair.get('price', 'N/A')}\n"
                f"💰 السيولة: {pair.get('liquidity', 0)}\n"
                f"📊 حجم 24h: {pair.get('volume_24h', 0)}\n"
                f"📈 تغير 24h: {pair.get('change_24h', 'N/A')}%\n"
                f"🧪 التصنيف: {classification}\n"
                f"🎯 Signal Score: {signal_score}/100\n"
                f"🏦 DEX: {pair.get('dex', 'unknown')}\n"
                f"🔗 {pair.get('pair_url', '')}\n\n"
            )

        message += f"💾 تم حفظ {saved_count} سجل في قاعدة البيانات."

    send_telegram(message)

    for alert in signal_messages:
        send_telegram(alert)

    return {
        "sent": True,
        "count": count,
        "signals": len(signal_messages)
    }


@app.route("/stats")
def stats():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) AS total FROM market_snapshots")
    total = cur.fetchone()["total"]

    cur.execute("SELECT COUNT(DISTINCT token_address) AS unique_tokens FROM market_snapshots")
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
        html += f"<p>{token['symbol']} - {token['name']} ({token['appearances']} مرات)</p>"

    html += '<p><a href="/">Back Home</a></p>'
    return html


@app.route("/top")
def top():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            token_address,
            symbol,
            name,
            COUNT(*) AS appearances,
            ROUND(AVG(volume_24h)::numeric, 2) AS avg_volume,
            ROUND(AVG(liquidity)::numeric, 2) AS avg_liquidity,
            ROUND(AVG(change_24h)::numeric, 2) AS avg_change,
            MAX(pair_url) AS pair_url
        FROM market_snapshots
        GROUP BY token_address, symbol, name
        ORDER BY COUNT(*) DESC, AVG(volume_24h) DESC
        LIMIT 20
    """)

    tokens = cur.fetchall()
    cur.close()
    conn.close()

    html = "<h1>🏆 Top Solana Tokens</h1>"

    for token in tokens:
        appearances = safe_float(token["appearances"])
        avg_volume = safe_float(token["avg_volume"])
        avg_liquidity = safe_float(token["avg_liquidity"])
        avg_change = safe_float(token["avg_change"])

        score = 0

        if appearances >= 10:
            score += 30
        elif appearances >= 5:
            score += 25
        elif appearances >= 3:
            score += 15
        else:
            score += 5

        if avg_volume >= 100000:
            score += 30
        elif avg_volume >= 50000:
            score += 20
        elif avg_volume >= 10000:
            score += 10

        if avg_liquidity >= 10000:
            score += 25
        elif avg_liquidity > 0:
            score += 10

        if 10 <= avg_change <= 200:
            score += 20
        elif avg_change > 300:
            score -= 15
        elif avg_change < -50:
            score -= 20

        if avg_liquidity == 0:
            score = min(score, 40)

        score = max(0, min(100, score))

        if avg_liquidity == 0:
            label = "🟡 مبكر جداً / بدون سيولة"
        elif score >= 75:
            label = "🟢 قوي"
        elif score >= 50:
            label = "🟡 متوسط"
        else:
            label = "🔴 ضعيف / مراقبة فقط"

        html += f"""
        <hr>
        <h2>{token['symbol']} - {token['name']}</h2>
        <p><b>Score:</b> {score}/100 {label}</p>
        <p><b>Appearances:</b> {token['appearances']}</p>
        <p><b>Avg Volume:</b> {token['avg_volume']}</p>
        <p><b>Avg Liquidity:</b> {token['avg_liquidity']}</p>
        <p><b>Avg Change:</b> {token['avg_change']}%</p>
        <p><a href="{token['pair_url']}" target="_blank">Open DexScreener</a></p>
        """

    html += '<p><a href="/">Back Home</a></p>'
    return html


@app.route("/winners")
def winners():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        WITH first_rows AS (
            SELECT DISTINCT ON (token_address)
                token_address,
                symbol,
                name,
                price AS first_price,
                created_at AS first_seen
            FROM market_snapshots
            WHERE price IS NOT NULL AND price > 0
            ORDER BY token_address, created_at ASC
        ),
        latest_rows AS (
            SELECT DISTINCT ON (token_address)
                token_address,
                price AS latest_price,
                created_at AS last_seen,
                pair_url
            FROM market_snapshots
            WHERE price IS NOT NULL AND price > 0
            ORDER BY token_address, created_at DESC
        )
        SELECT
            f.symbol,
            f.name,
            f.first_price,
            l.latest_price,
            ROUND(((l.latest_price - f.first_price) / f.first_price * 100)::numeric, 2) AS roi,
            f.first_seen,
            l.last_seen,
            l.pair_url
        FROM first_rows f
        JOIN latest_rows l ON f.token_address = l.token_address
        WHERE f.first_price > 0
        ORDER BY roi DESC
        LIMIT 20
    """)

    rows = cur.fetchall()
    cur.close()
    conn.close()

    html = "<h1>🚀 Winners</h1>"
    html += "<p>العملات التي ارتفعت بعد أول رصد لها.</p>"

    for r in rows:
        roi = float(r["roi"] or 0)

        if roi > 100:
            label = "🟢 انفجار قوي"
        elif roi > 30:
            label = "🟡 صعود جيد"
        elif roi > 0:
            label = "⚪ صعود بسيط"
        else:
            label = "🔴 لم تنجح"

        html += f"""
        <hr>
        <h2>{r['symbol']} - {r['name']}</h2>
        <p><b>ROI:</b> {r['roi']}% {label}</p>
        <p><b>First Price:</b> {r['first_price']}</p>
        <p><b>Latest Price:</b> {r['latest_price']}</p>
        <p><a href="{r['pair_url']}" target="_blank">Open DexScreener</a></p>
        """

    html += '<p><a href="/">Back Home</a></p>'
    return html


@app.route("/signals")
def signals():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            symbol,
            name,
            price,
            liquidity,
            volume_24h,
            change_24h,
            pair_url,
            created_at
        FROM market_snapshots
        WHERE volume_24h >= 30000
          AND change_24h > 20
        ORDER BY created_at DESC
        LIMIT 30
    """)

    rows = cur.fetchall()
    cur.close()
    conn.close()

    html = "<h1>🚨 Signals</h1>"
    html += "<p>آخر الفرص حسب الحجم والزخم، حتى لو كانت بدون سيولة حقيقية.</p>"

    for r in rows:
        liquidity = safe_float(r["liquidity"])
        volume = safe_float(r["volume_24h"])
        change = safe_float(r["change_24h"])

        score = 0

        if volume >= 200000:
            score += 40
        elif volume >= 100000:
            score += 30
        elif volume >= 50000:
            score += 20
        else:
            score += 10

        if 20 <= change <= 120:
            score += 30
        elif 120 < change <= 250:
            score += 20
        elif change > 250:
            score += 5

        if liquidity >= 10000:
            score += 30
        elif liquidity > 0:
            score += 10
        else:
            score = min(score, 40)

        score = max(0, min(100, score))

        if liquidity == 0:
            label = "🟡 مبكر جداً / بدون سيولة"
        elif score >= 75:
            label = "🟢 قوي"
        elif score >= 50:
            label = "🟡 متوسط"
        else:
            label = "🔴 مراقبة فقط"

        html += f"""
        <hr>
        <h2>{r['symbol']} - {r['name']}</h2>
        <p><b>Signal Score:</b> {score}/100 {label}</p>
        <p><b>Price:</b> {r['price']}</p>
        <p><b>Liquidity:</b> {r['liquidity']}</p>
        <p><b>Volume 24h:</b> {r['volume_24h']}</p>
        <p><b>Change 24h:</b> {r['change_24h']}%</p>
        <p><b>Seen At:</b> {r['created_at']}</p>
        <p><a href="{r['pair_url']}" target="_blank">Open DexScreener</a></p>
        """

    html += '<p><a href="/">Back Home</a></p>'
    return html


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
