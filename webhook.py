#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LINE Webhook で userId を収集するだけの超簡易スクリプト
"""
import os, hmac, hashlib, base64, json
from flask import Flask, request, abort

app = Flask(__name__)
CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")  # 必ず環境変数で渡す

def verify(signature, body):
    """x-line-signature を検証（推奨）"""
    digest = hmac.new(CHANNEL_SECRET.encode(), body, hashlib.sha256).digest()
    expected = base64.b64encode(digest).decode()
    return hmac.compare_digest(expected, signature)

@app.route("/webhook", methods=["POST"])
def webhook():
    # 署名チェック
    signature = request.headers.get("X-Line-Signature", "")
    body      = request.get_data()           # bytes
    if not verify(signature, body):
        abort(400, "Bad signature")

    data = json.loads(body.decode())
    for event in data.get("events", []):
        src = event.get("source", {})
        if src.get("type") == "user":
            user_id = src.get("userId")
            print(f">>> New userId: {user_id}")
            # 好きな保存先に追記（例: ローカルファイル）
            with open("user_ids.txt", "a") as f:
                f.write(user_id + "\n")
    return "OK", 200

if __name__ == "__main__":
    app.run(port=8000)
