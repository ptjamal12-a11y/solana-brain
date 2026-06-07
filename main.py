from flask import Flask, request
from collectors.solana_collector import get_solana_pairs
from database import init_db, save_market_snapshot, get_connection
import os
import requests
import time

app = Flask(__name__)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


@app.after_request
def add_utf8_header(response):
    response.headers["Content-Type"] = response.headers.get(
        "Content-Type",
        "text/html; charset=utf-8"
    )
    if response.headers["Content-Type"].startswith("text/html"):
        response.headers["Content-Type"] = "text/html; charset=utf-8"
    return response


def send_telegram(message):
    if not BOT_TOKEN or not CHAT_ID:
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
    except Exception:
        return default


def classify_pair(pair):
    liquidity = safe_float(pair.get("liquidity"))
    volume = safe_float(pair.get("volume_24h"))
    change = safe_float(pair.get("change_24h"))

    if liquidity == 0:
        return "Early / No Liquidity"

    if liquidity < 5000:
        return "Very Low Liquidity"

    if change < -50:
        return "Strong Drop"

    if change > 300:
        return "Too Late / High Pump Risk"

    if volume > 50000 and liquidity > 10000 and 10 <= change <= 200:
        return "Watchable"

    return "Watch Only"


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
        score = min(score, 20)

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
        score = min(score, 20)

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
    <p><a href="/best-today">Best Today</a></p>
    <p><a href="/init-ai">Init AI</a></p>
    <p><a href="/brain">Brain</a></p>
    <p><a href="/learn">Learn</a></p>
    <p><a href="/recommendations">Recommendations</a></p>
    <p><a href="/collect-recommendations">Collect Recommendations</a></p>
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

    cur.execute("""
        CREATE TABLE IF NOT EXISTS binance_snapshots (
            id SERIAL PRIMARY KEY,
            symbol TEXT,
            price NUMERIC,
            price_change_percent NUMERIC,
            volume NUMERIC,
            quote_volume NUMERIC,
            high_price NUMERIC,
            low_price NUMERIC,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)

    conn.commit()
    cur.close()
    conn.close()

    return "AI, recommendations, and market tables initialized"


@app.route("/scan")
def scan():
    pairs = get_solana_pairs()
    count = len(pairs)

    message = "Solana Market Scan Report\n"
    message += f"Scan time: {int(time.time())}\n"
    message += f"Results count: {count}\n\n"

    signal_messages = []

    if count == 0:
        message += "No data available now."
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
                    f"Strong Signal\n"
                    f"Token: {pair.get('symbol')} - {pair.get('name')}\n"
                    f"Score: {signal_score}/100\n"
                    f"Liquidity: {pair.get('liquidity')}\n"
                    f"Volume 24h: {pair.get('volume_24h')}\n"
                    f"Change 24h: {pair.get('change_24h')}%\n"
                    f"URL: {pair.get('pair_url')}"
                )

            message += (
                f"Token: {pair.get('symbol', 'Unknown')} - {pair.get('name', 'Unknown')}\n"
                f"Price: {pair.get('price', 'N/A')}\n"
                f"Liquidity: {pair.get('liquidity', 0)}\n"
                f"Volume 24h: {pair.get('volume_24h', 0)}\n"
                f"Change 24h: {pair.get('change_24h', 'N/A')}%\n"
                f"Classification: {classification}\n"
                f"Signal Score: {signal_score}/100\n"
                f"DEX: {pair.get('dex', 'unknown')}\n"
                f"URL: {pair.get('pair_url', '')}\n\n"
            )

        message += f"Saved {saved_count} records to database."

    send_telegram(message)

    for alert in signal_messages:
        send_telegram(alert)

    return {"sent": True, "count": count, "signals": len(signal_messages)}


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
    <h1>Solana Brain Stats</h1>
    <p><b>Total Records:</b> {total}</p>
    <p><b>Unique Tokens:</b> {unique_tokens}</p>
    <h2>Most Tracked Tokens</h2>
    """

    for token in top_tokens:
        html += f"<p>{token['symbol']} - {token['name']} ({token['appearances']} times)</p>"

    html += '<p><a href="/">Back Home</a></p>'
    return html


@app.route("/top")
def top():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            token_address, symbol, name,
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

    html = "<h1>Top Solana Tokens</h1>"

    for token in tokens:
        score = moonshot_score(
            token["appearances"],
            token["avg_volume"],
            token["avg_liquidity"],
            token["avg_change"]
        )

        avg_liquidity = safe_float(token["avg_liquidity"])

        if avg_liquidity == 0:
            label = "Early / No Liquidity"
        elif score >= 75:
            label = "Strong"
        elif score >= 50:
            label = "Medium"
        else:
            label = "Weak / Watch Only"

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
                token_address, symbol, name,
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
            f.symbol, f.name, f.first_price, l.latest_price,
            ROUND(((l.latest_price - f.first_price) / f.first_price * 100)::numeric, 2) AS roi,
            f.first_seen, l.last_seen, l.pair_url
        FROM first_rows f
        JOIN latest_rows l ON f.token_address = l.token_address
        WHERE f.first_price > 0
        ORDER BY roi DESC
        LIMIT 20
    """)

    rows = cur.fetchall()
    cur.close()
    conn.close()

    html = "<h1>Winners</h1>"
    html += "<p>Tokens that increased after first detection.</p>"

    for r in rows:
        roi = safe_float(r["roi"])

        if roi > 100:
            label = "Strong Explosion"
        elif roi > 30:
            label = "Good Rise"
        elif roi > 0:
            label = "Small Rise"
        else:
            label = "Not Successful"

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
        SELECT symbol, name, price, liquidity, volume_24h, change_24h, pair_url, created_at
        FROM market_snapshots
        WHERE volume_24h >= 30000
          AND change_24h > 20
        ORDER BY created_at DESC
        LIMIT 30
    """)

    rows = cur.fetchall()
    cur.close()
    conn.close()

    html = "<h1>Signals</h1>"
    html += "<p>Latest opportunities based on volume and momentum.</p>"

    for r in rows:
        pair = {
            "liquidity": r["liquidity"],
            "volume_24h": r["volume_24h"],
            "change_24h": r["change_24h"]
        }
        score = calculate_signal_score(pair)
        liquidity = safe_float(r["liquidity"])

        if liquidity == 0:
            label = "Early / No Liquidity"
        elif score >= 75:
            label = "Strong"
        elif score >= 50:
            label = "Medium"
        else:
            label = "Watch Only"

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


@app.route("/early")
def early():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT symbol, name, price, liquidity, volume_24h, change_24h, pair_url, created_at
        FROM market_snapshots
        WHERE liquidity = 0
          AND volume_24h >= 30000
          AND change_24h > 10
        ORDER BY volume_24h DESC, change_24h DESC
        LIMIT 30
    """)

    rows = cur.fetchall()
    cur.close()
    conn.close()

    html = "<h1>Early Gems</h1>"
    html += "<p>Very early Pump.fun tokens with no real liquidity. Watch only.</p>"

    for r in rows:
        html += f"""
        <hr>
        <h2>{r['symbol']} - {r['name']}</h2>
        <p><b>Price:</b> {r['price']}</p>
        <p><b>Liquidity:</b> {r['liquidity']}</p>
        <p><b>Volume 24h:</b> {r['volume_24h']}</p>
        <p><b>Change 24h:</b> {r['change_24h']}%</p>
        <p><b>Seen At:</b> {r['created_at']}</p>
        <p><a href="{r['pair_url']}" target="_blank">Open DexScreener</a></p>
        """

    html += '<p><a href="/">Back Home</a></p>'
    return html


@app.route("/moonshots")
def moonshots():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            token_address, symbol, name,
            COUNT(*) AS appearances,
            ROUND(AVG(volume_24h)::numeric, 2) AS avg_volume,
            ROUND(AVG(liquidity)::numeric, 2) AS avg_liquidity,
            ROUND(AVG(change_24h)::numeric, 2) AS avg_change,
            MAX(pair_url) AS pair_url
        FROM market_snapshots
        GROUP BY token_address, symbol, name
        HAVING COUNT(*) >= 3
           AND AVG(volume_24h) >= 50000
        ORDER BY AVG(volume_24h) DESC
        LIMIT 30
    """)

    rows = cur.fetchall()
    cur.close()
    conn.close()

    html = "<h1>Moonshots</h1>"
    html += "<p>Best candidates based on activity, recurrence, volume, and liquidity.</p>"

    for r in rows:
        score = moonshot_score(
            r["appearances"],
            r["avg_volume"],
            r["avg_liquidity"],
            r["avg_change"]
        )

        liquidity = safe_float(r["avg_liquidity"])

        if liquidity == 0:
            label = "Early / No Liquidity"
        elif score >= 75:
            label = "Strong"
        elif score >= 50:
            label = "Medium"
        else:
            label = "Watch Only"

        html += f"""
        <hr>
        <h2>{r['symbol']} - {r['name']}</h2>
        <p><b>Moonshot Score:</b> {score}/100 {label}</p>
        <p><b>Appearances:</b> {r['appearances']}</p>
        <p><b>Avg Volume:</b> {r['avg_volume']}</p>
        <p><b>Avg Liquidity:</b> {r['avg_liquidity']}</p>
        <p><b>Avg Change:</b> {r['avg_change']}%</p>
        <p><a href="{r['pair_url']}" target="_blank">Open DexScreener</a></p>
        """

    html += '<p><a href="/">Back Home</a></p>'
    return html


@app.route("/alerts")
def alerts():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            token_address,
            MAX(symbol) AS symbol,
            MAX(name) AS name,
            COUNT(*) AS appearances,
            ROUND(AVG(volume_24h)::numeric, 2) AS avg_volume,
            ROUND(AVG(liquidity)::numeric, 2) AS avg_liquidity,
            ROUND(AVG(change_24h)::numeric, 2) AS avg_change,
            MAX(pair_url) AS pair_url
        FROM market_snapshots
        GROUP BY token_address
        HAVING AVG(liquidity) >= 10000
           AND AVG(volume_24h) >= 50000
           AND COUNT(*) >= 2
        ORDER BY AVG(volume_24h) DESC
        LIMIT 20
    """)

    rows = cur.fetchall()
    cur.close()
    conn.close()

    html = "<h1>Alerts</h1>"
    html += "<p>Unique strong opportunities with real liquidity and good trading volume.</p>"

    for r in rows:
        score = moonshot_score(
            r["appearances"],
            r["avg_volume"],
            r["avg_liquidity"],
            r["avg_change"]
        )

        if score < 60:
            continue

        label = "Strong" if score >= 75 else "Medium"

        html += f"""
        <hr>
        <h2>{r['symbol']} - {r['name']}</h2>
        <p><b>Alert Score:</b> {score}/100 {label}</p>
        <p><b>Appearances:</b> {r['appearances']}</p>
        <p><b>Avg Volume:</b> {r['avg_volume']}</p>
        <p><b>Avg Liquidity:</b> {r['avg_liquidity']}</p>
        <p><b>Avg Change:</b> {r['avg_change']}%</p>
        <p><a href="{r['pair_url']}" target="_blank">Open DexScreener</a></p>
        """

    html += '<p><a href="/">Back Home</a></p>'
    return html

@app.route("/brain")
def brain():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT * FROM model_settings ORDER BY id DESC LIMIT 1")
    row = cur.fetchone()

    cur.close()
    conn.close()

    if not row:
        return "Run /init-ai first"

    return f"""
    <h1>Solana Brain Weights</h1>
    <p><b>Liquidity Weight:</b> {row['liquidity_weight']}</p>
    <p><b>Volume Weight:</b> {row['volume_weight']}</p>
    <p><b>Change Weight:</b> {row['change_weight']}</p>
    <p><b>Appearances Weight:</b> {row['appearances_weight']}</p>
    <p><b>Last Update:</b> {row['updated_at']}</p>
    <p><a href="/">Back Home</a></p>
    """


@app.route("/learn")
def learn():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        WITH first_rows AS (
            SELECT DISTINCT ON (token_address)
                token_address,
                price AS first_price
            FROM market_snapshots
            WHERE price IS NOT NULL AND price > 0
            ORDER BY token_address, created_at ASC
        ),
        latest_rows AS (
            SELECT DISTINCT ON (token_address)
                token_address,
                price AS latest_price
            FROM market_snapshots
            WHERE price IS NOT NULL AND price > 0
            ORDER BY token_address, created_at DESC
        ),
        perf AS (
            SELECT
                f.token_address,
                ((l.latest_price - f.first_price) / f.first_price * 100) AS roi
            FROM first_rows f
            JOIN latest_rows l ON f.token_address = l.token_address
            WHERE f.first_price > 0
        ),
        features AS (
            SELECT
                m.token_address,
                AVG(m.liquidity) AS avg_liquidity,
                AVG(m.volume_24h) AS avg_volume,
                AVG(m.change_24h) AS avg_change,
                COUNT(*) AS appearances,
                p.roi
            FROM market_snapshots m
            JOIN perf p ON m.token_address = p.token_address
            GROUP BY m.token_address, p.roi
        )
        SELECT
            AVG(avg_liquidity) FILTER (WHERE roi > 30) AS win_liquidity,
            AVG(avg_volume) FILTER (WHERE roi > 30) AS win_volume,
            AVG(avg_change) FILTER (WHERE roi > 30) AS win_change,
            AVG(appearances) FILTER (WHERE roi > 30) AS win_appearances
        FROM features
    """)

    data = cur.fetchone()

    liquidity_weight = 25
    volume_weight = 30
    change_weight = 20
    appearances_weight = 25

    if data:
        if safe_float(data["win_volume"]) > 50000:
            volume_weight += 10
        if safe_float(data["win_liquidity"]) > 10000:
            liquidity_weight += 10
        if 10 <= safe_float(data["win_change"]) <= 200:
            change_weight += 10
        if safe_float(data["win_appearances"]) >= 3:
            appearances_weight += 10

    cur.execute("""
        INSERT INTO model_settings (
            liquidity_weight,
            volume_weight,
            change_weight,
            appearances_weight,
            updated_at
        )
        VALUES (%s, %s, %s, %s, NOW())
    """, (
        liquidity_weight,
        volume_weight,
        change_weight,
        appearances_weight
    ))

    conn.commit()
    cur.close()
    conn.close()

    return f"""
    <h1>Learning Complete</h1>
    <p>Liquidity Weight: {liquidity_weight}</p>
    <p>Volume Weight: {volume_weight}</p>
    <p>Change Weight: {change_weight}</p>
    <p>Appearances Weight: {appearances_weight}</p>
    <p><a href="/brain">View Brain</a></p>
    """


@app.route("/add-recommendation")
def add_recommendation():
    source = request.args.get("source", "unknown")
    symbol = request.args.get("symbol", "")
    text = request.args.get("text", "")

    if not symbol:
        return "Missing symbol. Example: /add-recommendation?source=x&symbol=PUMP&text=good"

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT token_address, name, price, pair_url
        FROM market_snapshots
        WHERE LOWER(symbol) = LOWER(%s)
        ORDER BY created_at DESC
        LIMIT 1
    """, (symbol,))

    token = cur.fetchone()

    if not token:
        cur.close()
        conn.close()
        return "Token not found in market_snapshots yet"

    cur.execute("""
        INSERT INTO recommendations (
            source,
            symbol,
            token_name,
            token_address,
            recommendation_text,
            price_at_recommendation,
            pair_url
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (
        source,
        symbol,
        token["name"],
        token["token_address"],
        text,
        token["price"],
        token["pair_url"]
    ))

    conn.commit()
    cur.close()
    conn.close()

    return "Recommendation saved"


@app.route("/recommendations")
def recommendations():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT * FROM recommendations ORDER BY created_at DESC LIMIT 50")
    rows = cur.fetchall()

    cur.close()
    conn.close()

    html = "<h1>Recommendations</h1>"
    html += "<p>Manual and automatic recommendations from different sources.</p>"

    for r in rows:
        html += f"""
        <hr>
        <h2>{r['symbol']} - {r['token_name']}</h2>
        <p><b>Source:</b> {r['source']}</p>
        <p><b>Text:</b> {r['recommendation_text']}</p>
        <p><b>Price When Mentioned:</b> {r['price_at_recommendation']}</p>
        <p><b>Seen At:</b> {r['created_at']}</p>
        <p><a href="{r['pair_url']}" target="_blank">Open DexScreener</a></p>
        """

    html += '<p><a href="/">Back Home</a></p>'
    return html


@app.route("/source-ranking")
def source_ranking():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        WITH latest_prices AS (
            SELECT DISTINCT ON (token_address)
                token_address,
                price AS latest_price
            FROM market_snapshots
            WHERE price IS NOT NULL AND price > 0
            ORDER BY token_address, created_at DESC
        )
        SELECT
            r.source,
            COUNT(*) AS total_recommendations,
            ROUND(AVG(((l.latest_price - r.price_at_recommendation) / r.price_at_recommendation * 100))::numeric, 2) AS avg_roi,
            SUM(
                CASE
                    WHEN ((l.latest_price - r.price_at_recommendation) / r.price_at_recommendation * 100) > 30
                    THEN 1 ELSE 0
                END
            ) AS winners
        FROM recommendations r
        JOIN latest_prices l ON r.token_address = l.token_address
        WHERE r.price_at_recommendation IS NOT NULL
          AND r.price_at_recommendation > 0
        GROUP BY r.source
        ORDER BY avg_roi DESC
    """)

    rows = cur.fetchall()

    cur.close()
    conn.close()

    html = "<h1>Source Ranking</h1>"
    html += "<p>Ranking recommendation sources based on actual results.</p>"

    for r in rows:
        html += f"""
        <hr>
        <h2>{r['source']}</h2>
        <p><b>Total Recommendations:</b> {r['total_recommendations']}</p>
        <p><b>Average ROI:</b> {r['avg_roi']}%</p>
        <p><b>Winners +30%:</b> {r['winners']}</p>
        """

    html += '<p><a href="/">Back Home</a></p>'
    return html


@app.route("/collect-recommendations")
def collect_recommendations():
    pairs = get_solana_pairs()

    conn = get_connection()
    cur = conn.cursor()

    saved = 0
    skipped = 0

    for pair in pairs:
        score = calculate_signal_score(pair)

        if score < 70:
            skipped += 1
            continue

        if safe_float(pair.get("volume_24h")) < 50000:
            skipped += 1
            continue

        if safe_float(pair.get("change_24h")) < 10:
            skipped += 1
            continue

        symbol = pair.get("symbol")
        name = pair.get("name")
        address = pair.get("address")
        price = pair.get("price")
        pair_url = pair.get("pair_url")

        if not symbol or not address:
            skipped += 1
            continue

        source = "dexscreener_auto_filtered"
        text = f"Auto filtered recommendation. Signal Score: {score}/100"

        cur.execute("""
            SELECT id
            FROM recommendations
            WHERE token_address = %s
              AND source = %s
              AND created_at > NOW() - INTERVAL '6 hours'
            LIMIT 1
        """, (address, source))

        exists = cur.fetchone()

        if exists:
            skipped += 1
            continue

        cur.execute("""
            INSERT INTO recommendations (
                source,
                symbol,
                token_name,
                token_address,
                recommendation_text,
                price_at_recommendation,
                pair_url
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            source,
            symbol,
            name,
            address,
            text,
            price,
            pair_url
        ))

        saved += 1

    conn.commit()
    cur.close()
    conn.close()

    return {
        "saved_recommendations": saved,
        "skipped": skipped,
        "source": "dexscreener_auto_filtered"
    }
@app.route("/best-today")
def best_today():
    conn = get_connection()
    cur = conn.cursor()

    html = "<h1>Best Today</h1>"

    # أعلى حجم تداول
    cur.execute("""
        SELECT symbol, name, volume_24h, pair_url
        FROM market_snapshots
        ORDER BY volume_24h DESC
        LIMIT 1
    """)
    top_volume = cur.fetchone()

    if top_volume:
        html += f"""
        <h2>Highest Volume</h2>
        <p>{top_volume['symbol']} - {top_volume['name']}</p>
        <p>Volume: {top_volume['volume_24h']}</p>
        <p><a href="{top_volume['pair_url']}">Open DexScreener</a></p>
        <hr>
        """

    # أعلى سيولة
    cur.execute("""
        SELECT symbol, name, liquidity, pair_url
        FROM market_snapshots
        ORDER BY liquidity DESC
        LIMIT 1
    """)
    top_liquidity = cur.fetchone()

    if top_liquidity:
        html += f"""
        <h2>Highest Liquidity</h2>
        <p>{top_liquidity['symbol']} - {top_liquidity['name']}</p>
        <p>Liquidity: {top_liquidity['liquidity']}</p>
        <p><a href="{top_liquidity['pair_url']}">Open DexScreener</a></p>
        <hr>
        """

    # أعلى نمو
    cur.execute("""
        SELECT symbol, name, change_24h, pair_url
        FROM market_snapshots
        ORDER BY change_24h DESC
        LIMIT 1
    """)
    top_growth = cur.fetchone()

    if top_growth:
        html += f"""
        <h2>Highest Growth</h2>
        <p>{top_growth['symbol']} - {top_growth['name']}</p>
        <p>Growth: {top_growth['change_24h']}%</p>
        <p><a href="{top_growth['pair_url']}">Open DexScreener</a></p>
        <hr>
        """

    cur.close()
    conn.close()

    html += '<p><a href="/">Back Home</a></p>'

    return html

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
