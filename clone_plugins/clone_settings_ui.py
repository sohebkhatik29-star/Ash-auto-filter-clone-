"""Owner-only settings UI exposed inside an individual clone.
Only the four controls intended for a clone owner are shown here."""
from pyrogram import filters
from pyrogram.handlers import MessageHandler, CallbackQueryHandler
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from plugins.clone import mongo_db
from clone_plugins.users_api import get_user, update_user_info


def record(client):
    if mongo_db is None:
        return {}
    return mongo_db.bots.find_one({"bot_id": client.me.id}) or {}


def owner(client, uid):
    r = record(client)
    try:
        return int(r.get("user_id", 0)) == int(uid)
    except Exception:
        return False


def save(client, **data):
    if mongo_db is not None:
        mongo_db.bots.update_one({"bot_id": client.me.id}, {"$set": data}, upsert=True)


def menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔗 LINK SHORTENER", callback_data="cset:shortener")],
        [InlineKeyboardButton("📝 CUSTOM CAPTION", callback_data="cset:caption")],
        [InlineKeyboardButton("➕ CUSTOM BUTTON", callback_data="cset:button")],
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

    if action == "protect":
        state = not bool(r.get("protect_content", False))
        save(client, protect_content=state)
        return await query.message.edit_text(f"🛡️ <b>PROTECT CONTENT</b>\n\nStatus: <b>{'ON ✅' if state else 'OFF ❌'}</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 TOGGLE", callback_data="cset:protect")],[InlineKeyboardButton("‹ BACK", callback_data="cset:home")]]))

    await query.answer()
    if action == "shortener":
        ans = await client.ask(query.from_user.id, "🔗 Send <code>API_KEY | BASE_SITE</code>. Send <code>off</code> to disable.", timeout=120)
        text = (ans.text or "").strip()
        if text.lower() == "off":
            save(client, shortener_api=None, base_site=None)
            return await query.message.edit_text("🔗 <b>LINK SHORTENER</b>\n\nDisabled.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="cset:home")]]))
        if "|" not in text:
            return await query.message.edit_text("❌ Format: <code>API_KEY | vplink.in</code>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="cset:home")]]))
        api, site = [x.strip() for x in text.split("|", 1)]
        site = site.replace("https://", "").replace("http://", "").rstrip("/")
        save(client, shortener_api=api, base_site=site)
        # Keep the owner's legacy shortener profile in sync with the clone.
        try:
            uid = int(r.get("user_id"))
            await update_user_info(uid, {"shortener_api": api, "base_site": site})
        except Exception:
            pass
        return await query.message.edit_text("🔗 <b>LINK SHORTENER</b>\n\nSaved successfully.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="cset:home")]]))

    if action == "caption":
        ans = await client.ask(query.from_user.id, "📝 Send custom caption. Send <code>off</code> to disable.", timeout=120)
        text = (ans.text or "").strip()
        save(client, custom_caption=None if text.lower() == "off" else text[:4000])
        return await query.message.edit_text("📝 <b>CUSTOM CAPTION</b>\n\nSaved successfully.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="cset:home")]]))

    if action == "button":
        ans = await client.ask(query.from_user.id, "➕ Send <code>Button Text - https://example.com</code>. Send <code>off</code> to clear.", timeout=120)
        text = (ans.text or "").strip()
        if text.lower() == "off":
            save(client, custom_buttons=[])
            return await query.message.edit_text("➕ <b>CUSTOM BUTTON</b>\n\nButtons cleared.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="cset:home")]]))
        if " - " not in text:
            return await query.message.edit_text("❌ Format: <code>Button Text - https://example.com</code>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="cset:home")]]))
        label, url = [x.strip() for x in text.split(" - ", 1)]
        if not url.startswith(("http://", "https://")):
            return await query.message.edit_text("❌ URL must start with http:// or https://", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="cset:home")]]))
        buttons = list(r.get("custom_buttons", []))
        buttons.append({"text": label[:64], "url": url})
        save(client, custom_buttons=buttons)
        return await query.message.edit_text("➕ <b>CUSTOM BUTTON</b>\n\nButton added successfully.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="cset:home")]]))


async def home_callback(client, query):
    if query.data != "cset:home":
        return
    if not owner(client, query.from_user.id):
        return await query.answer("❌ Clone owner only.", show_alert=True)
    await query.message.edit_text("⚙️ <b>CLONE SETTINGS</b>\n\nOnly your clone settings are shown here.", reply_markup=menu())
    await query.answer()


def register(client):
    client.add_handler(MessageHandler(settings, filters.command("settings") & filters.private), group=0)
    client.add_handler(CallbackQueryHandler(home_callback, filters.regex(r"^cset:home$")), group=0)
    client.add_handler(CallbackQueryHandler(callbacks, filters.regex(r"^cset:(shortener|caption|button|protect)$")), group=0)
    return client
