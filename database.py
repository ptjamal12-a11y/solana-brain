import os
import psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_URL = os.getenv("DATABASE_URL")


def get_connection():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS market_snapshots (
            id SERIAL PRIMARY KEY,
            token_address TEXT,
            symbol TEXT,
            name TEXT,
            price NUMERIC,
            liquidity NUMERIC,
            volume_24h NUMERIC,
            change_24h NUMERIC,
            dex TEXT,
            pair_url TEXT,
            classification TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        );
    """)

    conn.commit()
    cur.close()
    conn.close()


def save_market_snapshot(pair, classification):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO market_snapshots (
            token_address,
            symbol,
            name,
            price,
            liquidity,
            volume_24h,
            change_24h,
            dex,
            pair_url,
            classification
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        pair.get("address"),
        pair.get("symbol"),
        pair.get("name"),
        pair.get("price"),
        pair.get("liquidity"),
        pair.get("volume_24h"),
        pair.get("change_24h"),
        pair.get("dex"),
        pair.get("pair_url"),
        classification
    ))

    conn.commit()
    cur.close()
    conn.close()
