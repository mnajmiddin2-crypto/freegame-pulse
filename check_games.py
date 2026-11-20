import os
import json
import html
import re
import xml.etree.ElementTree as ET
import requests

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID", "@gametraverse")
DB_FILE = "sent_games.json"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; FreeGamePulse/3.0; +https://github.com)"}

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
    # Ochiq va bloklanmaydigan xalqaro valyuta API
    usd_uzs = 12800.0
    rub_uzs = 135.0
    try:
        r = requests.get("https://er-api.com", timeout=15)
        if r.status_code == 200:
            rates = r.json().get("rates", {})
            usd_uzs = float(rates.get("UZS", 12800.0))
            rub_rate = float(rates.get("RUB", 95.0))
            rub_uzs = usd_uzs / rub_rate if rub_rate > 0 else 135.0
    except Exception as e:
        print("Kurs olish xatosi:", e)
    return usd_uzs, rub_uzs

def format_prices(usd_price, usd_uzs, rub_uzs):
    if usd_price <= 0:
        return "<b>0$ / 0 so'm / 0 ₽ (100% BEPUL)</b>"
    uzs = int(round((usd_price * usd_uzs) / 100) * 100)
    rub = int(round((usd_price * usd_uzs) / rub_uzs))
    uzs_str = f"{uzs:,}".replace(",", " ")
    rub_str = f"{rub:,}".replace(",", " ")
    return f"<b>${usd_price:.2f}</b> | <b>{uzs_str} so'm</b> | <b>{rub_str} ₽</b>"

def fetch_deals_rss():
    # Reddit GameDeals RSS — Steam, Epic Games, GOG bepul va chegirmali o'yinlari
    url = "https://reddit.com"
    deals = []
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        print("RSS status:", r.status_code)
        if r.status_code != 200:
            return []

        root = ET.fromstring(r.text)
        ns = {"atom": "http://w3.org"}

        for entry in root.findall("atom:entry", ns):
            entry_id = entry.findtext("atom:id", default="", namespaces=ns)
            raw_title = entry.findtext("atom:title", default="", namespaces=ns)
            content = entry.findtext("atom:content", default="", namespaces=ns)

            # Do'konni aniqlash
            store_match = re.search(r"\[(.*?)\]", raw_title)
            store = store_match.group(1) if store_match else "Game Store"
            if not any(s in store.lower() for s in ("steam", "epic", "gog", "humble", "fanatical", "ubisoft")):
                continue

            # Narx va chegirma foizini matndan ajratish (masalan: $4.99 / 80% off yoki FREE / 100% off)
            is_free = bool(re.search(r"\b(free|100%\s*off|\$0\.00|\$0)\b", raw_title, re.I))
            price_match = re.search(r"\$(\d+(?:\.\d{1,2})?)", raw_title)
            disc_match = re.search(r"(\d{2,3})%\s*off", raw_title, re.I)

            sale_price = 0.0 if is_free else (float(price_match.group(1)) if price_match else None)
            discount = 100 if is_free else (int(disc_match.group(1)) if disc_match else None)

            # Faqat bepul yoki kamida 50% chegirmali o'yinlarni olamiz
            if not is_free and (sale_price is None or (discount is not None and discount < 50)):
                continue

            # Asl do'kon havolasini va rasmni RSS ichidan olish
            link_match = re.search(r'href="(https?://[^"]+)"[^>]*>\[link\]', content)
            game_link = html.unescape(link_match.group(1)) if link_match else ""
            if not game_link:
                link_el = entry.find("atom:link", ns)
                game_link = link_el.attrib.get("href", "") if link_el is not None else ""

            img_match = re.search(r'<img[^>]+src="([^"]+)"', content)
            image = html.unescape(img_match.group(1)) if img_match else ""

            clean_title = re.sub(r"^\[.*?\]\s*", "", raw_title).strip()

            deals.append({
                "id": entry_id,
                "title": clean_title,
                "store": store,
                "sale": sale_price if sale_price is not None else 0.0,
                "discount": discount,
                "image": image,
                "link": game_link
            })
    except Exception as e:
        print("RSS xatosi:", e)
    return deals

def send_post(deal, usd_uzs, rub_uzs):
    is_free = deal["sale"] == 0
    disc_txt = f"-{deal['discount']}%" if deal["discount"] else "CHEGIRMA"
    header = "🎁 <b>100% BEPUL O'YIN!</b>" if is_free else f"🔥 <b>O'YIN CHEGIRMASI ({disc_txt})!</b>"
    btn_text = "📥 Bepul olish" if is_free else "🛒 Sahifaga o'tish"
    price_str = format_prices(deal["sale"], usd_uzs, rub_uzs)

    caption = (
        f"{header}\n\n"
        f"🎮 <b>{html.escape(deal['title'])}</b>\n"
        f"🏪 <b>Do'kon:</b> {html.escape(deal['store'])}\n"
        f"💰 <b>Chegirma narxi:</b> {price_str}\n"
        f"⏳ <b>Muddat:</b> Aksiya tugaguncha (cheklangan vaqt)"
    )
    markup = {"inline_keyboard": [[{"text": btn_text, "url": deal["link"]}]]}

    if deal["image"]:
        res = requests.post(
            f"https://telegram.org{BOT_TOKEN}/sendPhoto",
            data={
                "chat_id": CHANNEL_ID,
                "photo": deal["image"],
                "caption": caption,
                "parse_mode": "HTML",
                "reply_markup": json.dumps(markup)
            },
            timeout=20
        )
        if res.status_code == 200:
            print("Rasm bilan yuborildi:", deal["title"])
            return True

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
    print("Telegram javobi:", res.status_code, res.text)
    return res.status_code == 200

def main():
    if not BOT_TOKEN:
        print("XATO: BOT_TOKEN topilmadi!")
        return

    sent_ids = load_sent()
    usd_uzs, rub_uzs = get_rates()
    print(f"Jonli kurs: 1 USD = {usd_uzs:.2f} UZS | 1 RUB = {rub_uzs:.2f} UZS")

    deals = fetch_deals_rss()
    print(f"Topilgan o'yinlar soni: {len(deals)}")
    updated = False

    count = 0
    for deal in deals:
        if deal["id"] not in sent_ids:
            if send_post(deal, usd_uzs, rub_uzs):
                sent_ids.append(deal["id"])
                updated = True
                count += 1
                if count >= 5:
                    break

    if updated:
        save_sent(sent_ids)
        print("Baza yangilandi.")

if __name__ == "__main__":
    main()
