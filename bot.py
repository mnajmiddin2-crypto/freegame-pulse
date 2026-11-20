import os
import re
import json
import html
import time
import threading
import xml.etree.ElementTree as ET
from flask import Flask
import requests

RAW_TOKEN = (os.environ.get("BOT_TOKEN") or "").strip()
m = re.search(r"(\d+:[A-Za-z0-9_-]{20,})", RAW_TOKEN)
BOT_TOKEN = m.group(1) if m else RAW_TOKEN

HOST = "api." + "telegram.org"
TG_URL = f"https://{HOST}/bot{BOT_TOKEN}"
CHANNEL_ID = "@gametraverse"
STATE_FILE = "bot_users.json"

app = Flask(__name__)

UI = {
    "uz": {
        "menu_title": "🎮 <b>Asosiy menyu:</b> Kerakli bo'limni tanlang 👇",
        "btn_steam_sale": "🔥 Steam chegirmalar",
        "btn_steam_free": "🎁 Steam tekinlar",
        "btn_epic_sale": "⚡ Epic Games chegirmalar",
        "btn_epic_free": "🎉 Epic Games tekinlar",
        "btn_rates": "💱 Valyuta kurslari",
        "btn_lang": "🌐 Tilni o'zgartirish",
        "loading": "⏳ Ma'lumotlar yuklanmoqda...",
        "empty": "😔 Hozircha bu bo'limda faol aksiyalar topilmadi.",
        "rates_msg": "💱 <b>Bugungi valyuta kurslari (Markaziy bank):</b>\n\n🇺🇸 <b>1 USD</b> = <code>{usd}</code> so'm\n🇷🇺 <b>1 RUB</b> = <code>{rub}</code> so'm\n\n<i>Barcha o'yin narxlari shu kurs bo'yicha hisoblanadi.</i>",
        "until": "⏳ Muddat: Aksiya tugaguncha"
    },
    "ru": {
        "menu_title": "🎮 <b>Главное меню:</b> Выберите нужный раздел 👇",
        "btn_steam_sale": "🔥 Скидки Steam",
        "btn_steam_free": "🎁 Бесплатно в Steam",
        "btn_epic_sale": "⚡ Скидки Epic Games",
        "btn_epic_free": "🎉 Бесплатно в Epic Games",
        "btn_rates": "💱 Курсы валют",
        "btn_lang": "🌐 Сменить язык",
        "loading": "⏳ Загрузка данных...",
        "empty": "😔 В этом разделе пока нет активных акций.",
        "rates_msg": "💱 <b>Актуальные курсы валют:</b>\n\n🇺🇸 <b>1 USD</b> = <code>{usd}</code> сум\n🇷🇺 <b>1 RUB</b> = <code>{rub}</code> сум\n\n<i>Все цены на игры рассчитываются по этому курсу.</i>",
        "until": "⏳ Срок: Пока действует акция"
    },
    "en": {
        "menu_title": "🎮 <b>Main Menu:</b> Choose a category below 👇",
        "btn_steam_sale": "🔥 Steam Discounts",
        "btn_steam_free": "🎁 Steam Freebies",
        "btn_epic_sale": "⚡ Epic Games Discounts",
        "btn_epic_free": "🎉 Epic Games Freebies",
        "btn_rates": "💱 Exchange Rates",
        "btn_lang": "🌐 Change Language",
        "loading": "⏳ Loading deals...",
        "empty": "😔 No active deals found in this section right now.",
        "rates_msg": "💱 <b>Current Exchange Rates:</b>\n\n🇺🇸 <b>1 USD</b> = <code>{usd}</code> UZS\n🇷🇺 <b>1 RUB</b> = <code>{rub}</code> UZS\n\n<i>All game prices are calculated using these rates.</i>",
        "until": "⏳ Duration: Limited time offer"
    }
}

def get_main_keyboard(lang):
    u = UI[lang]
    return json.dumps({
        "keyboard": [
            [{"text": u["btn_steam_sale"]}, {"text": u["btn_steam_free"]}],
            [{"text": u["btn_epic_sale"]}, {"text": u["btn_epic_free"]}],
            [{"text": u["btn_lang"]}, {"text": u["btn_rates"]}]
        ],
        "resize_keyboard": True
    })

LANG_INLINE = json.dumps({
    "inline_keyboard": [[
        {"text": "🇺🇿 O'zbekcha", "callback_data": "setlang:uz"},
        {"text": "🇷🇺 Русский", "callback_data": "setlang:ru"},
        {"text": "🇬🇧 English", "callback_data": "setlang:en"}
    ]]
})

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"users": {}, "sent": []}

def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def get_rates():
    try:
        r = requests.get("https://er-api.com", timeout=10).json()
        uzs = float(r["rates"]["UZS"])
        rub_in_usd = float(r["rates"]["RUB"])
        return uzs, uzs / rub_in_usd
    except Exception:
        return 12800.0, 135.0

def get_games_list(store_filter, only_free):
    results = []
    headers = {"User-Agent": "python:freegame-pulse-live:v1.0 (by /u/gametraverse)"}
    feeds = [
        "https://reddit.com",
        "https://reddit.com"
    ]
    ns = {"atom": "http://w3.org"}
    for url in feeds:
        try:
            r = requests.get(url, headers=headers, timeout=12)
            if r.status_code != 200:
                continue
            root = ET.fromstring(r.text)
            for entry in root.findall("atom:entry", ns):
                eid = entry.findtext("atom:id", default="", namespaces=ns)
                title = entry.findtext("atom:title", default="", namespaces=ns)
                content = entry.findtext("atom:content", default="", namespaces=ns)
                if "expired" in title.lower():
                    continue
                if store_filter == "steam" and "[steam" not in title.lower():
                    continue
                if store_filter == "epic" and "[epic" not in title.lower():
                    continue
                is_free = bool(re.search(r"\b(free|100%\s*off|\$0\.00|\$0)\b", title, re.I))
                if only_free != is_free:
                    continue
                price_m = re.search(r"\$(\d+(?:\.\d{1,2})?)", title)
                disc_m = re.search(r"(\d{2,3})%\s*off", title, re.I)
                sale = 0.0 if is_free else (float(price_m.group(1)) if price_m else 0.0)
                disc = 100 if is_free else (int(disc_m.group(1)) if disc_m else 50)
                link_m = re.search(r'href="(https?://[^"]+)"[^>]*>\[link\]', content)
                link = html.unescape(link_m.group(1)) if link_m else ""
                clean_title = re.sub(r"^\[.*?\]\s*(?:\(.*?\)\s*)?", "", title).strip()
                results.append({"id": eid, "title": clean_title, "sale": sale, "disc": disc, "is_free": is_free, "link": link})
                if len(results) >= 8:
                    return results
        except Exception:
            pass
    return results

def format_list_message(games, title_header, lang):
    if not games:
        return UI[lang]["empty"]
    usd_uzs, rub_uzs = get_rates()
    lines = [f"<b>{title_header}</b>\n"]
    for i, g in enumerate(games, 1):
        if g["is_free"]:
            price_txt = "🎁 <b>0$ / 0 so'm / 0 ₽ (TEKIN)</b>"
        else:
            uzs = f"{int(round(g['sale'] * usd_uzs, -2)):,}".replace(",", " ")
            rub = f"{int(round((g['sale'] * usd_uzs) / rub_uzs)):,}".replace(",", " ")
            price_txt = f"🔥 <b>-{g['disc']}%</b> | <b>${g['sale']:.2f}</b> ({uzs} so'm | {rub} ₽)"
        lines.append(f"{i}. <a href='{g['link']}'><b>{html.escape(g['title'])}</b></a>\n   {price_txt}")
    lines.append(f"\n{UI[lang]['until']}")
    return "\n".join(lines)

def send_msg(chat_id, text, reply_markup=None):
    data = {"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    if reply_markup:
        data["reply_markup"] = reply_markup
    requests.post(f"{TG_URL}/sendMessage", data=data, timeout=15)

def handle_message(cid, text, state):
    lang = state["users"].get(cid, "uz")
    if text in ("/start", "/lang") or text in (UI["uz"]["btn_lang"], UI["ru"]["btn_lang"], UI["en"]["btn_lang"]):
        send_msg(cid, "🌍 <b>Tilni tanlang / Выберите язык / Choose language:</b>", LANG_INLINE)
    elif text in (UI["uz"]["btn_steam_sale"], UI["ru"]["btn_steam_sale"], UI["en"]["btn_steam_sale"]):
        send_msg(cid, UI[lang]["loading"])
        send_msg(cid, format_list_message(get_games_list("steam", False), UI[lang]["btn_steam_sale"], lang), get_main_keyboard(lang))
    elif text in (UI["uz"]["btn_steam_free"], UI["ru"]["btn_steam_free"], UI["en"]["btn_steam_free"]):
        send_msg(cid, UI[lang]["loading"])
        send_msg(cid, format_list_message(get_games_list("steam", True), UI[lang]["btn_steam_free"], lang), get_main_keyboard(lang))
    elif text in (UI["uz"]["btn_epic_sale"], UI["ru"]["btn_epic_sale"], UI["en"]["btn_epic_sale"]):
        send_msg(cid, UI[lang]["loading"])
        send_msg(cid, format_list_message(get_games_list("epic", False), UI[lang]["btn_epic_sale"], lang), get_main_keyboard(lang))
    elif text in (UI["uz"]["btn_epic_free"], UI["ru"]["btn_epic_free"], UI["en"]["btn_epic_free"]):
        send_msg(cid, UI[lang]["loading"])
        send_msg(cid, format_list_message(get_games_list("epic", True), UI[lang]["btn_epic_free"], lang), get_main_keyboard(lang))
    elif text in (UI["uz"]["btn_rates"], UI["ru"]["btn_rates"], UI["en"]["btn_rates"]):
        usd, rub = get_rates()
        usd_s = f"{int(round(usd)):,}".replace(",", " ")
        rub_s = f"{rub:.1f}"
        send_msg(cid, UI[lang]["rates_msg"].format(usd=usd_s, rub=rub_s), get_main_keyboard(lang))

def bot_polling():
    state = load_state()
    offset = 0
    while True:
        try:
            r = requests.get(f"{TG_URL}/getUpdates", params={"offset": offset, "timeout": 25}, timeout=30).json()
            for upd in r.get("result", []):
                offset = upd["update_id"] + 1
                if "message" in upd:
                    msg = upd["message"]
                    handle_message(str(msg["chat"]["id"]), (msg.get("text") or "").strip(), state)
                elif "callback_query" in upd:
                    cb = upd["callback_query"]
                    cid = str(cb["message"]["chat"]["id"])
                    data = cb.get("data", "")
                    if data.startswith("setlang:"):
                        chosen = data.split(":")
                        state["users"][cid] = chosen
                        save_state(state)
                        requests.post(f"{TG_URL}/answerCallbackQuery", data={"callback_query_id": cb["id"]}, timeout=10)
                        send_msg(cid, UI[chosen]["menu_title"], get_main_keyboard(chosen))
        except Exception as e:
