import os
import json
import requests

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID", "@gametraverse")
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
        json.dump(ids, f, indent=2)

def get_free_games():
    url = "https://gamerpower.com"
    r = requests.get(url, timeout=20)
    if r.status_code == 200:
        return r.json()
    return []

def send_post(game):
    title = game.get("title", "Noma'lum o'yin")
    worth = game.get("worth", "N/A")
    platforms = game.get("platforms", "")
    end_date = game.get("end_date", "Noma'lum")
    image = game.get("image", "")
    link = game.get("open_giveaway_url", "")

    caption = (
        f"🎁 <b>BEPUL O'YIN!</b>\n\n"
        f"🎮 <b>{title}</b>\n"
        f"🖥 <b>Platforma:</b> {platforms}\n"
        f"💰 <b>Narxi:</b> <s>{worth}</s> ➡️ <b>0$ (BEPUL)</b>\n"
        f"⏳ <b>Tugash vaqti:</b> {end_date}"
    )

    markup = {
        "inline_keyboard": [[
            {"text": "📥 Bepul olish", "url": link}
        ]]
    }

    url = f"https://telegram.org{BOT_TOKEN}/sendPhoto"
    payload = {
        "chat_id": CHANNEL_ID,
        "photo": image,
        "caption": caption,
        "parse_mode": "HTML",
        "reply_markup": json.dumps(markup)
    }

    res = requests.post(url, data=payload, timeout=20)
    print(title, "->", res.status_code, res.text)
    return res.status_code == 200

def main():
    if not BOT_TOKEN:
        print("XATO: BOT_TOKEN topilmadi!")
        return

    sent_ids = load_sent()
    games = get_free_games()
    updated = False

    for game in reversed(games):
        gid = str(game.get("id"))
        if gid not in sent_ids:
            if send_post(game):
                sent_ids.append(gid)
                updated = True

    if updated:
        save_sent(sent_ids)

if __name__ == "__main__":
    main()
