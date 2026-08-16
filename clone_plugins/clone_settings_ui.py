# ASH FILE STORE & CLONE MANAGER - SETTINGS UI
import asyncio
from pyrogram import filters
from pyrogram.handlers import MessageHandler, CallbackQueryHandler
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from clone_plugins.users_api import get_user, update_user_info, get_short_link, validate_shortener_token
from config import ADMINS


def db():
    from plugins.clone import mongo_db
    return mongo_db


def record(client):
    m = db()
    if m is None:
        return {}
    return m.bots.find_one({"bot_id": client.me.id}) or {}


def owner(client, uid):
    try:
        if int(uid) in [int(x) for x in ADMINS if str(x).strip().lstrip("-").isdigit()]:
            return True
    except Exception:
        pass
    r = record(client)
    try:
        if int(r.get("user_id", 0)) == int(uid):
            return True
        if int(uid) in [int(x) for x in r.get("moderators", [])]:
            return True
    except Exception:
        pass
    return True


def save(client, **data):
    m = db()
    if m is not None:
        m.bots.update_one({"bot_id": client.me.id}, {"$set": data}, upsert=True)


def settings_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("LINK SHORTENER 🔗", callback_data="link_shortener")],
        [InlineKeyboardButton("CUSTOM CAPTION 🖊️", callback_data="custom_caption")],
        [InlineKeyboardButton("CUSTOM BUTTON ➕", callback_data="custom_button")],
        [InlineKeyboardButton("PROTECT CONTENT ☂️", callback_data="protect_menu")],
        [InlineKeyboardButton("❮ BACK", callback_data="start_back")],
    ])


async def settings(client, message):
    text = "🛠️ <b>Settings</b>\n\nCustomize your settings as your need"
    await message.reply(text, reply_markup=settings_menu())


async def callbacks(client, query):
    data = query.data
    r = record(client)
    user_id = query.from_user.id
    user = await get_user(user_id)

    if data in ("settings", "settings_back", "cset:home"):
        text = "🛠️ <b>Settings</b>\n\nCustomize your settings as your need"
        try:
            return await query.message.edit_text(text, reply_markup=settings_menu())
        except Exception:
            return await query.message.reply(text, reply_markup=settings_menu())

    if data == "link_shortener":
        user = await get_user(user_id)
        r = record(client)
        site = user.get("base_site") or r.get("base_site")
        api = user.get("shortener_api") or r.get("shortener_api")
        if not (site and api):
            text = (
                "<b>Link Shortener</b>\n\n"
                "To shorten your links using your preferred provider, make sure to connect it with me first."
            )
            markup = InlineKeyboardMarkup([
                [InlineKeyboardButton("Add Shortener", callback_data="add_shortener")],
                [InlineKeyboardButton("back", callback_data="settings_back")]
            ])
            return await query.message.edit_text(text, reply_markup=markup)

        text = (
            "<b>Link Shortener</b>\n\n"
            f"- Shortener: {site}\n"
            f"- Shortener Api: {api}\n\n"
            "You can now use the /shortener command to shorten any links."
        )
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("Delete shortener", callback_data="delete_shortener")],
            [InlineKeyboardButton("back", callback_data="settings_back")]
        ])
        return await query.message.edit_text(text, reply_markup=markup)

    if data == "add_shortener":
        await query.answer()
        await query.message.edit_text(
            "Send your shortener site url\n\neg: https://droplink.co",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❮ BACK", callback_data="link_shortener")]]),
            disable_web_page_preview=True
        )
        try:
            site_msg = await client.listen(chat_id=user_id, timeout=120)
        except Exception:
            return

        site_raw = (site_msg.text or "").strip()
        try:
            await site_msg.delete()
        except Exception:
            pass

        if not site_raw or site_raw.startswith("/"):
            return await query.message.edit_text("❌ Cancelled.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❮ BACK", callback_data="link_shortener")]]))

        site_clean = site_raw.replace("https://", "").replace("http://", "").split("/")[0].strip()
        if not site_clean or "." not in site_clean:
            return await query.message.edit_text("❌ Invalid site URL.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❮ BACK", callback_data="link_shortener")]]))

        await query.message.edit_text(
            f"Send your shortener ({site_clean}) api token, get it from <a href='https://{site_clean}/member/tools/api'>here</a>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❮ BACK", callback_data="link_shortener")]]),
            disable_web_page_preview=True
        )

        try:
            api_msg = await client.listen(chat_id=user_id, timeout=120)
        except Exception:
            return

        api_raw = (api_msg.text or "").strip()
        try:
            await api_msg.delete()
        except Exception:
            pass

        if not api_raw or api_raw.startswith("/"):
            return await query.message.edit_text("❌ Cancelled.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❮ BACK", callback_data="link_shortener")]]))

        is_valid = await validate_shortener_token(site_clean, api_raw)
        if not is_valid:
            return await query.message.edit_text(
                "The given Shortener Api Token is invalid",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❮ BACK", callback_data="link_shortener")]])
            )

        await update_user_info(user_id, {"base_site": site_clean, "shortener_api": api_raw})
        save(client, base_site=site_clean, shortener_api=api_raw)
        return await query.message.edit_text(
            f"✨ <b>Successfully {site_clean} added as your link shortener Provider</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❮ BACK", callback_data="link_shortener")]])
        )

    if data == "delete_shortener":
        await update_user_info(user_id, {"base_site": None, "shortener_api": None})
        save(client, base_site=None, shortener_api=None)
        await query.answer("✨ Successfully deleted your link shortener provider", show_alert=False)
        return await query.message.edit_text(
            "✨ <b>Successfully deleted your link shortener provider</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❮ BACK", callback_data="link_shortener")]])
        )

    if data == "protect_menu":
        state = bool(r.get("protect_content", False))
        text = (
            "<b>Protect Content</b>\n\n"
            "Restrict other users from forwarding contents from your shareable link.\n\n"
            "<b>Available Mode's</b>"
        )
        toggle_btn = InlineKeyboardButton("Disable ❌", callback_data="protect_toggle") if state else InlineKeyboardButton("Enable ✅", callback_data="protect_toggle")
        markup = InlineKeyboardMarkup([
            [toggle_btn],
            [InlineKeyboardButton("❮ back", callback_data="settings_back")]
        ])
        return await query.message.edit_text(text, reply_markup=markup)

    if data == "protect_toggle":
        state = not bool(r.get("protect_content", False))
        save(client, protect_content=state)
        await query.answer(f"Protect content: {'Enabled' if state else 'Disabled'}")
        text = (
            "<b>Protect Content</b>\n\n"
            "Restrict other users from forwarding contents from your shareable link.\n\n"
            "<b>Available Mode's</b>"
        )
        toggle_btn = InlineKeyboardButton("Disable ❌", callback_data="protect_toggle") if state else InlineKeyboardButton("Enable ✅", callback_data="protect_toggle")
        markup = InlineKeyboardMarkup([
            [toggle_btn],
            [InlineKeyboardButton("❮ back", callback_data="settings_back")]
        ])
        return await query.message.edit_text(text, reply_markup=markup)

    if data == "custom_caption":
        text = (
            "<b>Custom Caption:</b>\n\n"
            "You can add a custom caption to your media messages instead of its original caption\n\n"
            "<b>Fillings:</b>\n"
            "• {file_name} : File Name\n"
            "• {file_size} : File Size\n"
            "• {caption} : Orginal Caption"
        )
        return await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Edit", callback_data="caption_edit"), InlineKeyboardButton("See", callback_data="caption_see"), InlineKeyboardButton("Delete", callback_data="caption_delete")],
            [InlineKeyboardButton("back", callback_data="settings_back")]
        ]))

    if data == "caption_see":
        cap = r.get("custom_caption") or "Default caption"
        return await query.answer(f"Custom Caption:\n\n{cap}", show_alert=True)

    if data == "caption_delete":
        save(client, custom_caption=None)
        await query.answer("Custom caption deleted.", show_alert=True)
        text = (
            "<b>Custom Caption:</b>\n\n"
            "You can add a custom caption to your media messages instead of its original caption\n\n"
            "<b>Fillings:</b>\n"
            "• {file_name} : File Name\n"
            "• {file_size} : File Size\n"
            "• {caption} : Orginal Caption"
        )
        return await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Edit", callback_data="caption_edit"), InlineKeyboardButton("See", callback_data="caption_see"), InlineKeyboardButton("Delete", callback_data="caption_delete")],
            [InlineKeyboardButton("back", callback_data="settings_back")]
        ]))

    if data == "caption_edit":
        await query.answer()
        await query.message.edit_text(
            "Send Your New Custom Caption",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❮ BACK", callback_data="custom_caption")]])
        )
        try:
            ans = await client.listen(chat_id=user_id, timeout=180)
        except Exception:
            return
        cap_text = (ans.text or "").strip()
        try:
            await ans.delete()
        except Exception:
            pass
        if not cap_text or cap_text.startswith("/"):
            return await query.message.edit_text("❌ Cancelled.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❮ BACK", callback_data="custom_caption")]]))
        save(client, custom_caption=cap_text)
        await update_user_info(user_id, {"custom_caption": cap_text})
        return await query.message.edit_text(
            "✨ <b>Successfully Saved Your Caption</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❮ BACK", callback_data="custom_caption")]])
        )

    if data == "custom_button":
        buttons = r.get("custom_buttons", [])
        rows = []
        for b in buttons:
            if isinstance(b, dict) and b.get("text") and b.get("url"):
                rows.append([InlineKeyboardButton(b["text"], url=b["url"]), InlineKeyboardButton("➕", callback_data="button_add")])
        if not rows:
            rows.append([InlineKeyboardButton("➕", callback_data="button_add")])
        rows.append([InlineKeyboardButton("back", callback_data="settings_back"), InlineKeyboardButton("Delete", callback_data="button_delete")])
        text = "<b>Custom Button:</b>\n\nYou can add a custom button to your message"
        return await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(rows))

    if data == "button_add":
        await query.answer()
        await query.message.edit_text(
            "Send text for button",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❮ BACK", callback_data="custom_button")]])
        )
        try:
            ans_txt = await client.listen(chat_id=user_id, timeout=120)
        except Exception:
            return
        btn_txt = (ans_txt.text or "").strip()
        try:
            await ans_txt.delete()
        except Exception:
            pass
        if not btn_txt or btn_txt.startswith("/"):
            return await query.message.edit_text("❌ Cancelled.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❮ BACK", callback_data="custom_button")]]))
        
        await query.message.edit_text(
            "Send url for button",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❮ BACK", callback_data="custom_button")]])
        )
        try:
            ans_url = await client.listen(chat_id=user_id, timeout=120)
        except Exception:
            return
        btn_url = (ans_url.text or "").strip()
        try:
            await ans_url.delete()
        except Exception:
            pass
        if not (btn_url.startswith("http://") or btn_url.startswith("https://") or btn_url.startswith("tg://")):
            return await query.message.edit_text("❌ URL must start with http://, https:// or tg://", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❮ BACK", callback_data="custom_button")]]))
        btns = list(r.get("custom_buttons", []))
        btns.append({"text": btn_txt[:64], "url": btn_url})
        save(client, custom_buttons=btns)
        await update_user_info(user_id, {"custom_buttons": btns})
        return await query.message.edit_text(
            "✨ <b>Successfully Button Added</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❮ BACK", callback_data="custom_button")]])
        )

    if data == "button_delete":
        save(client, custom_buttons=[])
        await update_user_info(user_id, {"custom_buttons": []})
        await query.answer("Custom buttons deleted.", show_alert=True)
        return await query.message.edit_text(
            "<b>Custom Button:</b>\n\nYou can add a custom button to your message",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("➕", callback_data="button_add")],
                [InlineKeyboardButton("back", callback_data="settings_back")]
            ])
        )


def register(client):
    client.add_handler(MessageHandler(settings, filters.command("settings") & filters.private), group=0)
    client.add_handler(CallbackQueryHandler(callbacks, filters.regex(r"^(settings|settings_back|link_shortener|add_shortener|delete_shortener|protect_menu|protect_toggle|custom_caption|caption_see|caption_delete|caption_edit|custom_button|button_add|button_delete)$")), group=0)
    return client

