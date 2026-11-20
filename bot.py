import os, re, json, html, time, threading, requests
from datetime import datetime, timezone
from flask import Flask

RAW_TOKEN = (os.environ.get("BOT_TOKEN") or "").strip()
m = re.search(r"(\d+:[A-Za-z0-9_-]{20,})", RAW_TOKEN)
BOT_TOKEN = m.group(1) if m else RAW_TOKEN
TG_URL = "https://telegram.org" + BOT_TOKEN
CHANNEL_ID = "@gametraverse"
STATE_FILE = "bot_users.json"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36"}
app = Flask(__name__)

UI = {
    "uz": {
        "menu": "🎮 <b>Asosiy menyu:</b> Kerakli bo'limni tanlang 👇",
        "s_sale": "🔥 Steam chegirmalar", "s_free": "🎁 Steam tekinlar",
        "e_sale": "⚡ Epic Games chegirmalar", "e_free": "🎉 Epic Games tekinlar",
        "rates": "💱 Valyuta kurslari", "lang": "🌐 Tilni o'zgartirish",
        "load": "⏳ Ma'lumotlar yuklanmoqda...", "empty": "😔 Hozircha bu bo'limda faol aksiyalar topilmadi.",
        "r_msg": "💱 <b>Valyuta kurslari:</b>\n\n🇺🇸 <b>1 USD</b> = <code>{usd}</code> so'm\n🇷🇺 <b>1 RUB</b> = <code>{rub}</code> so'm",
        "until": "⏳ Muddat: Aksiya tugaguncha"
    },
    "ru": {
        "menu": "🎮 <b>Главное меню:</b> Выберите раздел 👇",
        "s_sale": "🔥 Скидки Steam", "s_free": "🎁 Бесплатно в Steam",
        "e_sale": "⚡ Скидки Epic Games", "e_free": "🎉 Бесплатно в Epic Games",
        "rates": "💱 Курсы валют", "lang": "🌐 Сменить язык",
        "load": "⏳ Загрузка...", "empty": "😔 В этом разделе пока нет активных акций.",
        "r_msg": "💱 <b>Курсы валют:</b>\n\n🇺🇸 <b>1 USD</b> = <code>{usd}</code> сум\n🇷🇺 <b>1 RUB</b> = <code>{rub}</code> сум",
        "until": "⏳ Срок: Пока действует акция"
    },
    "en": {
        "menu": "🎮 <b>Main Menu:</b> Choose a category below 👇",
        "s_sale": "🔥 Steam Discounts", "s_free": "🎁 Steam Freebies",
        "e_sale": "⚡ Epic Games Discounts", "e_free": "🎉 Epic Games Freebies",
        "rates": "💱 Exchange Rates", "lang": "🌐 Change Language",
        "load": "⏳ Loading...", "empty": "😔 No active deals in this section right now.",
        "r_msg": "💱 <b>Exchange Rates:</b>\n\n🇺🇸 <b>1 USD</b> = <code>{usd}</code> UZS\n🇷🇺 <b>1 RUB</b> = <code>{rub}</code> UZS",
        "until": "⏳ Duration: Limited time offer"
    }
}

LANG_KB = json.dumps({"inline_keyboard": [[{"text": "🇺🇿 O'zbekcha", "callback_data": "setlang:uz"}, {"text": "🇷🇺 Русский", "callback_data": "setlang:ru"}, {"text": "🇬🇧 English", "callback_data": "setlang:en"}]]})

def main_kb(lang):
    u = UI[lang]
    return json.dumps({"keyboard": [[{"text": u["s_sale"]}, {"text": u["s_free"]}], [{"text": u["e_sale"]}, {"text": u["e_free"]}], [{"text": u["lang"]}, {"text": u["rates"]}]], "resize_keyboard": True})

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"users": {}, "sent": []}

def save_state(st):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=2)

def get_rates():
    try:
        r = requests.get("https://er-api.com", timeout=10).json()["rates"]
        uzs = float(r["UZS"])
        return uzs, uzs / float(r["RUB"])
    except Exception:
        return 12800.0, 135.0

def get_steam_games(free_only):
    res = []
    try:
        r = requests.get("https://steampowered.com", headers=HEADERS, timeout=15)
        data = r.json()
        items = (data.get("specials") or {}).get("items") or []
        seen = set()
        for it in items:
            appid = it.get("id")
            if not appid or appid in seen:
                continue
            seen.add(appid)
            disc = int(it.get("discount_percent") or 0)
            final_c = int(it.get("final_price") or 0)
            orig_c = int(it.get("original_price") or 0)
            if orig_c <= 0:
                continue
            isf = (final_c == 0 or disc == 100)
            if free_only != isf:
                continue
            exp = it.get("discount_expiration")
            end_s = datetime.fromtimestamp(exp, timezone.utc).strftime("%d.%m.%Y") if exp else ""
            res.append({
                "id": f"st_{appid}",
                "title": it.get("name", "Steam Game"),
                "orig": orig_c / 100.0,
                "sale": final_c / 100.0,
                "disc": disc if disc > 0 else 100,
                "free": isf,
                "end": end_s,
                "link": f"https://steampowered.com{appid}"
            })
            if len(res) >= 10:
                break
    except Exception as e:
        print("Steam err:", e)
    return res

def get_epic_games(free_only):
    res = []
    try:
        url = "https://epicgames.com"
        r = requests.get(url, headers=HEADERS, timeout=15)
        elements = r.json()["data"]["Catalog"]["searchStore"]["elements"]
        now = datetime.now(timezone.utc)
        for el in elements:
            price = (el.get("price") or {}).get("totalPrice") or {}
            orig_c = int(price.get("originalPrice") or 0)
            final_c = int(price.get("discountPrice") or 0)
            if orig_c <= 0 or final_c >= orig_c:
                continue
            promos = el.get("promotions") or {}
            active = False
            end_s = ""
            for b in promos.get("promotionalOffers") or []:
                for o in b.get("promotionalOffers") or []:
                    sd = datetime.fromisoformat(o["startDate"].replace("Z", "+00:00"))
                    ed = datetime.fromisoformat(o["endDate"].replace("Z", "+00:00"))
                    if sd <= now <= ed:
                        active = True
                        end_s = ed.strftime("%d.%m.%Y")
            if not active and final_c == 0:
                continue
            isf = (final_c == 0)
            if free_only != isf:
                continue
            disc = int(round((1 - (final_c / orig_c)) * 100))
            slug = el.get("productSlug") or el.get("urlSlug") or ""
            for m_item in (el.get("catalogNs") or {}).get("mappings") or []:
                if m_item.get("pageSlug"):
                    slug = m_item["pageSlug"]
                    break
            slug = slug.split("/")[-1]
            link = f"https://epicgames.com{slug}" if slug else "https://epicgames.com"
            res.append({
                "id": f"ep_{el['id']}",
                "title": el.get("title", "Epic Game"),
                "orig": orig_c / 100.0,
                "sale": final_c / 100.0,
                "disc": disc,
                "free": isf,
                "end": end_s,
                "link": link
            })
            if len(res) >= 10:
                break
    except Exception as e:
        print("Epic err:", e)
    return res

def fmt_games(games, hdr, lang):
    if not games:
        return UI[lang]["empty"]
    uzs_r, rub_r = get_rates()
    out = [f"<b>{hdr}</b>\n"]
    for i, g in enumerate(games, 1):
        if g["free"]:
            pt = f"🎁 <s>${g['orig']:.2f}</s> ➡️ <b>0$ / 0 so'm / 0 ₽ (TEKIN)</b>"
        else:
            uzs = f"{int(round(g['sale'] * uzs_r, -2)):,}".replace(",", " ")
            rub = f"{int(round((g['sale'] * uzs_r) / rub_r)):,}".replace(",", " ")
            pt = f"🔥 <b>-{g['disc']}%</b> | <s>${g['orig']:.2f}</s> ➡️ <b>${g['sale']:.2f}</b> ({uzs} so'm | {rub} ₽)"
        end_txt = f" | ⏳ {g['end']}" if g.get("end") else ""
        out.append(f"{i}. <a href='{g['link']}'><b>{html.escape(g['title'])}</b></a>\n   {pt}{end_txt}")
    return "\n".join(out)

def send(cid, txt, kb=None):
    d = {"chat_id": cid, "text": txt, "parse_mode": "HTML", "disable_web_page_preview": True}
    if kb:
        d["reply_markup"] = kb
    requests.post(f"{TG_URL}/sendMessage", data=d, timeout=15)

def on_msg(cid, txt, st):
    l = st["users"].get(cid, "uz")
    if txt in ("/start", "/lang", UI["uz"]["lang"], UI["ru"]["lang"], UI["en"]["lang"]):
        send(cid, "🌍 <b>Tilni tanlang / Выберите язык / Choose language:</b>", LANG_KB)
    elif txt in (UI["uz"]["s_sale"], UI["ru"]["s_sale"], UI["en"]["s_sale"]):
        send(cid, UI[l]["load"])
        send(cid, fmt_games(get_steam_games(False), UI[l]["s_sale"], l), main_kb(l))
    elif txt in (UI["uz"]["s_free"], UI["ru"]["s_free"], UI["en"]["s_free"]):
        send(cid, UI[l]["load"])
        send(cid, fmt_games(get_steam_games(True), UI[l]["s_free"], l), main_kb(l))
    elif txt in (UI["uz"]["e_sale"], UI["ru"]["e_sale"], UI["en"]["e_sale"]):
        send(cid, UI[l]["load"])
        send(cid, fmt_games(get_epic_games(False), UI[l]["e_sale"], l), main_kb(l))
    elif txt in (UI["uz"]["e_free"], UI["ru"]["e_free"], UI["en"]["e_free"]):
        send(cid, UI[l]["load"])
        send(cid, fmt_games(get_epic_games(True), UI[l]["e_free"], l), main_kb(l))
    elif txt in (UI["uz"]["rates"], UI["ru"]["rates"], UI["en"]["rates"]):
        u, r = get_rates()
        send(cid, UI[l]["r_msg"].format(usd=f"{int(round(u)):,}".replace(",", " "), rub=f"{r:.1f}"), main_kb(l))

def poll():
    st = load_state()
    off = 0
    while True:
        try:
            r = requests.get(f"{TG_URL}/getUpdates", params={"offset": off, "timeout": 25}, timeout=30).json()
            for u in r.get("result", []):
                off = u["update_id"] + 1
                if "message" in u:
                    on_msg(str(u["message"]["chat"]["id"]), (u["message"].get("text") or "").strip(), st)
                elif "callback_query" in u:
                    cb = u["callback_query"]
                    cid = str(cb["message"]["chat"]["id"])
                    if cb.get("data", "").startswith("setlang:"):
                        ch = cb["data"].split(":")[1]
