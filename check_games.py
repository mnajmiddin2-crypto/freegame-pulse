import os
import json
import html
from datetime import datetime, timezone, timedelta
import requests

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID", "@gametraverse")
DB_FILE = "sent_games.json"
HEADERS = {"User-Agent": "FreeGamePulseBot/2.0"}
TZ = timezone(timedelta(hours=5))  # Toshkent vaqti (UTC+5)

STORES = {
    "1": "Steam",
    "7": "GOG",
    "25": "Epic Games Store"
}

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
    # O'zbekiston Markaziy bankidan jonli USD va RUB kurslarini olish
    usd_uzs = 12800.0
    rub_uzs = 135.0
    try:
        r = requests.get("https://cbu.uz", timeout=15)
        if r.status_code == 200:
            for item in r.json():
                if item.get("Ccy") == "USD":
                    usd_uzs = float(item["Rate"])
                elif item.get("Ccy") == "RUB":
                    rub_uzs = float(item["Rate"])
    except Exception as e:
        print("Valyuta kursi xatosi (standart kurs ishlatiladi):", e)
    return usd_uzs, rub_uzs

def format_prices(usd_price, usd_uzs, rub_uzs):
    if usd_price <= 0:
        return "<b>0$ / 0 so'm / 0 ₽ (100% BEPUL)</b>"
    uzs = int(round((usd_price * usd_uzs) / 100) * 100)
    rub = int(round((usd_price * usd_uzs) / rub_uzs))
    uzs_str = f"{uzs:,}".replace(",", " ")
    rub_str = f"{rub:,}".replace(",", " ")
    return f"<b>${usd_price:.2f}</b> | <b>{uzs_str} so'm</b> | <b>{rub_str} ₽</b>"

def fetch_deals():
    # Steam (1), GOG (7), Epic Games (25) — kamida 75% chegirmali o'yinlar
    url = "https://cheapshark.com"
    deals = []
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        if r.status_code != 200:
            print("CheapShark status:", r.status_code)
            return []
        for d in r.json():
            deal_id = d.get("dealID")
            title = d.get("title", "Unknown")
            store_id = str(d.get("storeID", ""))
            store_name = STORES.get(store_id, "PC Store")
            sale_price = float(d.get("salePrice", 0))
            normal_price = float(d.get("normalPrice", 0))
            savings = int(round(float(d.get("savings", 0))))
            thumb = d.get("thumb", "")
            steam_id = d.get("steamAppID")

            # Yuqori sifatli rasm olish (Steam bo'lsa katta banner, aks holda thumb)
            image = f"https://steamstatic.com{steam_id}/header.jpg" if steam_id else thumb
            link = f"https://cheapshark.com{deal_id}"

            deals.append({
                "id": f"deal_{deal_id}",
                "title": title,
                "store": store_name,
                "sale": sale_price,
                "normal": normal_price,
                "savings": savings,
                "image": image,
                "link": link
            })
    except Exception as e:
        print("Deals API xatosi:", e)
    return deals

def send_post(deal, usd_uzs, rub_uzs):
    is_free = deal["sale"] == 0
    header = "🎁 <b>100% BEPUL O'YIN!</b>" if is_free else f"🔥 <b>KATTA CHEGIRMA (-{deal['savings']}%)!</b>"
    btn_text = "📥 Bepul olish" if is_free else "🛒 Chegirmada olish"

    old_price_str = format_prices(deal["normal"], usd_uzs, rub_uzs).replace("<b>", "").replace("</b>", "")
    new_price_str = format_prices(deal["sale"], usd_uzs, rub_uzs)

    caption = (
        f"{header}\n\n"
        f"🎮 <b>{html.escape(deal['title'])}</b>\n"
        f"🏪 <b>Do'kon:</b> {deal['store']}\n"
        f"📉 <b>Chegirma:</b> -{deal['savings']}%\n\n"
        f"❌ <b>Eski narxi:</b> <s>{old_price_str}</s>\n"
        f"✅ <b>Yangi narxi:</b> {new_price_str}\n\n"
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
            print("Yuborildi:", deal["title"])
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
    print("Matn yuborildi:", deal["title"], res.status_code)
    return res.status_code == 200

def main():
    if not BOT_TOKEN:
        print("XATO: BOT_TOKEN topilmadi!")
        return

    sent_ids = load_sent()
    usd_uzs, rub_uzs = get_rates()
    print(f"Kurs: 1 USD = {usd_uzs} UZS | 1 RUB = {rub_uzs} UZS")

    deals = fetch_deals()
    print(f"Topilgan chegirmalar soni: {len(deals)}")
    updated = False

    # Birinchi ishga tushganda kanal to'lib ketmasligi uchun eng sara 5 tasini yuboramiz
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
