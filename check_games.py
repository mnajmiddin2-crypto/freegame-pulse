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
        r = requests.get("https://er-api.com", timeout=15)
        if r.status_code == 200 and r.text.strip():
            data = r.json()
            uzs = float(data["rates"]["UZS"])
            rub = float(data["rates"]["RUB"])
            return uzs, uzs / rub
    except Exception:
        pass
    return 12800.0, 135.0

def send_tg(text, photo=None, url=None):
    markup = json.dumps({"inline_keyboard": [[{"text": "📥 O'yinni olish", "url": url}]]}) if url else None
    if photo:
        data = {"chat_id": CHANNEL_ID, "photo": photo, "caption": text, "parse_mode": "HTML"}
        if markup:
            data["reply_markup"] = markup
        try:
            r = requests.post(f"https://telegram.org{BOT_TOKEN}/sendPhoto", data=data, timeout=20)
            if r.status_code == 200:
                return True
        except Exception:
            pass

    data = {"chat_id": CHANNEL_ID, "text": text, "parse_mode": "HTML"}
    if markup:
        data["reply_markup"] = markup
    r = requests.post(f"https://telegram.org{BOT_TOKEN}/sendMessage", data=data, timeout=20)
    print("Telegram javob:", r.status_code, r.text)
    return r.status_code == 200

def fetch_games():
    deals = []

    # 1. Epic Games Store (nomi, rasmi, tavsifi, narxi bilan)
    try:
        epic_api = "https://epicgames.com"
        proxy_url = f"https://allorigins.win{requests.utils.quote(epic_api)}"
        r = requests.get(proxy_url, timeout=25)
        if r.status_code == 200 and r.text.strip().startswith("{"):
            elements = r.json()["data"]["Catalog"]["searchStore"]["elements"]
            for el in elements:
                price = (el.get("price") or {}).get("totalPrice") or {}
                orig = price.get("originalPrice") or 0
                disc = price.get("discountPrice")
                if orig > 0 and disc == 0:
                    slug = el.get("productSlug") or el.get("urlSlug") or ""
                    for m in (el.get("catalogNs") or {}).get("mappings") or []:
                        if m.get("pageSlug"):
                            slug = m["pageSlug"]
                            break
                    slug = slug.split("/")
                    image = ""
                    for img in el.get("keyImages") or []:
                        if img.get("type") in ("OfferImageWide", "DieselStoreFrontWide", "Thumbnail"):
                            image = img.get("url", "")
                            break
                    desc = (el.get("description") or "").strip()
                    if len(desc) > 180:
                        desc = desc[:177] + "..."

                    deals.append({
                        "id": f"epic_{el['id']}",
                        "title": el.get("title", "Epic Game"),
                        "desc": desc,
                        "store": "Epic Games Store",
                        "orig": orig / 100.0,
                        "final": 0.0,
                        "disc": 100,
                        "image": image,
                        "link": f"https://epicgames.com{slug}" if slug else "https://epicgames.com"
                    })
    except Exception as e:
        print("Epic xato:", e)

    # 2. Steam, GOG, Epic chegirmalari (CheapShark orqali)
    try:
        cs_api = "https://cheapshark.com"
        proxy_cs = f"https://allorigins.win{requests.utils.quote(cs_api)}"
        r = requests.get(proxy_cs, timeout=25)
        if r.status_code == 200 and r.text.strip().startswith("["):
            stores = {"1": "Steam", "7": "GOG", "25": "Epic Games Store"}
            for d in r.json():
                steam_id = d.get("steamAppID")
                rating = d.get("steamRatingText") or ""
                rating_pct = d.get("steamRatingPercent") or ""
                desc = f"Steam reytingi: {rating} ({rating_pct}% ijobiy baho)" if rating else ""

                deals.append({
                    "id": f"cs_{d['dealID']}",
                    "title": d.get("title", "Game"),
                    "desc": desc,
                    "store": stores.get(str(d.get("storeID")), "PC Store"),
                    "orig": float(d.get("normalPrice", 0)),
                    "final": float(d.get("salePrice", 0)),
                    "disc": int(round(float(d.get("savings", 0)))),
                    "image": f"https://steamstatic.com{steam_id}/header.jpg" if steam_id else d.get("thumb", ""),
                    "link": f"https://cheapshark.com{d['dealID']}"
                })
    except Exception as e:
        print("CheapShark xato:", e)

    return deals

def main():
    if not BOT_TOKEN:
        print("XATO: BOT_TOKEN yo'q!")
        return

    usd_uzs, rub_uzs = get_rates()
    sent_ids = load_sent()
    deals = fetch_games()
    print("Topilgan o'yinlar:", len(deals))

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
