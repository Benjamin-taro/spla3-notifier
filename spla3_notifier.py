#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
- 今日 19/21/23/01 BST の bankara-open を取得
- 4 枠足りなければ /results の is_fest==true を代わりに表示
- フェス開催中または 48h 前ならヘッダーで告知
"""
import os, requests, datetime, pytz
from dateutil import tz, parser

# ───────── 定数 ─────────
API_SCHEDULE = "https://spla3.yuu26.com/api/schedule"
API_FEST     = "https://spla3.yuu26.com/api/festivals"
UA           = "Splatoon3Notifier/3.0 (example@mail)"
UK           = pytz.timezone("Europe/London")
NIGHT_HOURS  = {19, 21, 23, 1}             # BST
TOKEN        = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
USERS        = os.environ["LINE_USER_IDS"].split(",")

EMOJI = {
    "ガチエリア":"⛳️", "ガチヤグラ":"🚚", "ガチホコバトル":"🐉", "ガチアサリ":"🏉",
    "ナワバリバトル":"🖌️", "トリカラバトル":"🍗"
}

# ───────── util ─────────
def to_dt(val):
    if isinstance(val, (int, float)):
        return datetime.datetime.fromtimestamp(val, tz.UTC)
    try:
        return datetime.datetime.fromtimestamp(int(val), tz.UTC)
    except Exception:
        return parser.isoparse(val)

def push(text):
    hdr = {"Authorization": f"Bearer {TOKEN}"}
    body = {"messages":[{"type":"text","text":text}]}
    for uid in USERS:
        body["to"] = uid
        requests.post("https://api.line.me/v2/bot/message/push",
                      json=body, headers=hdr, timeout=10)

# ───────── ① bankara-open 抽出 ─────────
def night_bankara(slots):
    out = []
    for s in slots:                        # list(dict)
        st = to_dt(s["start_time"]).astimezone(UK)
        if st.hour not in NIGHT_HOURS:
            continue
        et = to_dt(s["end_time"]).astimezone(UK)
        rule = s["rule"]["name"]; icon = EMOJI.get(rule,"")
        a,b = s["stages"]
        out.append(dict(
            start=st, end=et, rule=rule, icon=icon,
            stg1=a["name"], stg2=b["name"]
        ))
    return out

# ───────── ② フェス枠抽出 ─────────
def night_fest(slots):
    out = []
    for s in slots:
        if not s.get("is_fest"):          # is_fest==true
            continue
        if s["rule"] is None:             # 開催前の空白枠は除外
            continue
        st = to_dt(s["start_time"]).astimezone(UK)
        if st.hour not in NIGHT_HOURS:
            continue
        et = to_dt(s["end_time"]).astimezone(UK)
        rule = s["rule"]["name"]; icon = EMOJI.get(rule,"")
        a,b = s["stages"]
        out.append(dict(
            start=st, end=et, rule=rule, icon=icon,
            stg1=a["name"], stg2=b["name"]
        ))
    return out

# ───────── ③ フェス開催判定 ─────────
def fest_header():
    data = requests.get(API_FEST, headers={"User-Agent":UA}, timeout=10).json()
    # data  → list だったらそのまま
    if isinstance(data, list):
        fest_list = data
    # data["festivals"] 直下に配列があるパターン
    elif "festivals" in data:
        fest_list = data["festivals"]
    # data["result"]["festivals"] になっている標準パターン
    elif "result" in data and "festivals" in data["result"]:
        fest_list = data["result"]["festivals"]
    else:
        fest_list = []
    now = datetime.datetime.utcnow().replace(tzinfo=tz.UTC)
    for f in fest_list:
        st, ed = map(to_dt, (f["start_time"], f["end_time"]))
        if st - datetime.timedelta(days=2) <= now <= ed:
            teams = " vs ".join(t["team_name"] for t in f["teams"])
            return f"【フェス開催中🎉】\n勢力: {teams}\n"
    return ""                              # 該当なし

# ───────── ④ メッセージ生成 ─────────
def build_lines(rows):
    lines=[]
    for r in rows:
        lines.append(
            f"- {r['start']:%m/%d %H:%M}–{r['end']:%H:%M}\n"
            f"  {r['rule']}{r['icon']}\n"
            f"  {r['stg1']}\n"
            f"  {r['stg2']}\n"
        )
    return "\n".join(lines)

# ───────── main ─────────
def main():
    now_uk = datetime.datetime.now(UK)
    raw    = requests.get(API_SCHEDULE, headers={"User-Agent":UA}, timeout=10).json()
    slots  = raw["result"]["bankara_open"]      # dict 構造は固定

    bankara_rows = night_bankara(slots)
    if len(bankara_rows) == 4:                  # 4 枠そろった
        body = build_lines(bankara_rows)
    else:                                       # 不足 ⇒ フェス枠で置換
        fest_rows = night_fest(raw["result"]["fest"])
        body      = build_lines(fest_rows) if fest_rows else ""
        if not body:
            body = "該当するローテーションはありません。"
        bankara_rows = night_bankara(slots)

    if bankara_rows:                          # 1 件でも取れたらとりあえず出す
        body = build_lines(bankara_rows)
        if len(bankara_rows) < 4 and len(fest_rows) > 0:
            body += "\n"+"バンカラマッチ終了！"+ "\n"+"これよりフェス開始！"+ "\n"
        elif len(bankara_rows) == 0:
            body += "\n""フェス開催中！" 

        # 足りなかったぶんだけフェスで補完したい場合は ↓ を有効に
        if len(bankara_rows) < 4:
            fest_rows = night_fest(raw["result"]["fest"])
            body += ("\n" + build_lines(fest_rows[:4-len(bankara_rows)])) if fest_rows else ""

    else:                                     # まったく取れない ⇒ フェス or なし
        fest_rows = night_fest(raw["result"]["fest"])
        body = build_lines(fest_rows) if fest_rows else "該当するローテーションはありません"
    

    header  = fest_header()                     # 開催なら付加
    today_str = datetime.datetime.now(UK).strftime("%Y/%m/%d")
    title   = (
        f"【今日({today_str})\n"
        f"19時以降の\n"
        f"バンカラマッチ(オープン)】🦑\n"
        f"\n"
    )
    push(title + header + body)

if __name__ == "__main__":
    main()
