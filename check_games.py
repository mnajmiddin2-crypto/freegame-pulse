import os
import re
import json
import html
import requests

RAW_TOKEN = (os.environ.get("BOT_TOKEN") or "").strip()
print("Token uzunligi:", len(RAW_TOKEN), "| Boshlanishi:", RAW_TOKEN[:6])

m = re.search(r"(\d+:[A-Za-z0-9_-]{20,})", RAW_TOKEN)
BOT_TOKEN = m.group(1) if m else RAW_TOKEN

TG_URL = f"https://telegram.org{BOT_TOKEN}"
CHANNEL_ID = "@gametraverse"
DB_FILE = "sent_games.json"

def load_sent():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except Exception:
                return []
    return []

def save_sent(ids):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(ids[-300:], f, indent=2)

def send_tg(chat_id, text, photo=None, url=None):
    markup = json.dumps({"inline_keyboard": [[{"text": "📥 O'yinni ko'rish", "url": url}]]}) if url else None
    if photo:
        data = {"chat_id": chat_id, "photo": photo, "caption": text, "parse_mode": "HTML"}
        if markup:
            data["reply_markup"] = markup
        try:
            r = requests.post(f"{TG_URL}/sendPhoto", data=data, timeout=20)
            if r.status_code == 200:
                return True
        except Exception:
            pass

    data = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if markup:
        data["reply_markup"] = markup
    r = requests.post(f"{TG_URL}/sendMessage", data=data, timeout=20)
    print("Telegram javob:", r.status_code, r.text)
    return r.status_code == 200

def get_rates():
    try:
        r = requests.get("https://er-api.com", timeout=15).json()
        uzs = float(r["rates"]["UZS"])
        rub = float(r["rates"]["RUB"])
        return uzs, uzs / rub
    except Exception:
        return 12800.0, 135.0

def fetch_deals():
    deals = []
    # 1. IsThereAnyDeal / CheapShark ochiq feed (corsproxy.io orqali)
    try:
        target = "https://cheapshark.com"
        r = requests.get(f"https://corsproxy.io?{requests.utils.quote(target)}", timeout=20)
        if r.status_code == 200 and r.text.strip().startswith("["):
            stores = {"1": "Steam", "7": "GOG", "25": "Epic Games Store"}
            for d in r.json():
                steam_id = d.get("steamAppID")
                deals.append({
                    "id": f"cs_{d['dealID']}",
                    "title": d.get("title", "Game"),
                    "desc": f"Steam reytingi: {d.get('steamRatingText', 'Yaxshi')}",
                    "store": stores.get(str(d.get("storeID")), "PC Store"),
                    "orig": float(d.get("normalPrice", 0)),
                    "final": float(d.get("salePrice", 0)),
                    "disc": int(round(float(d.get("savings", 0)))),
                    "image": f"https://steamstatic.com{steam_id}/header.jpg" if steam_id else d.get("thumb", ""),
                    "link": f"https://cheapshark.com{d['dealID']}"
                })
    except Exception as e:
        print("Deals xato:", e)
    return deals

def main():
    if not BOT_TOKEN:
        print("XATO: BOT_TOKEN bo'sh!")
        return

    usd_uzs, rub_uzs = get_rates()
    sent_ids = load_sent()
    deals = fetch_deals()
    print("Topilgan chegirmalar:", len(deals))

    if not deals:
        send_tg(CHANNEL_ID, "✅ <b>PULSE bot @gametraverse kanaliga muvaffaqiyatli ulandi!</b>\nTez orada yangi chegirmalar va bepul o'yinlar chiqadi.")
        return

    updated = False
    count = 0
    for d in deals:
        if d["id"] not in sent_ids:
            uzs_new = f"{int(round(d['final'] * usd_uzs, -2)):,}".replace(",", " ")
            rub_new = f"{int(round((d['final'] * usd_uzs) / rub_uzs)):,}".replace(",", " ")
            uzs_old = f"{int(round(d['orig'] * usd_uzs, -2)):,}".replace(",", " ")

            is_free = d["final"] == 0
            header = "🎁 <b>100% BEPUL O'YIN!</b>" if is_free else f"🔥 <b>KATTA CHEGIRMA (-{d['disc']}%)!</b>"
            price_line = "<b>0$ / 0 so'm / 0 ₽ (BEPUL)</b>" if is_free else (
                f"<b>${d['final']:.2f}</b> | <b>{uzs_new} so'm</b> | <b>{rub_new} ₽</b>"
            )
            msg = (
                f"{header}\n\n"
                f"🎮 <b>{html.escape(d['title'])}</b>\n"
                f"📝 <i>{html.escape(d['desc'])}</i>\n\n"
                f"🏪 <b>Do'kon:</b> {d['store']}\n"
                f"❌ <b>Eski narxi:</b> <s>${d['orig']:.2f} ({uzs_old} so'm)</s>\n"
                f"✅ <b>Yangi narxi:</b> {price_line}\n"
                f"⏳ <b>Muddat:</b> Cheklangan vaqt"
            )
            if send_tg(CHANNEL_ID, msg, d["image"], d["link"]):
                sent_ids.append(d["id"])
                updated = True
                count += 1
                if count >= 5:
                    break

    if updated:
        save_sent(sent_ids)

if __name__ == "__main__":
    main()
