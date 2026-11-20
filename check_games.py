import os
import re
import json
import html
import requests

RAW_TOKEN = (os.environ.get("BOT_TOKEN") or "").strip()
# Agar token URL ko'rinishida kiritilgan bo'lsa, faqat haqiqiy token qismini ajratib olamiz
m = re.search(r"(\d+:[A-Za-z0-9_-]+)", RAW_TOKEN)
BOT_TOKEN = m.group(1) if m else RAW_TOKEN

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
            r = requests.post(f"https://telegram.org{BOT_TOKEN}/sendPhoto", data=data, timeout=20)
            if r.status_code == 200:
                return True
        except Exception as e:
            print("sendPhoto err:", e)

    data = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if markup:
        data["reply_markup"] = markup
    r = requests.post(f"https://telegram.org{BOT_TOKEN}/sendMessage", data=data, timeout=20)
    print("Telegram javob:", r.status_code, r.text)
    return r.status_code == 200

def reply_bot_users():
    try:
        r = requests.get(f"https://telegram.org{BOT_TOKEN}/getUpdates", timeout=15).json()
        for upd in r.get("result", []):
            msg = upd.get("message") or {}
            cid = msg.get("chat", {}).get("id")
            if cid:
                send_tg(cid, "👋 <b>Salom! FreeGame Pulse bot faol!</b>\nBarcha bepul o'yinlar va chegirmalar 👉 @gametraverse kanaliga yuborilmoqda.")
                requests.get(f"https://telegram.org{BOT_TOKEN}/getUpdates?offset={upd['update_id'] + 1}", timeout=10)
    except Exception as e:
        print("getUpdates err:", e)

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
    # SteamSpy TOP chegirmalar va bepul o'yinlar
    try:
        r = requests.get("https://steamspy.com", timeout=20)
        if r.status_code == 200 and r.text.strip().startswith("{"):
            data = r.json()
            for appid, info in data.items():
                disc = int(info.get("discount") or 0)
                price_cents = int(info.get("price") or 0)
                init_cents = int(info.get("initialprice") or 0)
                if init_cents > 0 and (price_cents == 0 or disc >= 30):
                    deals.append({
                        "id": f"spy_{appid}_{disc}",
                        "title": info.get("name", "Steam Game"),
                        "desc": f"Developer: {info.get('developer', 'Steam')}",
                        "store": "Steam",
                        "orig": init_cents / 100.0,
                        "final": price_cents / 100.0,
                        "disc": disc if disc > 0 else 100,
                        "image": f"https://steamstatic.com{appid}/header.jpg",
                        "link": f"https://steampowered.com{appid}"
                    })
    except Exception as e:
        print("SteamSpy xato:", e)
    return deals

def main():
    if not BOT_TOKEN:
        print("XATO: BOT_TOKEN topilmadi!")
        return

    reply_bot_users()
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
            desc_line = f"📝 <i>{html.escape(d['desc'])}</i>\n\n" if d.get("desc") else "\n"

            msg = (
                f"{header}\n\n"
                f"🎮 <b>{html.escape(d['title'])}</b>\n"
                f"{desc_line}"
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
