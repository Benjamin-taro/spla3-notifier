#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
- 今日 19/21/23/01 BST の bankara-open を取得
- 4 枠足りなければ /results の is_fest==true を代わりに表示
- フェス開催中または 48h 前ならヘッダーで告知
"""
import os, requests, pytz, json
from datetime import datetime
from dateutil import tz, parser
from random import choices
import gspread
from google.oauth2.service_account import Credentials
from random import choice
import traceback

# ───────── 定数 ─────────
API_SCHEDULE = "https://spla3.yuu26.com/api/schedule"
API_FEST     = "https://spla3.yuu26.com/api/festivals"
UA           = "Splatoon3Notifier/3.0 (example@mail)"
UK           = pytz.timezone("Europe/London")
NIGHT_HOURS  = {18, 19, 20, 21, 22, 23, 0, 1}             # Adjusted to both BST and GMT
TOKEN        = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
USERS        = os.environ["LINE_USER_IDS"].split(",")
EMOJI = {
    "ガチエリア":"⛳️", "ガチヤグラ":"🗼", "ガチホコバトル":"🐲", "ガチアサリ":"🏉",
    "ナワバリバトル":"🎨", "トリカラバトル":"🇫🇷"
}
GREETINGS = {
    "おはようございます！",
    "今日もいい日になりますよう！！",
    "おはよう！素敵な1日になりますように！",
    "Good morning!",
    "本日も憂鬱な朝がやってきました。",
    "よく眠れましたか？今日も1日フルパワーで！！",
    "おはようございます。今日も一日頑張りましょう。",
    "朝だー！！！目ぇ覚ませーーー！！！",
    "おはよう！！テンションぶち上げてくぞーー！"
}

NO_REPEAT_DAYS = 3
ALPHA = 0.15  # 経過日の影響係数（お好みで調整）

def load_greeting_from_sheet() -> str:
    try:
        raw = os.environ["GOOGLE_SHEETS_CREDENTIALS"]  # Secrets から渡す
        # raw = GOOGLE_SHEETS_CREDENTIALS  # Secrets から渡す
        creds = Credentials.from_service_account_info(
            json.loads(raw),
            #raw,
            scopes=["https://www.googleapis.com/auth/spreadsheets",]
        )
        gc = gspread.authorize(creds)

        sh = gc.open_by_key(os.environ.get("SHEET_ID", ""))
        # sh = gc.open_by_key(SHEET_ID)
        ws = sh.get_worksheet_by_id(int(os.environ.get("SHEET_GID", "0")))
        # B2:D をまとめて取得（[ [msg, count, last], ... ]）
        rows = ws.get("B2:D")  # なくても [] が来る
        today = datetime.now(UK).date()

        candidates = []  # (row_idx, msg, count, days_since, weight)
        for i, r in enumerate(rows, start=2):  # シート行番号は2から
            msg = (r[0] if len(r) >= 1 else "").strip()
            if not msg:
                continue
            # count
            try:
                cnt = int((r[1] if len(r) >= 2 else "").strip() or "0")
            except:
                cnt = 0
            # last_used
            last_raw = (r[2] if len(r) >= 3 else "").strip()
            days_since = 999
            if last_raw:
                try:
                    # "YYYY-MM-DD" 前提。もし時刻付きでも parser でOK
                    d = datetime.fromisoformat(last_raw).date()
                    days_since = (today - d).days
                except Exception:
                    try:
                        d = parser.isoparse(last_raw).date()
                        days_since = (today - d).days
                    except Exception:
                        days_since = 999

            # 直近 NO_REPEAT_DAYS 日は除外
            if days_since < NO_REPEAT_DAYS:
                weight = 0.0
            else:
                # 重み = 回数逆数 × 経過日ボーナス
                # 経過日の上限を軽くかけてもOK（例: min(days_since, 30)）
                weight = (1.0 / (cnt + 1)) * (1.0 + ALPHA * min(days_since, 30))

            candidates.append((i, msg, cnt, days_since, weight))

        # すべて 0 なら、除外条件を外して素直に等確率
        weights = [w for *_, w in candidates]
        if not candidates:
            return "Good morning!"
        if all(w == 0 for w in weights):
            weights = [1.0] * len(candidates)

        # 重み付き抽選
        chosen = choices(candidates, weights=weights, k=1)[0]
        row_idx, msg, cnt, _, _ = chosen

        # 使用回数/最終使用日を更新
        ws.update(f"C{row_idx}:D{row_idx}", [[str(cnt + 1), today.isoformat()]])

        return msg
    except Exception as e:
        print("[WARN] Sheets 読み込み失敗:", repr(e))
        print(traceback.format_exc())
        return "Good morning!"

# ───────── util ─────────
def to_dt(val):
    if isinstance(val, (int, float)):
        return datetime.fromtimestamp(val, tz.UTC)
    try:
        return datetime.fromtimestamp(int(val), tz.UTC)
    except Exception:
        return parser.isoparse(val)

def push(text):
    hdr = {"Authorization": f"Bearer {TOKEN}"}
    body = {"messages":[{"type":"text","text":text}]}
    for uid in USERS:
        body["to"] = uid
        requests.post("https://api.line.me/v2/bot/message/push",
                      json=body, headers=hdr, timeout=10)


def fmt(r: dict) -> str:
    """1 スロット分をテキスト化（UK と日本時間を併記）"""
    JST = pytz.timezone("Asia/Tokyo")
    uk_st, uk_et = r["start"], r["end"]
    jst_st = uk_st.astimezone(JST)
    jst_et = uk_et.astimezone(JST)

    return (
        f"- {uk_st:%m/%d %H:%M}–{uk_et:%H:%M}\n"
        f"- (日本時間 {jst_st:%m/%d %H:%M}–{jst_et:%H:%M})\n"
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
    rows = []  # 抽出結果を格納するリスト
    # ── 1. 今日が週末か判定 ──
    now_uk = datetime.now(UK)
    if now_uk.weekday() >= 5:  # 5=土, 6=日
        hours = {10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 0, 1}
        limit = None
    else:
        hours = NIGHT_HOURS
        limit = 4

    # ① bankara_open
    for s in raw["result"]["bankara_open"]:
        if s["rule"] is None:            # 空スロット無し
            continue
        st = to_dt(s["start_time"]).astimezone(UK)
        # ── ここでデバッグログ ──
        print(f"[DEBUG] bankara slot start={st:%m/%d %H:%M}  hour={st.hour} "
              f"{'OK' if st.hour in hours else 'SKIP'}")
        if st.hour not in hours:
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
        if st.hour not in hours:
            continue
        et   = to_dt(s["end_time"]).astimezone(UK)
        rule = s["rule"]["name"]; icon = EMOJI.get(rule, "")
        a, b = s["stages"]
        rows.append(dict(src="fest", start=st, end=et,
                         rule=rule, icon=icon,
                         stg1=a["name"], stg2=b["name"]))

    # ③ 時刻順で並べ替えて先頭４つだけ返す
    rows.sort(key=lambda r: r["start"])
    return rows if limit is None else rows[:limit]

# ───────── main ─────────
def main():
    raw   = requests.get(API_SCHEDULE, headers={"User-Agent":UA}, timeout=10).json()
    # --- デバッグログ：生 API データ件数を確認
    print(f"[DEBUG] raw bankara_open: {len(raw['result'].get('bankara_open', []))} 件, "
          f"fest: {len(raw['result'].get('fest', []))} 件")
    rows  = pick_rows(raw)
    # --- デバッグログ：フィルタ後の行数を確認
    print(f"[DEBUG] filtered rows: {len(rows)} 件")
    now_uk = datetime.now(UK)

    if not rows:                     # 何も取れなかったときの保険
        body = "該当するローテーションはありません。"
    else:
        body = build_lines(rows)     # 時系列で４つ並んだ本文
    today_str = datetime.now(UK).strftime("%Y/%m/%d")
    if now_uk.weekday() >= 5:  # 5=土, 6=日
        title   = (
            f"【今日({today_str})の\n"
            f"バンカラマッチ(オープン)】🦑\n"
            f"\n"
        )
    else:
        title   = (
            f"【今日({today_str})\n"
            f"19時以降の\n"
            f"バンカラマッチ(オープン)】🦑\n"
            f"\n"
        )
    #greeting = choice(list(GREETINGS)) + "\n"
    greeting = load_greeting_from_sheet() + "\n"
    if now_uk.weekday() >= 5:  # 5=土, 6=日
        greeting = "週末なので1日のスケジュールを通知するよ！" + "\n"
    push(greeting + "\n" + title + body)

if __name__ == "__main__":
    main()
