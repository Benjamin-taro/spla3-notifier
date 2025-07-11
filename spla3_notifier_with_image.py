#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, io, base64, datetime, requests, pytz
from PIL import Image, ImageDraw, ImageFont
from dateutil import tz, parser
from pathlib import Path


# ─────────────────── 設定 ───────────────────
API   = "https://spla3.yuu26.com/api/bankara-open/schedule"
UA    = "Splatoon3Notifier/1.0 (email@example.com)"
UK    = pytz.timezone("Europe/London")
HOURS = {19, 21, 23, 1}                        # 対象枠
TOKEN = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
USERS = os.environ["LINE_USER_IDS"].split(",")

# 区分絵文字
EMOJI = {"ガチエリア":"⛳️","ガチヤグラ":"🚚","ガチホコバトル":"🐉","ガチアサリ":"🏉"}

STAGE_IMG = {
    "デカライン高架下": "stage_images/dekaline.png",
    "リュウグウターミナル": "stage_images/ryugu.png",
    "カジキ空港": "stage_images/kajiki.png",
    "バイガイ亭": "stage_images/baigai.jpeg",
    "ネギトロ炭鉱": "stage_images/negitoro.jpeg",
    "タカアシ経済特区": "stage_images/takaashi.png",
    "オヒョウ海運": "stage_images/ohyo.png",
    "タラポートショッピングパーク": "stage_images/tara.png",
    "コンブトラック": "stage_images/konbu.png",
    "ナンプラー遺跡": "stage_images/napura.png",
    "マンタマリア号": "stage_images/manta.png",
    "クサヤ温泉": "stage_images/kusaya.png",
    "ヒラメが丘団地": "stage_images/hirame.png",
    "スメーシーワールド": "stage_images/sumeshi.png",
    "ザトウマーケット": "stage_images/zato.png",
    "チョウザメ造船": "stage_images/chozame.png",
    "海人美術大学": "stage_images/amabi.png",
    "マヒマヒリゾート＆スパ": "stage_images/mahimahi.png",
    "キンメダイ美術館": "stage_images/kinmedai.png",
    "マサバ海峡大橋": "stage_images/masaba.png",
    "ナメロウ金属": "stage_images/namero.png",
    "マテガイ放水路": "stage_images/mategai.png",
    "ヤガラ市場": "stage_images/yagara.png",
    "ゴンズイ地区": "stage_images/gonzui.png",
    "ユノハナ大渓谷": "stage_images/yunohana.png",

}

# Imgur (匿名) アップロード設定
IMGUR_UPLOAD = "https://api.imgur.com/3/image"
IMGUR_HEADER = {"Authorization": "Client-ID 54634b5e34c76a1"}   # 無料 Dev 用

BASE = Path(__file__).resolve().parent
JPFONT = BASE / "fonts/NotoSansJP-Regular.ttf"


    

# ───────────────── 関数群 ─────────────────
def get_font(size):
    try:
        return ImageFont.truetype(str(JPFONT), size)
    except OSError:
        return ImageFont.load_default()

def fetch():
    r = requests.get(API, headers={"User-Agent": UA}, timeout=10)
    r.raise_for_status()
    return r.json()["results"]

def to_dt(val):                                    # epoch/int/ISO を datetime に
    if isinstance(val, (int, float)):
        return datetime.datetime.fromtimestamp(val, tz.UTC)
    try:
        return datetime.datetime.fromtimestamp(int(val), tz.UTC)
    except (ValueError, TypeError):
        return parser.isoparse(val)

def select_slots(results):                         # 夜枠だけ抽出
    slots = []
    for s in results:
        st = to_dt(s["start_time"]).astimezone(UK)
        if st.hour not in HOURS:
            continue
        et = to_dt(s["end_time"]).astimezone(UK)
        s["tstr"] = (st.strftime("%m/%d %H:%M"), et.strftime("%H:%M"))
        slots.append(s)
    return slots

def build_banner(slots, today):                    # Pillow で合成
    W, H = 1280, 720*4 + 180
    base = Image.new("RGB", (W, H), "white")
    draw = ImageDraw.Draw(base)
    font = get_font(48)

    draw.text((40, 40), f"今日({today}) 19時以降のバンカラマッチ(オープン) 🦑",
              fill="black", font=font)
    y = 180

    for s in slots:
        for i, stg in enumerate(s["stages"]):
            img = Image.open(STAGE_IMG[stg["name"]]).resize((640, 360))
            base.paste(img, (i*640, y))
        rule = s["rule"]["name"]; icon = EMOJI.get(rule, "")
        st, et = s["tstr"]
        draw.text((40, y+370), f"{st}–{et}  {rule}{icon}", fill="black", font=font)
        y += 720

    buf = io.BytesIO()
    base.save(buf, format="JPEG", quality=90)
    return buf.getvalue()

def upload_image(img_bytes):                       # Imgur 匿名アップロード
    b64 = base64.b64encode(img_bytes)
    res = requests.post(IMGUR_UPLOAD, headers=IMGUR_HEADER, data={"image": b64})
    res.raise_for_status()
    return res.json()["data"]["link"]

def push_image(url):
    img_msg = {"type":"image","originalContentUrl":url,"previewImageUrl":url}
    hdr = {"Authorization": f"Bearer {TOKEN}"}
    for uid in USERS:
        body = {"to": uid, "messages":[img_msg]}
        requests.post("https://api.line.me/v2/bot/message/push",
                      json=body, headers=hdr, timeout=10)

def push_text(text):                               # エラー時など
    hdr = {"Authorization": f"Bearer {TOKEN}"}
    for uid in USERS:
        body = {"to": uid, "messages":[{"type":"text","text":text}]}
        requests.post("https://api.line.me/v2/bot/message/push",
                      json=body, headers=hdr, timeout=10)

# ────────────────── main ──────────────────
# --- main() の最後を差し替え ---
if __name__ == "__main__":
    today = datetime.datetime.now(UK).strftime("%Y/%m/%d")
    slots = select_slots(fetch())
    if not slots:
        print("夜枠がありません")
        exit()

    banner = build_banner(slots, today)

    # ==== ローカルテスト: 画像を保存して終了 ====
    with open("banner_test.jpg", "wb") as f:
        f.write(banner)
    print("✓ banner_test.jpg を生成しました")
    exit()
