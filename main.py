from flask import Flask
from collectors.solana_collector import start

app = Flask(__name__)

@app.route("/")
def home():
    return "Solana Brain is running"

@app.route("/scan")
def scan():
    start()
    return "Scan completed"

if __name__ == "__main__":
    start()
    app.run(host="0.0.0.0", port=10000)
