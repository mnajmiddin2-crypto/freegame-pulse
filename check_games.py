import os
import json
import html
from datetime import datetime, timezone
import requests

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID", "@gametraverse")
DB_FILE = "sent_games.json"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0"}

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
        json.dump(ids, f, indent=2)

def fetch_epic():
    url = "https://epicgames.com"
    games = []
    try:
        r = requests.get(url, headers=HEADERS, timeout=25)
        data = r.json()
        elements = data["data"]["Catalog"]["searchStore"]["elements"]
        now = datetime.now(timezone.utc)

        for el in elements:
            promos = el.get("promotions") or {}
            active = False
            end_str = "Cheklangan muddat"
            for block in promos.get("promotionalOffers") or []:
                for offer in block.get("promotionalOffers") or []:
                    s = datetime.fromisoformat(offer["startDate"].replace("Z", "+00:00"))
                    e = datetime.fromisoformat(offer["endDate"].replace("Z", "+00:00"))
                    if s <= now <= e:
                        active = True
                        end_str = e.strftime("%d.%m.%Y %H:%M UTC")
            if not active:
                continue

            price = (el.get("price") or {}).get("totalPrice") or {}
            orig = price.get("originalPrice") or 0
            if price.get("discountPrice") != 0 or orig <= 0:
                continue

            slug = el.get("productSlug") or ""
            if not slug:
                for m in (el.get("catalogNs") or {}).get("mappings") or []:
                    if m.get("pageSlug"):
                        slug = m["pageSlug"]
                        break
            if not slug:
                slug = el.get("urlSlug") or ""
            slug = slug.split("/")[0]
            link = f"https://epicgames.com{slug}" if slug else "https://epicgames.com"

            image = ""
            for img in el.get("keyImages") or []:
                if img.get("type") in ("OfferImageWide", "DieselStoreFrontWide", "Thumbnail"):
                    image = img.get("url", "")
                    break

            games.append({
                "id": f"epic_{el['id']}",
                "title": el.get("title", "Unknown"),
                "store": "Epic Games Store",
                "worth": f"${orig / 100:.2f}",
                "end": end_str,
                "image": image,
                "link": link
            })
    except Exception as e:
        print("Epic API xatosi:", e)
    return games

def fetch_steam():
    url = "https://steampowered.com"
    games = []
    try:
        r = requests.get(url, headers=HEADERS, timeout=25)
        data = r.json()
        items = (data.get("specials") or {}).get("items") or []
        for it in items:
            if it.get("discount_percent") == 100 and it.get("final_price") == 0 and (it.get("original_price") or 0) > 0:
                appid = it["id"]
                games.append({
                    "id": f"steam_{appid}",
                    "title": it.get("name", "Unknown"),
                    "store": "Steam",
                    "worth": f"${it['original_price'] / 100:.2f}",
                    "end": "Cheklangan muddat",
                    "image": it.get("large_capsule_image") or it.get("header_image", ""),
                    "link": f"https://steampowered.com{appid}"
                })
    except Exception as e:
        print("Steam API xatosi:", e)
    return games

def send_post(game):
    caption = (
        f"🎁 <b>BEPUL O'YIN!</b>\n\n"
        f"🎮 <b>{html.escape(game['title'])}</b>\n"
        f"🏪 <b>Do'kon:</b> {game['store']}\n"
        f"💰 <b>Narxi:</b> <s>{game['worth']}</s> ➡️ <b>0$ (BEPUL)</b>\n"
        f"⏳ <b>Muddat:</b> {game['end']}"
    )
    markup = {"inline_keyboard": [[{"text": "📥 Bepul olish", "url": game["link"]}]]}

    if game["image"]:
        res = requests.post(
            f"https://telegram.org{BOT_TOKEN}/sendPhoto",
            data={
                "chat_id": CHANNEL_ID,
                "photo": game["image"],
                "caption": caption,
                "parse_mode": "HTML",
                "reply_markup": json.dumps(markup)
            },
            timeout=20
        )
        if res.status_code == 200:
            print("Yuborildi:", game["title"])
            return True
        print("sendPhoto xato:", res.text)

    res = requests.post(
        f"https://telegram.org{BOT_TOKEN}/sendMessage",
        data={
            "chat_id": CHANNEL_ID,
            "text": caption,
            "parse_mode": "HTML",
            "reply_markup": json.dumps(markup)
        },
        timeout=20
    )
    print("sendMessage:", game["title"], res.status_code, res.text)
    return res.status_code == 200

def main():
    if not BOT_TOKEN:
        print("XATO: BOT_TOKEN kiritilmagan!")
        return

    sent_ids = load_sent()
    games = fetch_epic() + fetch_steam()
    print(f"Topilgan bepul o'yinlar soni: {len(games)}")
    updated = False

    for game in games:
        if game["id"] not in sent_ids:
            if send_post(game):
                sent_ids.append(game["id"])
                updated = True

    if updated:
        save_sent(sent_ids)
        print("Baza yangilandi.")

if __name__ == "__main__":
    main()
