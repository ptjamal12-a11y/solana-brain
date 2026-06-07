import requests
import time

SEARCH_TERMS = [
    "pump",
    "pumpfun",
    "meme",
    "moon",
    "solana",
    "dog",
    "cat",
    "pepe",
    "bonk",
    "wif",
    "ai",
    "trump"
]

BLOCKED_SYMBOLS = {
    "SOL", "WSOL", "USDC", "USDT", "USD1",
    "BTC", "ETH", "JUP", "RAY"
}

BLOCKED_NAMES = {
    "solana",
    "usd coin",
    "tether",
    "wrapped solana",
    "bitcoin",
    "ethereum"
}


def safe_float(value, default=0):
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def is_bad_pair(pair):
    symbol = str(pair.get("symbol", "")).upper().strip()
    name = str(pair.get("name", "")).lower().strip()
    price = safe_float(pair.get("price"))
    liquidity = safe_float(pair.get("liquidity"))
    volume_24h = safe_float(pair.get("volume_24h"))

    if not symbol:
        return True

    if symbol in BLOCKED_SYMBOLS:
        return True

    if name in BLOCKED_NAMES:
        return True

    if "-" in symbol or "/" in symbol:
        return True

    if 0.95 <= price <= 1.05:
        return True

    if liquidity > 100_000_000:
        return True

    if volume_24h <= 0:
        return True

    return False


def parse_pair(p):
    base = p.get("baseToken") or {}
    token_address = base.get("address")

    if not token_address:
        return None

    return {
        "address": token_address,
        "symbol": base.get("symbol", "Unknown"),
        "name": base.get("name", "Unknown"),
        "price": p.get("priceUsd"),
        "liquidity": safe_float((p.get("liquidity") or {}).get("usd")),
        "volume_24h": safe_float((p.get("volume") or {}).get("h24")),
        "change_24h": safe_float((p.get("priceChange") or {}).get("h24")),
        "dex": p.get("dexId", "unknown"),
        "pair_url": p.get("url", "")
    }


def fetch_search(term):
    url = f"https://api.dexscreener.com/latest/dex/search?q={term}"

    response = requests.get(
        url,
        timeout=20,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json"
        }
    )

    print("DEX SEARCH:", term, response.status_code, flush=True)

    if response.status_code != 200:
        return []

    data = response.json()
    return data.get("pairs") or []


def get_solana_pairs():
    all_pairs = []

    for term in SEARCH_TERMS:
        try:
            pairs = fetch_search(term)

            for p in pairs:
                if p.get("chainId") != "solana":
                    continue

                item = parse_pair(p)

                if not item:
                    continue

                if is_bad_pair(item):
                    continue

                all_pairs.append(item)

            time.sleep(0.2)

        except Exception as e:
            print("Collector error:", term, e, flush=True)

    best_by_token = {}

    for pair in all_pairs:
        address = pair["address"]

        if address not in best_by_token:
            best_by_token[address] = pair
        else:
            old = best_by_token[address]
            if pair["volume_24h"] > old["volume_24h"]:
                best_by_token[address] = pair

    final_pairs = list(best_by_token.values())

    final_pairs.sort(
        key=lambda x: (
            x["volume_24h"],
            x["liquidity"],
            abs(safe_float(x["change_24h"]))
        ),
        reverse=True
    )

    print("SOLANA PAIRS FOUND:", len(final_pairs), flush=True)

    return final_pairs[:20]
