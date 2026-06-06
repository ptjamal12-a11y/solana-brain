import requests

def get_solana_pairs():
    url = "https://api.dexscreener.com/latest/dex/search?q=solana"

    try:
        response = requests.get(url, timeout=15)
        print("Status Code:", response.status_code)

        if response.status_code != 200:
            print("DexScreener error:", response.text[:200])
            return []

        data = response.json()
        pairs = data.get("pairs", [])
        solana_pairs = [p for p in pairs if p.get("chainId") == "solana"]

        return solana_pairs[:5]

    except Exception as e:
        print("Collector error:", e)
        return []


def start():
    pairs = get_solana_pairs()

    print("Solana Collector Started")
    print(f"Found {len(pairs)} Solana pairs")

    for pair in pairs:
        base = pair.get("baseToken", {})
        print(
            base.get("symbol"),
            pair.get("priceUsd"),
            pair.get("liquidity", {}).get("usd")
        )


if __name__ == "__main__":
    start()
