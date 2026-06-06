import requests

def get_solana_pairs():
    url = "https://api.dexscreener.com/latest/dex/search?q=solana"

    try:
        response = requests.get(url, timeout=15)
        data = response.json()

        pairs = data.get("pairs", [])

        solana_pairs = []
        for p in pairs:
            if p.get("chainId") != "solana":
                continue

            liquidity = p.get("liquidity", {}).get("usd")
            volume_24h = p.get("volume", {}).get("h24")
            change_24h = p.get("priceChange", {}).get("h24")

            if liquidity is None:
                continue

            solana_pairs.append({
                "symbol": p.get("baseToken", {}).get("symbol", "Unknown"),
                "name": p.get("baseToken", {}).get("name", "Unknown"),
                "price": p.get("priceUsd", "N/A"),
                "liquidity": liquidity,
                "volume_24h": volume_24h,
                "change_24h": change_24h
            })

        solana_pairs.sort(key=lambda x: x["liquidity"], reverse=True)
        return solana_pairs[:5]

    except Exception as e:
        print("Collector error:", e)
        return []
