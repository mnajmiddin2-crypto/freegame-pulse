import os
import json
import html
import requests

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL = os.environ.get("CHANNEL", "@gametraverse")
SENT_FILE = "sent_games.json"

def load_sent():
    if os.path.exists(SENT_FILE):
        with open(SENT_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except Exception:
                return []
    return []

def save_sent(data):
    with open(SENT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def get_epic_games():
    url = "https://epicgames.com"
    r = requests.get(url, params={"locale": "en-US", "country": "US", "allowCountries": "US"}, timeout=20)
    r.raise_for_status()
    elements = r.json()["data"]["Catalog"]["searchStore"]["elements"]
    
    games = []
    for el in elements:
        price = (el.get("price") or {}).get("totalPrice") or {}
        if price.get("discountPrice") == 0 and (price.get("originalPrice") or 0) > 0:
            promos = el.get("promotions") or {}
            if promos.get("promotionalOffers"):
                slug = el.get("productSlug") or el.get("urlSlug") or ""
                slug = slug.split("/")
                link = f"https://epicgames.com{slug}" if slug else "https://epicgames.com"
                
                image = ""
                for img in el.get("keyImages") or []:
                    if img.get("type") in ("OfferImageWide", "DieselStoreFrontWide", "Thumbnail"):
                        image = img.get("url")
                        break
                        
                games.append({
                    "id": f"epic_{el['id']}",
                    "title": el.get("title", "O'yin"),
                    "store": "Epic Games Store",
                    "price": f"${price['originalPrice'] / 100:.2f}",
                    "link": link,
                    "image": image
                })
    return games

def send_post(game):
    caption = (
        f"🎁 <b>BEPUL O'YIN!</b>\n\n"
        f"🎮 <b>{html.escape(game['title'])}</b>\n"
        f"🏪 Do'kon: {game['store']}\n"
        f"💰 Narxi: <s>{game['price']}</s> ➡️ <b>BEPUL (0$)</b>"
    )
    markup = json.dumps({
        "inline_keyboard": [[{"text": "🎮 Bepul olish", "url": game["link"]}]]
    })
    
    url = f"https://telegram.org{BOT_TOKEN}/sendPhoto"
    res = requests.post(url, data={
        "chat_id": CHANNEL,
        "photo": game["image"],
        "caption": caption,
        "parse_mode": "HTML",
        "reply_markup": markup
    }, timeout=20).json()
    
    if not res.get("ok"):
        print("Rasm bilan yuborishda xato:", res)
        url_msg = f"https://telegram.org{BOT_TOKEN}/sendMessage"
        res = requests.post(url_msg, data={
            "chat_id": CHANNEL,
            "text": caption,
            "parse_mode": "HTML",
            "reply_markup": markup
        }, timeout=20).json()
        print("Matn bilan yuborish natijasi:", res)
        
    return res.get("ok", False)

def main():
    if not BOT_TOKEN:
        raise ValueError("XATO: GitHub Secrets ichida BOT_TOKEN topilmadi!")
        
    sent = load_sent()
    games = get_epic_games()
    print(f"Topilgan bepul o'yinlar soni: {len(games)}")
    
    for g in games:
        if g["id"] not in sent:
            print(f"Yuborilmoqda: {g['title']}")
            if send_post(g):
                sent.append(g["id"])
                print("Muvaffaqiyatli yuborildi!")
            else:
                print("Yuborib bo'lmadi!")
                
    save_sent(sent)

if __name__ == "__main__":
    main()
