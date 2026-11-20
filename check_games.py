import os
import re
import json
import html
import xml.etree.ElementTree as ET
import requests

RAW_TOKEN = (os.environ.get("BOT_TOKEN") or "").strip()
m = re.search(r"(\d+:[A-Za-z0-9_-]{20,})", RAW_TOKEN)
BOT_TOKEN = m.group(1) if m else RAW_TOKEN

HOST = "api." + "telegram.org"
TG_URL = f"https://{HOST}/bot{BOT_TOKEN}"
CHANNEL_ID = "@gametraverse"
DB_FILE = "sent_games.json"
STATE_FILE = "bot_state.json"

def load_json(path, default):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except Exception:
                return default
    return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def send_tg(chat_id, text, photo=None, url=None, reply_markup=None):
    markup = reply_markup or (
        json.dumps({"inline_keyboard": [[{"text": "📥 O'yinni ko'rish", "url": url}]]}) if url else None
    )
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
    return r.status_code == 200

# 1. Botga shaxsiy chatda yozgan foydalanuvchilarga javob berish (/start, /stop)
def handle_bot_users(state):
    offset = state.get("offset", 0)
    users = state.setdefault("users", [])
    try:
        r = requests.get(f"{TG_URL}/getUpdates", params={"offset": offset, "timeout": 5}, timeout=15).json()
        for upd in r.get("result", []):
            state["offset"] = upd["update_id"] + 1
            msg = upd.get("message") or {}
            cid = msg.get("chat", {}).get("id")
            text = (msg.get("text") or "").strip()
            if not cid:
                continue
            if text == "/stop":
                if cid in users:
                    users.remove(cid)
                send_tg(cid, "🔕 Bildirishnomalar to'xtatildi. Qayta yoqish uchun /start bosing.")
            else:
                if cid not in users:
                    users.append(cid)
                kb = json.dumps({"inline_keyboard": [[{"text": "📢 Kanalga o'tish (@gametraverse)", "url": "https://t.me"}]]})
                send_tg(
                    cid,
                    "👋 <b>Salom! FreeGame Pulse botiga xush kelibsiz!</b>\n\n"
                    "✅ Siz bildirishnomalarga obuna bo'ldingiz.\n"
                    "🎮 Steam, Epic Games va GOG'dagi <b>100% bepul o'yinlar</b> hamda <b>katta chegirmalar</b> (Dollar, So'm va Rublda) har safar yangilanganda sizga ham, @gametraverse kanaliga ham yuboriladi!\n\n"
                    "Bekor qilish: /stop",
                    reply_markup=kb
                )
    except Exception as e:
        print("Bot updates xato:", e)

def get_rates():
    try:
        r = requests.get("https://er-api.com", timeout=15).json()
        uzs = float(r["rates"]["UZS"])
        rub = float(r["rates"]["RUB"])
        return uzs, uzs / rub
    except Exception:
        return 12800.0, 135.0

# 2. GitHub serverlaridan bloklanmaydigan ochiq o'yin chegirmalari feedi (Steam + Epic + GOG)
def fetch_deals():
    deals = []
    headers = {"User-Agent": "python:freegame-pulse:v4.0 (by /u/gametraverse)"}
    feeds = [
        "https://reddit.com",
        "https://reddit.com"
    ]
    ns = {"atom": "http://w3.org"}

    for feed_url in feeds:
        try:
            r = requests.get(feed_url, headers=headers, timeout=20)
            if r.status_code != 200:
                continue
            root = ET.fromstring(r.text)
            for entry in root.findall("atom:entry", ns):
                eid = entry.findtext("atom:id", default="", namespaces=ns)
                title = entry.findtext("atom:title", default="", namespaces=ns)
                content = entry.findtext("atom:content", default="", namespaces=ns)

                if "expired" in title.lower():
                    continue

                store_m = re.search(r"\[(.*?)\]", title)
                store = store_m.group(1) if store_m else "PC Store"
                if not any(s in store.lower() for s in ("steam", "epic", "gog", "humble", "ubisoft")):
                    continue

                is_free = bool(re.search(r"\b(free|100%\s*off|\$0\.00|\$0)\b", title, re.I))
                price_m = re.search(r"\$(\d+(?:\.\d{1,2})?)", title)
                disc_m = re.search(r"(\d{2,3})%\s*off", title, re.I)

                sale = 0.0 if is_free else (float(price_m.group(1)) if price_m else None)
                disc = 100 if is_free else (int(disc_m.group(1)) if disc_m else None)

                if not is_free and (sale is None or (disc is not None and disc < 50)):
                    continue

                link_m = re.search(r'href="(https?://[^"]+)"[^>]*>\[link\]', content)
                link = html.unescape(link_m.group(1)) if link_m else ""
                if not link:
                    continue

                # Steam AppID bo'lsa sifatli katta banner rasm yasaymiz
                steam_m = re.search(r"store\.steampowered\.com/app/(\d+)", link)
                if steam_m:
                    image = f"https://steamstatic.com{steam_m.group(1)}/header.jpg"
                else:
                    img_m = re.search(r'<img[^>]+src="([^"]+)"', content)
                    image = html.unescape(img_m.group(1)) if img_m else ""

                clean_title = re.sub(r"^\[.*?\]\s*(?:\(.*?\)\s*)?", "", title).strip()

                deals.append({
                    "id": eid,
                    "title": clean_title,
                    "store": store,
                    "sale": sale if sale is not None else 0.0,
                    "disc": disc,
                    "image": image,
                    "link": link
                })
        except Exception as e:
            print("Feed xato:", e)
    return deals

def main():
    if not BOT_TOKEN:
        return

    state = load_json(STATE_FILE, {"offset": 0, "users": []})
    handle_bot_users(state)

    usd_uzs, rub_uzs = get_rates()
    sent_ids = load_json(DB_FILE, [])
    deals = fetch_deals()
    print("Topilgan o'yinlar:", len(deals))

    updated = False
    count = 0
    for d in deals:
        if d["id"] not in sent_ids:
            is_free = d["sale"] == 0
            disc_txt = f"-{d['disc']}%" if d["disc"] else "CHEGIRMA"
            header = "🎁 <b>100% BEPUL O'YIN!</b>" if is_free else f"🔥 <b>KATTA CHEGIRMA ({disc_txt})!</b>"

            uzs_new = f"{int(round(d['sale'] * usd_uzs, -2)):,}".replace(",", " ")
            rub_new = f"{int(round((d['sale'] * usd_uzs) / rub_uzs)):,}".replace(",", " ")
            price_line = "<b>0$ / 0 so'm / 0 ₽ (100% BEPUL)</b>" if is_free else (
                f"<b>${d['sale']:.2f}</b> | <b>{uzs_new} so'm</b> | <b>{rub_new} ₽</b>"
            )

            msg = (
                f"{header}\n\n"
                f"🎮 <b>{html.escape(d['title'])}</b>\n"
                f"🏪 <b>Do'kon:</b> {html.escape(d['store'])}\n"
                f"✅ <b>Chegirma narxi:</b> {price_line}\n"
                f"⏳ <b>Muddat:</b> Aksiya tugaguncha (cheklangan vaqt)"
            )
            if send_tg(CHANNEL_ID, msg, d["image"], d["link"]):
                sent_ids.append(d["id"])
                updated = True
                count += 1
                # Obuna bo'lgan bot foydalanuvchilariga ham yuborish
                for uid in list(state.get("users", [])):
                    send_tg(uid, msg, d["image"], d["link"])
                if count >= 5:
                    break

    if updated:
        save_json(DB_FILE, sent_ids[-300:])
    save_json(STATE_FILE, state)

if __name__ == "__main__":
    main()
