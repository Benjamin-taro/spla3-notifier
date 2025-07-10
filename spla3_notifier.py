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

EMOJI = {
    "ガチエリア": "⛳️",
    "ガチヤグラ": "🚚",
    "ガチホコバトル": "🐉",   # API によっては “ガチホコ” の表記も
    "ガチアサリ": "🏉",
}


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

        rule = s.get("rule", {}).get("name", "??")
        icon = EMOJI.get(rule, "")
        #stages = ", ".join(t["name"] for t in s["stages"])

        # 1 行目：日付&時間、2 行目：ルール+絵文字+ステージ
        lines.append(
            f"- {st:%m/%d %H:%M}–{et:%H:%M}\n"
            f"  {rule}{icon}\n"
            f"  {s['stages'][0]['name']}\n"
            f"  {s['stages'][1]['name']}\n"
        )
    return "\n".join(lines)


def push(text):
    hdr = {"Authorization": f"Bearer {TOKEN}"}
    for uid in USERS:
        body = {"to": uid, "messages":[{"type":"text","text":text}]}
        requests.post("https://api.line.me/v2/bot/message/push",
                      json=body, headers=hdr, timeout=10)

def main():
    today_str = datetime.datetime.now(UK).strftime("%Y/%m/%d")
    body = pick(fetch())

    text = (
        f"【今日({today_str})\n"
        f"19時以降の\n"
        f"バンカラマッチ(オープン)】🦑\n"
        f"\n"
        f"{body if body else '該当するローテーションはありません'}"
    )
    push(text)

if __name__ == "__main__":
    main()
