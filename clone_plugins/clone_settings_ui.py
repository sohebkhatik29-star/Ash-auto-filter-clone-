"""Owner-only settings UI exposed inside an individual clone.
Only the four controls intended for a clone owner are shown here.
"""
from pyrogram import filters
from pyrogram.handlers import MessageHandler, CallbackQueryHandler
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from clone_plugins.users_api import update_user_info


def db():
    from plugins.clone import mongo_db
    return mongo_db


def record(client):
    m = db()
    if m is None:
        return {}
    return m.bots.find_one({"bot_id": client.me.id}) or {}


def owner(client, uid):
    from config import ADMINS
    try:
        if int(uid) in [int(x) for x in ADMINS if str(x).strip().lstrip("-").isdigit()]:
            return True
    except Exception:
        pass
    r = record(client)
    try:
        return int(r.get("user_id", 0)) == int(uid)
    except Exception:
        return False


def save(client, **data):
    m = db()
    if m is not None:
        m.bots.update_one({"bot_id": client.me.id}, {"$set": data}, upsert=True)


def menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔗 LINK SHORTENER", callback_data="cset:shortener")],
        [InlineKeyboardButton("📝 CUSTOM CAPTION", callback_data="cset:caption")],
        [InlineKeyboardButton("➕ CUSTOM BUTTON", callback_data="cset:button")],
        [InlineKeyboardButton("🖼️ START PHOTO", callback_data="cset:startpic")],
        [InlineKeyboardButton("🛡️ PROTECT CONTENT", callback_data="cset:protect")],
    ])


async def settings(client, message):
    if not owner(client, message.from_user.id):
        return await message.reply("❌ Clone owner only.")
    await message.reply("⚙️ <b>CLONE SETTINGS</b>\n\nOnly your clone settings are shown here.", reply_markup=menu())


async def callbacks(client, query):
    data = query.data
    if not data.startswith("cset:"):
        return
    if not owner(client, query.from_user.id):
        return await query.answer("❌ Clone owner only.", show_alert=True)
    action = data.split(":", 1)[1]
    r = record(client)

    if action == "home":
        await query.message.edit_text("⚙️ <b>CLONE SETTINGS</b>\n\nOnly your clone settings are shown here.", reply_markup=menu())
        return await query.answer()

    if action == "protect":
        state = not bool(r.get("protect_content", False))
        save(client, protect_content=state)
        return await query.answer(f"🛡️ Protect Content: {'ON' if state else 'OFF'}", show_alert=True)

    await query.answer()
    if action == "shortener":
        ans = await client.ask(query.from_user.id, "🔗 Send <code>API_KEY | BASE_SITE</code>. Send <code>off</code> to disable.", timeout=120)
        text = (ans.text or "").strip()
        if text.lower() == "off":
            save(client, shortener_api=None, base_site=None)
            try:
                await update_user_info(int(r.get("user_id")), {"shortener_api": None, "base_site": None})
            except Exception:
                pass
            return await client.send_message(query.from_user.id, "✅ <b>Link shortener disabled.</b>")
        if "|" not in text:
            return await client.send_message(query.from_user.id, "❌ <b>Format:</b> <code>API_KEY | BASE_SITE</code>\nExample: <code>cc32b72b56d7980dba4e49bf3ee466556955c0c6 | vplink.in</code>")
        api, site = [x.strip() for x in text.split("|", 1)]
        site = site.replace("https://", "").replace("http://", "").rstrip("/")
        save(client, shortener_api=api, base_site=site)
        try:
            await update_user_info(int(r.get("user_id")), {"shortener_api": api, "base_site": site})
        except Exception:
            pass
        return await client.send_message(query.from_user.id, f"✅ <b>Link shortener saved!</b>\n\n<b>Site:</b> <code>{site}</code>\n<b>API:</b> <code>{api}</code>")

    if action == "caption":
        ans = await client.ask(query.from_user.id, "📝 Send custom caption. Send <code>off</code> to disable.", timeout=120)
        text = (ans.text or "").strip()
        if text.lower() == "off":
            save(client, custom_caption=None)
            return await client.send_message(query.from_user.id, "✅ <b>Custom caption disabled.</b>")
        save(client, custom_caption=text[:4000])
        return await client.send_message(query.from_user.id, f"✅ <b>Custom caption saved!</b>\n\n<code>{text[:4000]}</code>")

    if action == "button":
        ans = await client.ask(query.from_user.id, "➕ Send <code>Button Text - https://example.com</code>. Send <code>off</code> to clear.", timeout=120)
        text = (ans.text or "").strip()
        if text.lower() == "off":
            save(client, custom_buttons=[])
            return await client.send_message(query.from_user.id, "✅ <b>Custom buttons cleared.</b>")
        if " - " not in text and "-" in text:
            parts = [x.strip() for x in text.split("-", 1)]
        elif " - " in text:
            parts = [x.strip() for x in text.split(" - ", 1)]
        else:
            return await client.send_message(query.from_user.id, "❌ <b>Format:</b> <code>Button Text - https://example.com</code>")
        label, url = parts[0], parts[1]
        if not url.startswith(("http://", "https://", "tg://")):
            return await client.send_message(query.from_user.id, "❌ <b>URL must start with http://, https:// or tg://</b>")
        buttons = list(r.get("custom_buttons", []))
        buttons.append({"text": label[:64], "url": url})
        save(client, custom_buttons=buttons)
        return await client.send_message(query.from_user.id, f"✅ <b>Custom button added:</b> [{label}]({url})", disable_web_page_preview=True)

    if action == "startpic":
        ans = await client.ask(query.from_user.id, "🖼️ Send image URL for start photo. Send <code>off</code> to reset to default.", timeout=120)
        text = (ans.text or "").strip()
        if text.lower() == "off":
            save(client, start_pic=None)
            return await client.send_message(query.from_user.id, "✅ <b>Reset to default start photo.</b>")
        if not text.startswith(("http://", "https://")):
            return await client.send_message(query.from_user.id, "❌ <b>URL must start with http:// or https://</b>")
        save(client, start_pic=text)
        return await client.send_message(query.from_user.id, "✅ <b>Custom start photo saved!</b>")


def register(client):
    client.add_handler(MessageHandler(settings, filters.command("settings") & filters.private), group=0)
    client.add_handler(CallbackQueryHandler(callbacks, filters.regex(r"^cset:(home|shortener|caption|button|startpic|protect)$")), group=0)
    return client
