import requests

DEX_URLS = [
    "https://api.dexscreener.com/latest/dex/search?q=pumpfun",
    "https://api.dexscreener.com/latest/dex/search?q=pump",
    "https://api.dexscreener.com/latest/dex/search?q=moon",
    "https://api.dexscreener.com/latest/dex/search?q=meme",
]

BLOCKED_SYMBOLS = {
    "SOL", "WSOL", "USDC", "USDT", "USD1", "SOL-USDT",
    "USDC-SOL", "SOL-USD1", "BTC", "ETH"
}

BLOCKED_NAMES = {
    "solana", "usd coin", "tether", "wrapped solana"
}


def safe_float(value, default=0):
    try:
        if value is None:
            return default
        return float(value)
    except:
        return default


def is_bad_pair(pair):
    symbol = str(pair.get("symbol", "")).upper()
    name = str(pair.get("name", "")).lower()
    price = safe_float(pair.get("price"))
    liquidity = safe_float(pair.get("liquidity"))
    volume_24h = safe_float(pair.get("volume_24h"))

    if symbol in BLOCKED_SYMBOLS:
        return True

    if name in BLOCKED_NAMES:
        return True

    if "-" in symbol:
        return True

    # استبعاد العملات المستقرة أو الأزواج القريبة من 1$
    if 0.95 <= price <= 1.05:
        return True

    # استبعاد سيولة ضخمة غالباً ليست ميم كوين
    if liquidity > 50_000_000:
        return True

    # استبعاد بدون نشاط
    if volume_24h <= 0:
        return True

    return False


def get_solana_pairs():
    all_pairs = []

    for url in DEX_URLS:
        try:
            response = requests.get(
                url,
                timeout=15,
                headers={"User-Agent": "Mozilla/5.0"}
            )

            print("DEX STATUS:", response.status_code, url)

            if response.status_code != 200:
                continue

            data = response.json()
            pairs = data.get("pairs") or []

            for p in pairs:
                if p.get("chainId") != "solana":
                    continue

                base = p.get("baseToken") or {}
                token_address = base.get("address")

                if not token_address:
                    continue

                item = {
                    "address": token_address,
                    "symbol": base.get("symbol", "Unknown"),
                    "name": base.get("name", "Unknown"),
                    "price": p.get("priceUsd"),
                    "liquidity": safe_float((p.get("liquidity") or {}).get("usd")),
                    "volume_24h": safe_float((p.get("volume") or {}).get("h24")),
                    "change_24h": (p.get("priceChange") or {}).get("h24"),
                    "dex": p.get("dexId", "unknown"),
                    "pair_url": p.get("url", "")
                }

                if is_bad_pair(item):
                    continue

                all_pairs.append(item)

        except Exception as e:
            print("Collector URL error:", url, e)

    # إزالة التكرار حسب عنوان التوكن
    best_by_token = {}

    for pair in all_pairs:
        address = pair["address"]

        if address not in best_by_token:
            best_by_token[address] = pair
        elif pair["liquidity"] > best_by_token[address]["liquidity"]:
            best_by_token[address] = pair

    final_pairs = list(best_by_token.values())

    # نرتب حسب النشاط وليس السيولة فقط
    final_pairs.sort(
        key=lambda x: (x["volume_24h"], x["liquidity"]),
        reverse=True
    )

    print("SOLANA MEME PAIRS FOUND:", len(final_pairs))

    return final_pairs[:10]
