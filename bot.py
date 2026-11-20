import os, re, json, html, time, threading, requests
import xml.etree.ElementTree as ET
from flask import Flask

RAW_TOKEN = (os.environ.get("BOT_TOKEN") or "").strip()
m = re.search(r"(\d+:[A-Za-z0-9_-]{20,})", RAW_TOKEN)
BOT_TOKEN = m.group(1) if m else RAW_TOKEN
TG_URL = "https://" + "api." + "telegram.org/bot" + BOT_TOKEN
CHANNEL_ID = "@gametraverse"
STATE_FILE = "bot_users.json"
app = Flask(__name__)

UI = {
    "uz": {
        "menu": "🎮 <b>Asosiy menyu:</b> Kerakli bo'limni tanlang 👇",
        "s_sale": "🔥 Steam chegirmalar", "s_free": "🎁 Steam tekinlar",
        "e_sale": "⚡ Epic Games chegirmalar", "e_free": "🎉 Epic Games tekinlar",
        "rates": "💱 Valyuta kurslari", "lang": "🌐 Tilni o'zgartirish",
        "load": "⏳ Yuklanmoqda...", "empty": "😔 Hozircha faol aksiyalar topilmadi.",
        "r_msg": "💱 <b>Valyuta kurslari:</b>\n\n🇺🇸 <b>1 USD</b> = <code>{usd}</code> so'm\n🇷🇺 <b>1 RUB</b> = <code>{rub}</code> so'm",
        "until": "⏳ Muddat: Aksiya tugaguncha"
    },
    "ru": {
        "menu": "🎮 <b>Главное меню:</b> Выберите раздел 👇",
        "s_sale": "🔥 Скидки Steam", "s_free": "🎁 Бесплатно в Steam",
        "e_sale": "⚡ Скидки Epic Games", "e_free": "🎉 Бесплатно в Epic Games",
        "rates": "💱 Курсы валют", "lang": "🌐 Сменить язык",
        "load": "⏳ Загрузка...", "empty": "😔 Активных акций пока нет.",
        "r_msg": "💱 <b>Курсы валют:</b>\n\n🇺🇸 <b>1 USD</b> = <code>{usd}</code> сум\n🇷🇺 <b>1 RUB</b> = <code>{rub}</code> сум",
        "until": "⏳ Срок: Пока действует акция"
    },
    "en": {
        "menu": "🎮 <b>Main Menu:</b> Choose a category 👇",
        "s_sale": "🔥 Steam Discounts", "s_free": "🎁 Steam Freebies",
        "e_sale": "⚡ Epic Games Discounts", "e_free": "🎉 Epic Games Freebies",
        "rates": "💱 Exchange Rates", "lang": "🌐 Change Language",
        "load": "⏳ Loading...", "empty": "😔 No active deals right now.",
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
            return json.load(open(STATE_FILE, "r", encoding="utf-8"))
        except Exception:
            return {"users": {}, "sent": []}
    return {"users": {}, "sent": []}

def save_state(st):
    json.dump(st, open(STATE_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

def get_rates():
    try:
        r = requests.get("https://er-api.com", timeout=10).json()["rates"]
        uzs = float(r["UZS"])
        return uzs, uzs / float(r["RUB"])
    except Exception:
        return 12800.0, 135.0

def get_games(store, free_only):
    res = []
    ns = {"atom": "http://w3.org"}
    urls = ["https://reddit.com", "https://reddit.com"]
    for u in urls:
        try:
            r = requests.get(u, headers={"User-Agent": "python:pulse:v1"}, timeout=12)
            if r.status_code != 200: continue
            for e in ET.fromstring(r.text).findall("atom:entry", ns):
                t = e.findtext("atom:title", "", ns)
                c = e.findtext("atom:content", "", ns)
                if "expired" in t.lower() or f"[{store}" not in t.lower(): continue
                isf = bool(re.search(r"\b(free|100%\s*off|\$0\.00|\$0)\b", t, re.I))
                if isf != free_only: continue
                pm = re.search(r"\$(\d+(?:\.\d{1,2})?)", t)
                dm = re.search(r"(\d{2,3})%\s*off", t, re.I)
                lm = re.search(r'href="(https?://[^"]+)"[^>]*>\[link\]', c)
                res.append({"id": e.findtext("atom:id", "", ns), "title": re.sub(r"^\[.*?\]\s*(?:\(.*?\)\s*)?", "", t).strip(), "sale": 0.0 if isf else (float(pm.group(1)) if pm else 0.0), "disc": 100 if isf else (int(dm.group(1)) if dm else 50), "free": isf, "link": html.unescape(lm.group(1)) if lm else ""})
                if len(res) >= 8: return res
        except Exception:
            pass
    return res

def fmt_games(games, hdr, lang):
    if not games: return UI[lang]["empty"]
    uzs_r, rub_r = get_rates()
    out = [f"<b>{hdr}</b>\n"]
    for i, g in enumerate(games, 1):
        if g["free"]:
            pt = "🎁 <b>0$ / 0 so'm / 0 ₽ (TEKIN)</b>"
        else:
            uzs = f"{int(round(g['sale'] * uzs_r, -2)):,}".replace(",", " ")
            rub = f"{int(round((g['sale'] * uzs_r) / rub_r)):,}".replace(",", " ")
            pt = f"🔥 <b>-{g['disc']}%</b> | <b>${g['sale']:.2f}</b> ({uzs} so'm | {rub} ₽)"
        out.append(f"{i}. <a href='{g['link']}'><b>{html.escape(g['title'])}</b></a>\n   {pt}")
    out.append(f"\n{UI[lang]['until']}")
    return "\n".join(out)

def send(cid, txt, kb=None):
    d = {"chat_id": cid, "text": txt, "parse_mode": "HTML", "disable_web_page_preview": True}
    if kb: d["reply_markup"] = kb
    requests.post(f"{TG_URL}/sendMessage", data=d, timeout=15)

def on_msg(cid, txt, st):
    l = st["users"].get(cid, "uz")
    if txt in ("/start", "/lang", UI["uz"]["lang"], UI["ru"]["lang"], UI["en"]["lang"]):
        send(cid, "🌍 <b>Tilni tanlang / Выберите язык / Choose language:</b>", LANG_KB)
    elif txt in (UI["uz"]["s_sale"], UI["ru"]["s_sale"], UI["en"]["s_sale"]):
        send(cid, UI[l]["load"])
        send(cid, fmt_games(get_games("steam", False), UI[l]["s_sale"], l), main_kb(l))
    elif txt in (UI["uz"]["s_free"], UI["ru"]["s_free"], UI["en"]["s_free"]):
        send(cid, UI[l]["load"])
        send(cid, fmt_games(get_games("steam", True), UI[l]["s_free"], l), main_kb(l))
    elif txt in (UI["uz"]["e_sale"], UI["ru"]["e_sale"], UI["en"]["e_sale"]):
        send(cid, UI[l]["load"])
        send(cid, fmt_games(get_games("epic", False), UI[l]["e_sale"], l), main_kb(l))
    elif txt in (UI["uz"]["e_free"], UI["ru"]["e_free"], UI["en"]["e_free"]):
        send(cid, UI[l]["load"])
        send(cid, fmt_games(get_games("epic", True), UI[l]["e_free"], l), main_kb(l))
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
                        st["users"][cid] = ch
                        save_state(st)
                        requests.post(f"{TG_URL}/answerCallbackQuery", data={"callback_query_id": cb["id"]}, timeout=10)
                        send(cid, UI[ch]["menu"], main_kb(ch))
        except Exception as e:
            print("Err:", e)
            time.sleep(3)

def notify():
    while True:
        time.sleep(10800)
        st = load_state()
        for g in get_games("steam", True) + get_games("epic", True):
            if g["id"] not in st["sent"]:
                st["sent"] = (st["sent"] + [g["id"]])[-200:]
                save_state(st)
                al = f"🚨 <b>YANGI TEKIN O'YIN!</b>\n\n🎮 <a href='{g['link']}'><b>{html.escape(g['title'])}</b></a>\n💰 <b>0$ / 0 so'm / 0 ₽ (TEKIN)</b>"
                send(CHANNEL_ID, al)
                for uid in list(st["users"].keys()): send(uid, al)

@app.route("/")
def home():
    return "OK"

if __name__ == "__main__":
    threading.Thread(target=poll, daemon=True).start()
    threading.Thread(target=notify, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
