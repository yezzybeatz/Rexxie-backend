from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import json
import threading
import time
import websocket

app = Flask(__name__)
CORS(app)

DERIV_APP_ID = os.getenv("DERIV_APP_ID", "1089")
DERIV_TOKEN = os.getenv("DERIV_TOKEN", "")
WS_URL = f"wss://ws.binaryws.com/websockets/v3?app_id={DERIV_APP_ID}"

@app.route("/")
def home():
    return "Rexxie Backend is LIVE - Deriv Connected"

def deriv_call(payload, timeout=15):
    result = {}
    done = threading.Event()
    def on_message(ws, message):
        data = json.loads(message)
        result.update(data)
        if "authorize" in data or "balance" in data or "buy" in data or "error" in data:
            done.set()
    def on_open(ws):
        ws.send(json.dumps(payload))
    ws = websocket.WebSocketApp(WS_URL, on_message=on_message, on_open=on_open)
    t = threading.Thread(target=ws.run_forever, daemon=True)
    t.start()
    done.wait(timeout)
    try:
        ws.close()
    except:
        pass
    return result

@app.route("/balance", methods=["GET"])
def balance():
    if not DERIV_TOKEN:
        return jsonify({"error": "No DERIV_TOKEN set on Render"}), 400
    auth = deriv_call({"authorize": DERIV_TOKEN})
    if "error" in auth:
        return jsonify({"error": auth["error"]}), 400
    bal = deriv_call({"authorize": DERIV_TOKEN, "balance": 1})
    # Second call: authorize then balance in one connection is better, so do combined
    return jsonify(bal)

@app.route("/trade", methods=["POST"])
def trade():
    data = request.json or {}
    symbol = data.get("symbol", "R_100")
    direction = data.get("direction", "CALL")
    stake = float(data.get("stake", 1))
    duration = int(data.get("duration", 5))
    if not DERIV_TOKEN:
        return jsonify({"error": "No DERIV_TOKEN set"}), 400
    # Authorize + Buy in one flow using direct ws
    res = {}
    done = threading.Event()
    def on_message(ws, message):
        d = json.loads(message)
        if "authorize" in d and "error" not in d:
            ws.send(json.dumps({
                "buy": 1,
                "price": stake,
                "parameters": {
                    "amount": stake,
                    "basis": "stake",
                    "contract_type": direction,
                    "currency": "USD",
                    "duration": duration,
                    "duration_unit": "m",
                    "symbol": symbol
                }
            }))
        if "buy" in d or ("error" in d and "authorize" not in d):
            res.update(d)
            done.set()
        if "error" in d and "authorize" in d:
            res.update(d)
            done.set()
    def on_open(ws):
        ws.send(json.dumps({"authorize": DERIV_TOKEN}))
    ws = websocket.WebSocketApp(WS_URL, on_message=on_message, on_open=on_open)
    threading.Thread(target=ws.run_forever, daemon=True).start()
    done.wait(20)
    try:
        ws.close()
    except:
        pass
    return jsonify(res)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
