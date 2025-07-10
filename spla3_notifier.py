#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, requests, datetime, pytz
from dateutil import tz, parser   # ← 追加：ISO 時間文字列をパース

API   = "https://spla3.yuu26.com/api/bankara-open/schedule"
UA    = "Splatoon3Notifier/1.0 (email@example.com)"
UK    = pytz.timezone("Europe/London")
HOURS = {19, 21, 23, 1}            # 19:00 以降の 4 スロット (BST)

TOKEN = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
USERS = os.environ["LINE_USER_IDS"].split(",")

def fetch():
    r = requests.get(API, headers={"User-Agent": UA}, timeout=10)
    r.raise_for_status()
    return r.json()["results"]

def to_dt(val):
    """epoch(int/str) でも ISO-8601 でも datetime を返す"""
    if isinstance(val, (int, float)):
        return datetime.datetime.fromtimestamp(val, tz.UTC)
    try:
        return datetime.datetime.fromtimestamp(int(val), tz.UTC)
    except (ValueError, TypeError):
        return parser.isoparse(val)    # ← ここで ISO を処理

def pick(slots):
    lines = []
    for s in slots:
        st = to_dt(s["start_time"]).astimezone(UK)
        if st.hour not in HOURS:
            continue
        et = to_dt(s["end_time"]).astimezone(UK)
        rule   = s.get("rule", {}).get("name", "??")
        stages = ", ".join(t["name"] for t in s["stages"])
        lines.append(f"{st:%m/%d %H:%M}–{et:%H:%M}  {rule}: {stages}")
    return "\n".join(lines)

def push(text):
    hdr = {"Authorization": f"Bearer {TOKEN}"}
    for uid in USERS:
        body = {"to": uid, "messages":[{"type":"text","text":text}]}
        requests.post("https://api.line.me/v2/bot/message/push",
                      json=body, headers=hdr, timeout=10)

def main():
    msg = pick(fetch())
    push("【今日19時以降のバンカラマッチ(オープン)】\n" + msg if msg else
         "本日19時以降のバンカラマッチ(オープン)はありません")

if __name__ == "__main__":
    main()
