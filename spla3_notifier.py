#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, requests, datetime, pytz
from dateutil import tz, parser

# ───────── 設定 ─────────
API_SCHEDULE = "https://spla3.yuu26.com/api/schedule"
API_FEST     = "https://spla3.yuu26.com/api/festivals"
UA  = "Splatoon3Notifier/2.1 (email@example.com)"
UK  = pytz.timezone("Europe/London")
HOURS = {19, 21, 23, 1}               # 19 / 21 / 23 / 01 (BST)

TOKEN = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
USERS = os.environ["LINE_USER_IDS"].split(",")

EMOJI = {
    "ガチエリア":"⛳️", "ガチヤグラ":"🚚", "ガチホコバトル":"🐉", "ガチアサリ":"🏉",
    "ナワバリバトル":"🖌️", "トリカラバトル":"🍗"
}

# ───────── util ─────────
def to_dt(v):
    if isinstance(v, (int, float)):
        return datetime.datetime.fromtimestamp(v, tz.UTC)
    try:
        return datetime.datetime.fromtimestamp(int(v), tz.UTC)
    except Exception:
        return parser.isoparse(v)

def push(text):
    hdr = {"Authorization": f"Bearer {TOKEN}"}
    body = {"messages":[{"type":"text","text":text}]}
    for uid in USERS:
        body["to"] = uid
        requests.post("https://api.line.me/v2/bot/message/push",
                      json=body, headers=hdr, timeout=10)

# ───────── バンカラ4枠 ─────────
def pick_bankara(results):
    lines=[]
    for s in results:
        if s.get("category") != "bankara-open":
            continue
        st = to_dt(s["start_time"]).astimezone(UK)
        if st.hour not in HOURS:
            continue
        et = to_dt(s["end_time"]).astimezone(UK)
        rule = s["rule"]["name"]; icon = EMOJI.get(rule,"")
        a,b = s["stages"]
        lines.append(f"- {st:%m/%d %H:%M}–{et:%H:%M}\n"
                     f"  {rule}{icon}\n"
                     f"  {a['name']}\n"
                     f"  {b['name']}\n")
    return "\n".join(lines)

# ───────── フェス ─────────
def build_fest_msg(fest, now_uk):
    st = to_dt(fest["start_time"]).astimezone(UK)
    ed = to_dt(fest["end_time"]).astimezone(UK)
    teams = " vs ".join(t["team_name"] for t in fest["teams"])
    stage = fest["regular_stage"]["name"]
    tri   = fest["tricolor_stage"]["name"]

    head = f"【フェス開催中🎉】\n勢力: {teams}"
    body = (f"ナワバリ{EMOJI['ナワバリバトル']} 会場: {stage}\n"
            f"トリカラ{EMOJI['トリカラバトル']} 会場: {tri}\n"
            f"期間: {st:%m/%d %H:%M} → {ed:%m/%d %H:%M}")
    if now_uk < st:
        head = f"【フェス直前⚡️】\n勢力: {teams}"
        body = (f"開始: {st:%m/%d %H:%M}\n"
                f"メイン会場: {stage}\n"
                f"トリカラ会場: {tri}")
    return head + "\n" + body

def active_fest():
    data = requests.get(API_FEST, headers={"User-Agent": UA}, timeout=10).json()
    fest_list = data.get("festivals") if isinstance(data, dict) else data
    fest_list = fest_list or []               # None 対策
    now = datetime.datetime.utcnow().replace(tzinfo=tz.UTC)
    for f in fest_list:
        st, ed = map(to_dt, (f["start_time"], f["end_time"]))
        if st - datetime.timedelta(days=2) <= now <= ed:
            return f
    return None


# ───────── main ─────────
def main():
    now_uk = datetime.datetime.now(UK)

    fest = active_fest()
    if fest:
        push(build_fest_msg(fest, now_uk))

    raw = requests.get(API_SCHEDULE, headers={"User-Agent": UA}, timeout=10).json()
    if isinstance(raw, list):                 # ← リストならそのまま
        results = raw
    else:                                     # ← dict のときはキーを順番に探索
        results = raw.get("results") \
            or raw.get("data") \
            or raw.get("schedules") \
            or []
    body  = pick_bankara(results)
    title = f"【今日({now_uk:%Y/%m/%d})\n19時以降の\nバンカラマッチ(オープン)】🦑\n\n"
    push(title + (body if body else "フェス開催中/開催前のため\n通常バンカラはありません。"))

if __name__ == "__main__":
    main()
