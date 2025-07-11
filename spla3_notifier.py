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
    print(f"フェス候補: {len(fest_list)} 件")
    now = datetime.datetime.utcnow().replace(tzinfo=tz.UTC)
    for f in fest_list:
        st, ed = map(to_dt, (f["start_time"], f["end_time"]))
        if st - datetime.timedelta(days=2) <= now <= ed:
            teams = " vs ".join(t["team_name"] for t in f["teams"])
            return f"【フェス開催中🎉】\n勢力: {teams}\n"
    return ""                              # 該当なし

# ───────── ④ メッセージ生成 ─────────
def fmt(r: dict) -> str:
    """1 スロット分をテキスト化"""
    return (
        f"- {r['start']:%m/%d %H:%M}–{r['end']:%H:%M}\n"
        f"  {r['rule']}{r['icon']}\n"
        f"  {r['stg1']}\n"
        f"  {r['stg2']}\n"
    )

def build_lines(rows: list[dict]) -> str:
    if not rows:
        return "該当するローテーションはありません。"

    lines = []

    # ① 全部フェスだけなら先頭にヘッダー
    if all(r["src"] == "fest" for r in rows):
        lines.append("フェス開催中！\n")

    # ② 行を並べつつ境目でアナウンスを挿入
    for i, r in enumerate(rows):
        lines.append(fmt(r))

        # 次があればカテゴリの変わり目をチェック
        if i + 1 < len(rows) and r["src"] != rows[i + 1]["src"]:
            if r["src"] == "bankara":      # bankara → fest
                lines.append("バンカラマッチ終了！\nこれよりフェス開始！\n")
            else:                          # fest → bankara
                lines.append("これにてフェス終了！\n通常通りバンカラマッチ開始！\n")

    return "\n".join(lines)

# ───────── 抽出関数を少し整理 ─────────
def pick_rows(raw):
    """bankara_open と fest を 19/21/23/01 BST だけ抽出して返す"""
    rows = []

    # ① bankara_open
    for s in raw["result"]["bankara_open"]:
        if s["rule"] is None:            # 空スロット無し
            continue
        st = to_dt(s["start_time"]).astimezone(UK)
        if st.hour not in NIGHT_HOURS:
            continue
        et   = to_dt(s["end_time"]).astimezone(UK)
        rule = s["rule"]["name"]; icon = EMOJI.get(rule, "")
        a, b = s["stages"]
        rows.append(dict(src="bankara", start=st, end=et,
                         rule=rule, icon=icon,
                         stg1=a["name"], stg2=b["name"]))

    # ② fest（あれば）
    for s in raw["result"]["fest"]:
        if not s.get("is_fest") or s["rule"] is None:
            continue
        st = to_dt(s["start_time"]).astimezone(UK)
        if st.hour not in NIGHT_HOURS:
            continue
        et   = to_dt(s["end_time"]).astimezone(UK)
        rule = s["rule"]["name"]; icon = EMOJI.get(rule, "")
        a, b = s["stages"]
        rows.append(dict(src="fest", start=st, end=et,
                         rule=rule, icon=icon,
                         stg1=a["name"], stg2=b["name"]))

    # ③ 時刻順で並べ替えて先頭４つだけ返す
    rows.sort(key=lambda r: r["start"])
    return rows[:4]

# ───────── main ─────────
def main():
    raw   = requests.get(API_SCHEDULE, headers={"User-Agent":UA}, timeout=10).json()
    rows  = pick_rows(raw)

    if not rows:                     # 何も取れなかったときの保険
        body = "該当するローテーションはありません。"
    else:
        body = build_lines(rows)     # 時系列で４つ並んだ本文
    today_str = datetime.datetime.now(UK).strftime("%Y/%m/%d")
    title   = (
        f"【今日({today_str})\n"
        f"19時以降の\n"
        f"バンカラマッチ(オープン)】🦑\n"
        f"\n"
    )
    push(title + body)

if __name__ == "__main__":
    main()
