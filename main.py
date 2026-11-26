import os, json, traceback
from flask import Flask, request, jsonify
from flask_cors import CORS
import websocket
app = Flask(__name__)
CORS(app)
APP_ID = os.environ.get("DERIV_APP_ID", "1089")
TOKEN = os.environ.get("DERIV_TOKEN", "")
def call(p):
    try:
        ws = websocket.create_connection(f"wss://ws.deriv.com/websockets/v3?app_id={APP_ID}", timeout=15, header=["User-Agent: Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15", "Origin: https://app.deriv.com"])
        try:
            if TOKEN:
                ws.send(json.dumps({"authorize": TOKEN}))
                a = json.loads(ws.recv())
                if "error" in a:
                    return {"error": a["error"]}
            ws.send(json.dumps(p))
            # Deriv sometimes sends ping/extra messages first - keep reading until we get our answer
            for _ in range(5):
                r = json.loads(ws.recv())
                if "error" in r or "balance" in r or "buy" in r or "proposal" in r or "portfolio" in r or "proposal_open_contract" in r:
                    return r
            return r
        finally:
            ws.close()
    except Exception as e:
        return {"error": {"message": str(e)}}
@app.route("/")
def home():
    return "Rexxie Backend is LIVE - Deriv Connected"
@app.route("/balance")
def balance():
    try:
        r = call({"balance": 1})
        if "error" in r:
            return jsonify({"balance": 0, "currency": "USD", "error": r["error"]})
        b = r.get("balance", {})
        return jsonify({"balance": float(b.get("balance", 0)), "currency": b.get("currency", "USD"), "loginid": b.get("loginid", "")})
    except Exception as e:
        return jsonify({"balance": 0, "error": str(e)})
@app.route("/trade", methods=["POST"])
def trade():
    try:
        d = request.get_json(force=True)
        prop = call({"proposal": 1, "amount": float(d.get("amount", 1)), "basis": "stake", "contract_type": d.get("contract_type", "CALL"), "currency": "USD", "duration": int(d.get("duration", 5)), "duration_unit": "m", "symbol": d.get("symbol", "R_100")})
        if "error" in prop:
            return jsonify({"error": prop["error"]}), 400
        buy = call({"buy": prop["proposal"]["id"], "price": float(d.get("amount", 1))})
        if "error" in buy:
            return jsonify({"error": buy["error"]}), 400
        c = buy.get("buy", {})
        return jsonify({"contract_id": c.get("contract_id"), "buy_price": c.get("buy_price"), "payout": c.get("payout")})
    except Exception as e:
        return jsonify({"error": str(e)}), 400
@app.route("/positions")
@app.route("/portfolio")
def positions():
    r = call({"portfolio": 1})
    if "error" in r:
        return jsonify({"open_positions": [], "positions": [], "error": r["error"]})
    cs = r.get("portfolio", {}).get("contracts", [])
    out = [{"contract_id": x.get("contract_id"), "symbol": x.get("symbol"), "profit": x.get("profit")} for x in cs]
    return jsonify({"open_positions": out, "positions": out})
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
