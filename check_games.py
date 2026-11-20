import os
import json
import html
import requests

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID") or "@gametraverse"
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

def get_rates():
    try:
        r = requests.get("https://er-api.com", timeout=15).json()
        uzs = float(r["rates"]["UZS"])
        rub = float(r["rates"]["RUB"])
        return uzs, uzs / rub
    except Exception:
        return 12800.0, 135.0

def send_tg(text, photo=None, url=None):
    markup = json.dumps({"inline_keyboard": [[{"text": "🛒 Sahifaga o'tish", "url": url}]]}) if url else None
    if photo:
        data = {"chat_id": CHANNEL_ID, "photo": photo, "caption": text, "parse_mode": "HTML"}
        if markup:
            data["reply_markup"] = markup
        r = requests.post(f"https://telegram.org{BOT_TOKEN}/sendPhoto", data=data, timeout=20)
        if r.status_code == 200:
            return True

    data = {"chat_id": CHANNEL_ID, "text": text, "parse_mode": "HTML"}
    if markup:
        data["reply_markup"] = markup
    r = requests.post(f"https://telegram.org{BOT_TOKEN}/sendMessage", data=data, timeout=20)
    print("TG javob:", r.status_code, r.text)
    return r.status_code == 200

def fetch_steam_deals():
    # Steam qidiruv API — hech qachon bloklanmaydi
    url = "https://steampowered.com"
    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
    print("Steam status:", r.status_code)
    items = r.json().get("items", [])
    deals = []
    for it in items:
        price_info = it.get("price") or {}
        orig = price_info.get("initial", 0) / 100.0
        final = price_info.get("final", 0) / 100.0
        disc = price_info.get("discount_percent", 0)
        if orig > 0 and (final == 0 or disc >= 50):
            appid = it["id"]
            deals.append({
                "id": f"steam_{appid}",
                "title": it.get("name", "Game"),
                "store": "Steam",
                "orig": orig,
                "final": final,
                "disc": disc,
                "image": it.get("tiny_image", ""),
                "link": f"https://steampowered.com{appid}"
            })
    return deals

def main():
    print("CHANNEL_ID:", CHANNEL_ID)
    print("BOT_TOKEN bormi:", bool(BOT_TOKEN))
    if not BOT_TOKEN:
        print("XATO: BOT_TOKEN kiritilmagan!")
        return

    usd_uzs, rub_uzs = get_rates()
    sent_ids = load_sent()
    deals = fetch_steam_deals()
    print("Topilgan o'yinlar:", len(deals))

    if not deals:
        send_tg("🤖 <b>FreeGame Pulse bot ulandi!</b>\nHozircha yangi katta chegirmalar yo'q, kuzatish davom etmoqda.")
        return

    updated = False
    count = 0
    for d in deals:
        if d["id"] not in sent_ids:
            uzs_new = f"{int(round(d['final'] * usd_uzs, -2)):,}".replace(",", " ")
            rub_new = f"{int(round((d['final'] * usd_uzs) / rub_uzs)):,}".replace(",", " ")
            uzs_old = f"{int(round(d['orig'] * usd_uzs, -2)):,}".replace(",", " ")

            price_line = "<b>0$ / 0 so'm / 0 ₽ (100% BEPUL)</b>" if d["final"] == 0 else (
                f"<b>${d['final']:.2f}</b> | <b>{uzs_new} so'm</b> | <b>{rub_new} ₽</b>"
            )
            msg = (
                f"🔥 <b>O'YIN CHEGIRMASI (-{d['disc']}%)!</b>\n\n"
                f"🎮 <b>{html.escape(d['title'])}</b>\n"
                f"🏪 <b>Do'kon:</b> {d['store']}\n"
                f"❌ <b>Eski narxi:</b> <s>${d['orig']:.2f} ({uzs_old} so'm)</s>\n"
                f"✅ <b>Yangi narxi:</b> {price_line}"
            )
            if send_tg(msg, d["image"], d["link"]):
                sent_ids.append(d["id"])
                updated = True
                count += 1
                if count >= 5:
                    break

    if updated:
        save_sent(sent_ids)

if __name__ == "__main__":
    main()
