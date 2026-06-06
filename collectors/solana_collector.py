import requests

DEX_URLS = [
    "https://api.dexscreener.com/latest/dex/search?q=SOL%20USDC",
    "https://api.dexscreener.com/latest/dex/search?q=USDC%20SOL",
    "https://api.dexscreener.com/latest/dex/search?q=pump",
]

def safe_float(value, default=0):
    try:
        if value is None:
            return default
        return float(value)
    except:
        return default

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
                symbol = base.get("symbol", "Unknown")
                name = base.get("name", "Unknown")

                liquidity = safe_float((p.get("liquidity") or {}).get("usd"))
                volume_24h = safe_float((p.get("volume") or {}).get("h24"))
                change_24h = (p.get("priceChange") or {}).get("h24")
                price = p.get("priceUsd")

                if not token_address:
                    continue

                if liquidity <= 0:
                    continue

                all_pairs.append({
                    "address": token_address,
                    "symbol": symbol,
                    "name": name,
                    "price": price,
                    "liquidity": liquidity,
                    "volume_24h": volume_24h,
                    "change_24h": change_24h,
                    "dex": p.get("dexId", "unknown"),
                    "pair_url": p.get("url", "")
                })

        except Exception as e:
            print("Collector URL error:", url, e)

    # إزالة التكرار: نخلي أعلى سيولة لكل توكن
    best_by_token = {}

    for pair in all_pairs:
        address = pair["address"]

        if address not in best_by_token:
            best_by_token[address] = pair
        else:
            if pair["liquidity"] > best_by_token[address]["liquidity"]:
                best_by_token[address] = pair

    final_pairs = list(best_by_token.values())
    final_pairs.sort(key=lambda x: x["liquidity"], reverse=True)

    print("SOLANA PAIRS FOUND:", len(final_pairs))

    return final_pairs[:10]
