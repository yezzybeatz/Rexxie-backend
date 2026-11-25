import os, json, threading, time
from flask import Flask, request, jsonify
from flask_cors import CORS
import websocket

app = Flask(__name__)
CORS(app)

APP_ID = os.environ.get("DERIV_APP_ID", "1089")
TOKEN = os.environ.get("DERIV_TOKEN", "")

def deriv_request(payload):
    # One-shot Deriv WebSocket call
    ws = websocket.create_connection(f"wss://ws.binaryws.com/websockets/v3?app_id={APP_ID}", timeout=20)
    try:
        if TOKEN:
            ws.send(json.dumps({"authorize": TOKEN}))
            auth = json.loads(ws.recv())
            if "error" in auth:
                return {"error": auth["error"]}
        ws.send(json.dumps(payload))
        res = json.loads(ws.recv())
        return res
    finally:
        ws.close()

@app.route("/")
def home():
    return "Rexxie Backend is LIVE - Deriv Connected"

@app.route("/balance")
def balance():
    r = deriv_request({"balance": 1, "account": "all"})
    if "error" in r:
        return jsonify({"error": r["error"]}), 400
    b = r.get("balance", {})
    return jsonify({
        "balance": float(b.get("balance", 0)),
        "currency": b.get("currency", "USD"),
        "loginid": b.get("loginid", "")
    })

@app.route("/trade", methods=["POST"])
def trade():
    d = request.get_json(force=True)
    symbol = d.get("symbol", "R_100")
    contract = d.get("contract_type", "CALL")
    amount = float(d.get("amount", 1))
    duration = int(d.get("duration", 5))
    duration_unit = d.get("duration_unit", "m")
    basis = d.get("basis", "stake")
    currency = d.get("currency", "USD")

    # 1. Get proposal
    prop = deriv_request({
        "proposal": 1,
        "amount": amount,
        "basis": basis,
        "contract_type": contract,
        "currency": currency,
        "duration": duration,
        "duration_unit": duration_unit,
        "symbol": symbol
    })
    if "error" in prop:
        return jsonify({"error": prop["error"]}), 400
    proposal_id = prop["proposal"]["id"]
    # 2. Buy it
    buy = deriv_request({"buy": proposal_id, "price": amount})
    if "error" in buy:
        return jsonify({"error": buy["error"]}), 400
    c = buy.get("buy", {})
    return jsonify({
        "contract_id": c.get("contract_id"),
        "longcode": c.get("longcode", ""),
        "buy_price": c.get("buy_price"),
        "payout": c.get("payout"),
        "balance_after": c.get("balance_after")
    })

@app.route("/positions")
@app.route("/portfolio")
@app.route("/open_positions")
def positions():
    r = deriv_request({"portfolio": 1})
    if "error" in r:
        return jsonify({"error": r["error"]}), 400
    contracts = r.get("portfolio", {}).get("contracts", [])
    out = []
    for c in contracts:
        out.append({
            "contract_id": c.get("contract_id"),
            "symbol": c.get("symbol"),
            "contract_type": c.get("contract_type"),
            "buy_price": c.get("buy_price"),
            "payout": c.get("payout"),
            "profit": c.get("profit"),
            "is_win": 1 if float(c.get("profit", 0) or 0) > 0 else 0
        })
    return jsonify({"open_positions": out, "positions": out})

@app.route("/result/<contract_id>")
def result(contract_id):
    r = deriv_request({"proposal_open_contract": 1, "contract_id": int(contract_id)})
    if "error" in r:
        return jsonify({"error": r["error"]}), 400
    c = r.get("proposal_open_contract", {})
    profit = float(c.get("profit", 0) or 0)
    return jsonify({
        "contract_id": contract_id,
        "profit": profit,
        "is_win": 1 if profit > 0 else 0,
        "status": c.get("status"),
        "is_expired": c.get("is_expired", 0)
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
