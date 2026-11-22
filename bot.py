import os, re, json, html, time, threading, urllib.parse, requests
from datetime import datetime, timezone
from flask import Flask

RAW_TOKEN = (os.environ.get("BOT_TOKEN") or "").strip()
m = re.search(r"(\d+:[A-Za-z0-9_-]{20,})", RAW_TOKEN)
BOT_TOKEN = m.group(1) if m else RAW_TOKEN
TG_URL = "https://api." + "telegram.org/bot" + BOT_TOKEN
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
        "load": "⏳ O'yinlar, rasmlar va 3 tilli tavsiflar yuklanmoqda...", "empty": "😔 Hozircha bu bo'limda faol aksiyalar topilmadi.",
        "btn": "🎮 O'yinni olish / Ochish",
        "r_msg": "💱 <b>Valyuta kurslari:</b>\n\n🇺🇸 <b>1 USD</b> = <code>{usd}</code> so'm\n🇷🇺 <b>1 RUB</b> = <code>{rub}</code> so'm"
    },
    "ru": {
        "menu": "🎮 <b>Главное меню:</b> Выберите раздел 👇",
        "s_sale": "🔥 Скидки Steam", "s_free": "🎁 Бесплатно в Steam",
        "e_sale": "⚡ Скидки Epic Games", "e_free": "🎉 Бесплатно в Epic Games",
        "rates": "💱 Курсы валют", "lang": "🌐 Сменить язык",
        "load": "⏳ Загрузка игр, картинок и описаний на 3 языках...", "empty": "😔 В этом разделе пока нет активных акций.",
        "btn": "🎮 Забрать / Открыть игру",
        "r_msg": "💱 <b>Курсы валют:</b>\n\n🇺🇸 <b>1 USD</b> = <code>{usd}</code> сум\n🇷🇺 <b>1 RUB</b> = <code>{rub}</code> сум"
    },
    "en": {
        "menu": "🎮 <b>Main Menu:</b> Choose a category below 👇",
        "s_sale": "🔥 Steam Discounts", "s_free": "🎁 Steam Freebies",
        "e_sale": "⚡ Epic Games Discounts", "e_free": "🎉 Epic Games Freebies",
        "rates": "💱 Exchange Rates", "lang": "🌐 Change Language",
        "load": "⏳ Loading games, images & 3-language descriptions...", "empty": "😔 No active deals in this section right now.",
        "btn": "🎮 Claim / Open Game",
        "r_msg": "💱 <b>Exchange Rates:</b>\n\n🇺🇸 <b>1 USD</b> = <code>{usd}</code> UZS\n🇷🇺 <b>1 RUB</b> = <code>{rub}</code> UZS"
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

TR_CACHE = {}

def tr(text, lang):
    clean = re.sub(r"<[^>]+>", "", text or "").strip()
    if not clean:
        return ""
    clean = clean[:180]
    if lang == "en":
        return clean
    key = (clean, lang)
    if key in TR_CACHE:
        return TR_CACHE[key]

    # 1. Mozhi va SimplyTranslate ochiq serverlari (Render IP'ni bloklamaydi)
    mirrors = [
        ("mozhi.aryak.me", f"/api/translate?engine=google&from=en&to={lang}&text="),
        ("translate.bus-hit.me", f"/api/translate?engine=google&from=en&to={lang}&text="),
        ("simplytranslate.org", f"/api/translate/?engine=google&from=en&to={lang}&text="),
        ("st.tokhmi.xyz", f"/api/translate/?engine=google&from=en&to={lang}&text=")
    ]
    q = urllib.parse.quote(clean)
    for host, path in mirrors:
        try:
            u = "".join(["https://", host, path, q])
            r = requests.get(u, headers=HEADERS, timeout=7).json()
            res = r.get("translated-text") or r.get("translated_text") or r.get("translation")
            if res and res.lower() != clean.lower():
                TR_CACHE[key] = res
                return res
        except Exception:
            pass

    # 2. Zaxira: deep-translator (Bing / Pons / Google)
    try:
        from deep_translator import GoogleTranslator
        res = GoogleTranslator(source="en", target=lang).translate(clean)
        if res:
            TR_CACHE[key] = res
            return res
    except Exception:
        pass

    return clean



def get_rates():
    try:
        u = "".join(["https://", "open.", "er-api.com", "/v6/latest/USD"])
        r = requests.get(u, timeout=10).json()["rates"]
        uzs = float(r["UZS"])
        return uzs, uzs / float(r["RUB"])
    except Exception:
        return 12800.0, 135.0

def get_steam_details(appid):
    try:
        u = "".join(["https://", "store.", "steampowered.com", f"/api/appdetails?appids={appid}&l=english"])
        d = requests.get(u, headers=HEADERS, timeout=8).json()
        info = (d.get(str(appid), {}).get("data") or {})
        desc = info.get("short_description", "")
        genres = ", ".join([g.get("description", "") for g in (info.get("genres") or [])[:3]])
        img = info.get("header_image", "")
        return desc, genres, img
    except Exception:
        return "", "", ""

def get_steam_games(free_only):
    res = []
    try:
        u = "".join(["https://", "store.", "steampowered.com", "/api/featuredcategories/?cc=us&l=english"])
        r = requests.get(u, headers=HEADERS, timeout=15)
        items = (r.json().get("specials") or {}).get("items") or []
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
            desc, genres, h_img = get_steam_details(appid)
            img = h_img or it.get("large_capsule_image") or it.get("header_image") or ""
            res.append({
                "id": f"st_{appid}",
                "title": it.get("name", "Steam Game"),
                "desc": desc,
                "genres": genres,
                "img": img,
                "orig": orig_c / 100.0,
                "sale": final_c / 100.0,
                "disc": disc if disc > 0 else 100,
                "free": isf,
                "end": end_s,
                "link": "".join(["https://", "store.", "steampowered.com", f"/app/{appid}/"])
            })
            if len(res) >= 5:
                break
    except Exception as e:
        print("Steam err:", e, flush=True)
    return res


def get_epic_games(free_only):
    res = []
    try:
        u = "".join(["https://", "store-site-backend-static-ipv4.ak.", "epicgames.com", "/freeGamesPromotions?locale=en-US&country=US&allowCountries=US"])
        r = requests.get(u, headers=HEADERS, timeout=15)
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
            img = ""
            for im in el.get("keyImages") or []:
                if im.get("type") in ("OfferImageWide", "DieselStoreFrontWide", "Thumbnail"):
                    img = im.get("url", "")
                    break
            tags = [t.get("name", "") for t in (el.get("tags") or []) if t.get("groupName") == "genre"][:3]
            if not tags:
                tags = [c.get("path", "").split("/")[-1].title() for c in (el.get("categories") or []) if c.get("path") and c.get("path") != "games"][:2]
            genres = ", ".join([t for t in tags if t])
            slug = el.get("productSlug") or el.get("urlSlug") or ""
            for m_item in (el.get("catalogNs") or {}).get("mappings") or []:
                if m_item.get("pageSlug"):
                    slug = m_item["pageSlug"]
                    break
            slug = slug.split("/")[-1]
            link = "".join(["https://", "store.", "epicgames.com", f"/en-US/p/{slug}"]) if slug else "".join(["https://", "store.", "epicgames.com", "/en-US/free-games"])
            res.append({
                "id": f"ep_{el['id']}",
                "title": el.get("title", "Epic Game"),
                "desc": el.get("description", ""),
                "genres": genres,
                "img": img,
                "orig": orig_c / 100.0,
                "sale": final_c / 100.0,
                "disc": disc,
                "free": isf,
                "end": end_s,
                "link": link
            })
            if len(res) >= 5:
                break
    except Exception as e:
        print("Epic err:", e, flush=True)
    return res

def build_caption(g, uzs_r, rub_r):
    if g["free"]:
        pt = "🎁 <s>${:.2f}</s> ➡️ <b>0$ / 0 so'm / 0 ₽ (TEKIN)</b>".format(g["orig"])
    else:
        uzs = f"{int(round(g['sale'] * uzs_r, -2)):,}".replace(",", " ")
        rub = f"{int(round((g['sale'] * uzs_r) / rub_r)):,}".replace(",", " ")
        pt = f"🔥 <b>-{g['disc']}%</b> | <s>${g['orig']:.2f}</s> ➡️ <b>${g['sale']:.2f}</b> ({uzs} so'm | {rub} ₽)"
    genre_txt = f"\n🏷 <b>Janr / Жанр / Genre:</b> {html.escape(g['genres'])}" if g.get("genres") else ""
    end_txt = f"\n⏳ <b>Muddat / До / Ends:</b> {g['end']}" if g.get("end") else ""
    d_en = html.escape(tr(g["desc"], "en"))
    d_uz = html.escape(tr(g["desc"], "uz"))
    d_ru = html.escape(tr(g["desc"], "ru"))
    desc_block = f"\n\n🇺🇿 {d_uz}\n🇷🇺 {d_ru}\n🇬🇧 {d_en}" if d_en else ""
    return f"🎮 <b>{html.escape(g['title'])}</b>\n{pt}{genre_txt}{end_txt}{desc_block}"[:1020]

def send(cid, txt, kb=None):
    d = {"chat_id": cid, "text": txt, "parse_mode": "HTML", "disable_web_page_preview": True}
    if kb:
        d["reply_markup"] = kb
    try:
        requests.post(f"{TG_URL}/sendMessage", data=d, timeout=15)
    except Exception as e:
        print("Send err:", e, flush=True)

def send_game_card(cid, g, lang):
    uzs_r, rub_r = get_rates()
    cap = build_caption(g, uzs_r, rub_r)
    ikb = json.dumps({"inline_keyboard": [[{"text": UI[lang]["btn"], "url": g["link"]}]]})
    if g.get("img"):
        try:
            r = requests.post(f"{TG_URL}/sendPhoto", data={"chat_id": cid, "photo": g["img"], "caption": cap, "parse_mode": "HTML", "reply_markup": ikb}, timeout=15).json()
            if r.get("ok"):
                return
        except Exception:
            pass
    send(cid, cap, ikb)

def send_games_list(cid, games, lang):
    if not games:
        send(cid, UI[lang]["empty"], main_kb(lang))
        return
    for g in games:
        send_game_card(cid, g, lang)
        time.sleep(0.3)

def on_msg(cid, txt, st):
    l = st["users"].get(cid, "uz")
    if txt in ("/start", "/lang", UI["uz"]["lang"], UI["ru"]["lang"], UI["en"]["lang"]):
        send(cid, "🌍 <b>Tilni tanlang / Выберите язык / Choose language:</b>", LANG_KB)
    elif txt in (UI["uz"]["s_sale"], UI["ru"]["s_sale"], UI["en"]["s_sale"]):
        send(cid, UI[l]["load"])
        send_games_list(cid, get_steam_games(False), l)
    elif txt in (UI["uz"]["s_free"], UI["ru"]["s_free"], UI["en"]["s_free"]):
        send(cid, UI[l]["load"])
        send_games_list(cid, get_steam_games(True), l)
    elif txt in (UI["uz"]["e_sale"], UI["ru"]["e_sale"], UI["en"]["e_sale"]):
        send(cid, UI[l]["load"])
        send_games_list(cid, get_epic_games(False), l)
    elif txt in (UI["uz"]["e_free"], UI["ru"]["e_free"], UI["en"]["e_free"]):
        send(cid, UI[l]["load"])
        send_games_list(cid, get_epic_games(True), l)
    elif txt in (UI["uz"]["rates"], UI["ru"]["rates"], UI["en"]["rates"]):
        uzs, rub = get_rates()
        send(cid, UI[l]["r_msg"].format(usd=f"{uzs:,.2f}".replace(",", " "), rub=f"{rub:,.2f}".replace(",", " ")), main_kb(l))
    else:
        send(cid, UI[l]["menu"], main_kb(l))

def auto_channel_loop():
    while True:
        try:
            st = load_state()
            free_games = get_epic_games(True) + get_steam_games(True)
            changed = False
            for g in free_games:
                if g["id"] not in st["sent"]:
                    send_game_card(CHANNEL_ID, g, "uz")
                    for uid, ul in st["users"].items():
                        send_game_card(uid, g, ul)
                    st["sent"].append(g["id"])
                    changed = True
            if changed:
                save_state(st)
        except Exception as e:
            print("Auto loop err:", e, flush=True)
        time.sleep(1800)

def poll_loop():
    offset = 0
    while True:
        try:
            r = requests.get(f"{TG_URL}/getUpdates", params={"offset": offset, "timeout": 25}, timeout=35).json()
            for upd in r.get("result", []):
                offset = upd["update_id"] + 1
                st = load_state()
                if "message" in upd and "text" in upd["message"]:
                    cid = str(upd["message"]["chat"]["id"])
                    if cid not in st["users"]:
                        st["users"][cid] = "uz"
                        save_state(st)
                    on_msg(cid, upd["message"]["text"], st)
                elif "callback_query" in upd:
                    cb = upd["callback_query"]
                    cid = str(cb["message"]["chat"]["id"])
                    data = cb.get("data", "")
                    if data.startswith("setlang:"):
                        lang = data.split(":")[1]
                        st["users"][cid] = lang
                        save_state(st)
                        requests.post(f"{TG_URL}/answerCallbackQuery", data={"callback_query_id": cb["id"]})
                        send(cid, UI[lang]["menu"], main_kb(lang))
        except Exception as e:
            print("Poll err:", e, flush=True)
            time.sleep(5)

@app.route("/")
def health():
    return "FreeGame Pulse is alive!", 200

if __name__ == "__main__":
    threading.Thread(target=poll_loop, daemon=True).start()
    threading.Thread(target=auto_channel_loop, daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
