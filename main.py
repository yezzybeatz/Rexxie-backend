import os, json
from flask import Flask, request, jsonify
from flask_cors import CORS
import websocket
app = Flask(__name__)
CORS(app)
APP_ID = os.environ.get("DERIV_APP_ID", "1089")
TOKEN = os.environ.get("DERIV_TOKEN", "")
def call(p):
    ws = websocket.create_connection(f"wss://ws.binaryws.com/websockets/v3?app_id={APP_ID}", timeout=20)
    try:
        if TOKEN:
            ws.send(json.dumps({"authorize": TOKEN}))
            a = json.loads(ws.recv())
            if "error" in a:
                return {"error": a["error"]}
        ws.send(json.dumps(p))
        return json.loads(ws.recv())
    finally:
        ws.close()
@app.route("/")
def home():
    return "Rexxie Backend is LIVE - Deriv Connected"
@app.route("/balance")
def balance():
    r = call({"balance": 1, "account": "all"})
    if "error" in r:
        return jsonify({"error": r["error"]}), 400
    b = r.get("balance", {})
    return jsonify({"balance": float(b.get("balance", 0)), "currency": b.get("currency", "USD"), "loginid": b.get("loginid", "")})
@app.route("/trade", methods=["POST"])
def trade():
    d = request.get_json(force=True)
    prop = call({"proposal": 1, "amount": float(d.get("amount", 1)), "basis": "stake", "contract_type": d.get("contract_type", "CALL"), "currency": "USD", "duration": int(d.get("duration", 5)), "duration_unit": "m", "symbol": d.get("symbol", "R_100")})
    if "error" in prop:
        return jsonify({"error": prop["error"]}), 400
    buy = call({"buy": prop["proposal"]["id"], "price": float(d.get("amount", 1))})
    if "error" in buy:
        return jsonify({"error": buy["error"]}), 400
    c = buy.get("buy", {})
    return jsonify({"contract_id": c.get("contract_id"), "buy_price": c.get("buy_price"), "payout": c.get("payout")})
@app.route("/positions")
@app.route("/portfolio")
def positions():
    r = call({"portfolio": 1})
    if "error" in r:
        return jsonify({"error": r["error"]}), 400
    cs = r.get("portfolio", {}).get("contracts", [])
    out = [{"contract_id": x.get("contract_id"), "symbol": x.get("symbol"), "profit": x.get("profit")} for x in cs]
    return jsonify({"open_positions": out, "positions": out})
@app.route("/result/<contract_id>")
def result(contract_id):
    r = call({"proposal_open_contract": 1, "contract_id": int(contract_id)})
    if "error" in r:
        return jsonify({"error": r["error"]}), 400
    c = r.get("proposal_open_contract", {})
    p = float(c.get("profit", 0) or 0)
    return jsonify({"contract_id": contract_id, "profit": p, "is_win": 1 if p > 0 else 0})
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
