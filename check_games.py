import json, os, re, urllib.request

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHANNEL_ID = "@gametraverse"
STATE_FILE = "sent_games.json"

def load_sent():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return set(json.load(f))
    return set()

def save_sent(sent):
    with open(STATE_FILE, "w") as f:
        json.dump(sorted(list(sent)), f, indent=2)

def fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))

def send_telegram(title, platform, end_date, image, open_url):
    caption = (
        f"🔥 <b>YANGI BEPUL O‘YIN!</b>\n\n"
        f"🎮 <b>Nomi:</b> {title}\n"
        f"🖥 <b>Platforma:</b> {platform}\n"
        f"⏳ <b>Muddati:</b> {end_date}\n\n"
        f"👇 Hoziroq kutubxonangizga qo‘shib oling!"
    )
    payload = {
        "chat_id": CHANNEL_ID,
        "photo": image,
        "caption": caption,
        "parse_mode": "HTML",
        "reply_markup": {"inline_keyboard": [[{"text": "🎮 O‘yinni olish", "url": open_url}]]}
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"https://telegram.org{BOT_TOKEN}/sendPhoto",
        data=data,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        print("Yuborildi:", title, r.status)

def main():
    sent = load_sent()
    changed = False

    # 1. Epic Games Store
    try:
        epic = fetch_json("https://epicgames.com")
        for g in epic["data"]["Catalog"]["searchStore"]["elements"]:
            offers = (g.get("promotions") or {}).get("promotionalOffers") or []
            if not offers:
                continue
            end = next((o["endDate"][:10] for grp in offers for o in grp.get("promotionalOffers", []) if o.get("discountSetting", {}).get("discountPercentage") == 0), None)
            if not end:
                continue
            gid = f"epic_{g['id']}"
            if gid in sent:
                continue
            img = next((i["url"] for i in g.get("keyImages", []) if i.get("type") in ("OfferImageWide", "Thumbnail")), "")
            mappings = (g.get("catalogNs") or {}).get("mappings") or []
            slug = mappings.get("pageSlug") if mappings else g.get("productSlug")
            url = f"https://epicgames.com{slug}" if slug else "https://epicgames.com"
            send_telegram(g["title"], "Epic Games Store", end, img, url)
            sent.add(gid)
            changed = True
    except Exception as e:
        print("Epic xato:", e)

    # 2. Steam 100% chegirma
    try:
        steam = fetch_json("https://steampowered.com")
        for it in steam.get("items", []):
            m = re.search(r"/apps/(\d+)/", it.get("logo", ""))
            if not m:
                continue
            aid = m.group(1)
            gid = f"steam_{aid}"
            if gid in sent:
                continue
            img = f"https://steamstatic.com{aid}/header.jpg"
            url = f"https://steampowered.com{aid}/"
            send_telegram(it["name"], "Steam", "Cheklangan muddat", img, url)
            sent.add(gid)
            changed = True
    except Exception as e:
        print("Steam xato:", e)

    if changed:
        save_sent(sent)

if __name__ == "__main__":
    main()
