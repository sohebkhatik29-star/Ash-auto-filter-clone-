from pyrogram import Client, filters, StopPropagation
from pyrogram.handlers import MessageHandler, CallbackQueryHandler
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from config import ADMINS, SUPPORT_GROUP, UPDATE_CHANNEL, BOT_USERNAME, PICS, tg_link
from Script import script
from clone_plugins.master_manager import docs_for, list_markup, manage_clone, clone_manage_action, clone_delete, get_bot
from plugins.users_api import (
    get_user, update_user_info, validate_shortener_token,
    parse_time_string, format_time_minutes, is_user_premium
)
import random
import re
import time


async def edit_or_reply(query_or_msg, text, reply_markup=None, disable_web_page_preview=False):
    msg = getattr(query_or_msg, "message", None) or query_or_msg
    if not msg:
        return
    if getattr(msg, "photo", None) or getattr(msg, "media", None):
        try:
            return await msg.edit_caption(caption=text, reply_markup=reply_markup)
        except Exception:
            try:
                await msg.delete()
            except Exception:
                pass
            return await msg.reply_text(text=text, reply_markup=reply_markup, disable_web_page_preview=disable_web_page_preview)
    else:
        try:
            return await msg.edit_text(text=text, reply_markup=reply_markup, disable_web_page_preview=disable_web_page_preview)
        except Exception:
            return await msg.reply_text(text=text, reply_markup=reply_markup, disable_web_page_preview=disable_web_page_preview)


def master_settings_markup():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🤖 MY CLONE BOT ↗", callback_data="my_clone")],
        [InlineKeyboardButton("💳 PREMIUM PLAN", callback_data="master_premium_plan")],
        [InlineKeyboardButton("🔗 LINK SHORTNER", callback_data="link_shortener")],
        [InlineKeyboardButton("⏰ TOKEN VERIFICATION", callback_data="master_token_verification:1")],
        [InlineKeyboardButton("🍿 CUSTOM CAPTION", callback_data="custom_caption")],
        [InlineKeyboardButton("📢 CUSTOM FORCE SUBSCRIBE", callback_data="master_fsub_menu")],
        [InlineKeyboardButton("🔘 CUSTOM BUTTON", callback_data="custom_button")],
        [InlineKeyboardButton("♻️ AUTO DELETE", callback_data="master_auto_delete_menu")],
        [InlineKeyboardButton("🔒 PROTECT CONTENT", callback_data="protect_menu")],
        [InlineKeyboardButton("‹ BACK", callback_data="settings_back")],
    ])


def manage_clones_markup(uid):
    docs = docs_for(uid)
    rows = []
    for d in docs:
        bid = int(d["bot_id"])
        name = d.get("name") or d.get("username") or str(bid)
        rows.append([InlineKeyboardButton(f"{name}", callback_data=f"manage_clone:{bid}")])
    rows.append([InlineKeyboardButton("➕ Add Clone", callback_data="add_clone_prompt")])
    rows.append([InlineKeyboardButton("‹ back", callback_data="master_settings")])
    return InlineKeyboardMarkup(rows)


async def send_manage_clones(client, message, user_id=None):
    uid = user_id or message.from_user.id
    text = (
        "✨ <b>Manage Clone's</b>\n\n"
        "You can now manage and create your very own identical clone bot, "
        "mirroring all my awesome features, using the given buttons."
    )
    markup = manage_clones_markup(uid)
    if hasattr(message, "reply_text"):
        return await message.reply_text(text, reply_markup=markup)
    return await message.reply(text, reply_markup=markup)


async def send_settings_menu(client, message):
    text = "⚙️ <b>Settings</b>\n\nCustomize your settings as your need"
    if hasattr(message, "reply_text"):
        return await message.reply_text(
            text,
            reply_markup=master_settings_markup(),
        )
    return await message.reply(
        text,
        reply_markup=master_settings_markup(),
    )


async def settings(client, message):
    await send_settings_menu(client, message)
    raise StopPropagation


async def callbacks(client, query):
    data = query.data or ""

    if data in ("settings", "master_settings"):
        text = "⚙️ <b>Settings</b>\n\nCustomize your settings as your need"
        await edit_or_reply(query, text, reply_markup=master_settings_markup())
        await query.answer()
        raise StopPropagation

    if data in ("my_clone", "my_clones"):
        text = (
            "✨ <b>Manage Clone's</b>\n\n"
            "You can now manage and create your very own identical clone bot, "
            "mirroring all my awesome features, using the given buttons."
        )
        markup = manage_clones_markup(query.from_user.id)
        await edit_or_reply(query, text, reply_markup=markup)
        await query.answer()
        raise StopPropagation

    if data in ("add_clone_prompt", "clone"):
        prompt_text = (
            "1) create a bot using @BotFather\n"
            "2) Then you will get a message with bot token\n"
            "3) Send that bot token to me"
        )
        await edit_or_reply(query, 
            prompt_text,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ back", callback_data="my_clones")]])
        )
        await query.answer()
        try:
            token_msg = await client.listen(chat_id=query.from_user.id, timeout=180)
        except Exception:
            return
        
        raw_text = (token_msg.text or "").strip()
        if raw_text.lower() == "/cancel":
            await edit_or_reply(query, 
                "<b>Cancelled 🚫</b>",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ back", callback_data="my_clones")]])
            )
            raise StopPropagation
        
        match = re.search(r"\b(\d+:[A-Za-z0-9_-]+)\b", raw_text)
        if not match:
            await edit_or_reply(query, 
                "❌ <b>Could not read the bot token. Please forward the token message from @BotFather.</b>",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ back", callback_data="my_clones")]])
            )
            raise StopPropagation
        
        bot_token = match.group(1)
        await edit_or_reply(query, "<b>👨‍💻 Cloning your bot...</b>")
        try:
            from plugins.clone import set_clone_menu, register_clone_handlers, mongo_db
            from config import API_ID, API_HASH
            vj = Client(f"clone_{query.from_user.id}_{int(match.group(1).split(':')[0])}", API_ID, API_HASH, bot_token=bot_token, plugins={})
            await vj.start()
            register_clone_handlers(vj)
            bot = await vj.get_me()
            if mongo_db is not None:
                mongo_db.bots.update_one({"bot_id": bot.id}, {"$set": {
                    "bot_id": bot.id, "is_bot": True, "user_id": query.from_user.id,
                    "name": bot.first_name, "token": bot_token, "username": bot.username,
                    "force_channels": [], "custom_caption": None, "custom_buttons": [],
                    "protect_content": False, "no_forward": False, "auto_delete_enabled": False,
                    "auto_delete_minutes": 15, "access_token_enabled": False, "access_token_hours": 1,
                    "moderators": [], "mode": "private", "deactivated": False, "hide_owner": False
                }}, upsert=True)
            await set_clone_menu(vj, query.from_user.id)
            await edit_or_reply(query, 
                "✨ <b>Sucessfully Cloned Your Bot</b>",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="my_clones")]])
            )
        except Exception as e:
            await edit_or_reply(query, 
                f"⚠️ <b>Bot Error:</b>\n\n<code>{e}</code>",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ back", callback_data="my_clones")]])
            )
        raise StopPropagation

    if data in ("google_backup", "master_google_backup"):
        text = (
            "<b>Clone Backup</b>\n\n"
            "You can connect a google account to retrieve ownership and data of clones in this tg account, "
            "if this account is deleted or you loose access to it, use /recover to restore them."
        )
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("Connect With Google", callback_data="google_connect")],
            [InlineKeyboardButton("‹ back", callback_data="master_settings")]
        ])
        await edit_or_reply(query, text, reply_markup=markup)
        await query.answer()
        raise StopPropagation

    if data == "google_connect":
        await query.answer("Google Drive backup is stored securely in MongoDB database.", show_alert=True)
        raise StopPropagation

    if data in ("log_channel", "master_log_channel"):
        user = await get_user(query.from_user.id)
        log_ch = user.get("log_channel")
        log_title = user.get("log_channel_title")
        if log_ch:
            status_text = f"<b>YOUR LOG CHANNEL - {log_title or log_ch}</b>"
        else:
            status_text = "<b>YOU DIDN'T ADDED ANY LOG CHANNEL ❗</b>"

        text = (
            "📢 <b>LOG CHANNEL:</b>\n\n"
            "<b>\"WHAT IS LOG CHANNEL ??\"</b>\n"
            "IF NEW USERS START YOUR BOT THEN BOT NOTIFIES YOU.\n\n"
            f"{status_text}"
        )
        markup = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("SET CHANNEL", callback_data="master_set_log_channel"),
                InlineKeyboardButton("DELETE CHANNEL", callback_data="master_delete_log_channel")
            ],
            [InlineKeyboardButton("‹ BACK", callback_data="master_settings")]
        ])
        await edit_or_reply(query, text, reply_markup=markup)
        await query.answer()
        raise StopPropagation

    if data == "master_set_log_channel":
        await query.answer()
        me = client.me or (await client.get_me())
        prompt_text = (
            "<b>FORWARD LOG CHANNEL ANY MESSAGE TO ME,\n"
            f"AND MAKE SURE @{me.username} IS ADMIN IN YOUR CHANNEL.</b>\n\n"
            "<code>/cancel</code> - <b>CANCEL THIS PROCESS.</b>"
        )
        await edit_or_reply(query, 
            prompt_text,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="master_log_channel")]])
        )
        try:
            ch_msg = await client.listen(chat_id=query.from_user.id, timeout=120)
        except Exception:
            raise StopPropagation

        ch_raw = (ch_msg.text or "").strip()
        try:
            await ch_msg.delete()
        except Exception:
            pass

        if ch_raw.lower() == "/cancel":
            await edit_or_reply(query, 
                "❌ <b>Process Cancelled.</b>",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="master_log_channel")]])
            )
            raise StopPropagation

        channel_id = None
        channel_title = None

        if ch_msg.forward_from_chat:
            channel_id = ch_msg.forward_from_chat.id
            channel_title = ch_msg.forward_from_chat.title
        elif ch_raw.startswith("-100") or (ch_raw.startswith("-") and ch_raw[1:].isdigit()):
            channel_id = int(ch_raw)
        elif ch_raw.isdigit():
            channel_id = int(f"-100{ch_raw}")
        elif ch_raw.startswith("@"):
            try:
                chat = await client.get_chat(ch_raw)
                channel_id = chat.id
                channel_title = chat.title
            except Exception:
                pass

        if not channel_id:
            await edit_or_reply(query, 
                "❌ <b>Invalid Channel! Please forward a message directly from your channel.</b>",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="master_log_channel")]])
            )
            raise StopPropagation

        try:
            chat = await client.get_chat(channel_id)
            channel_title = chat.title or channel_title or str(channel_id)
            await client.send_message(
                chat_id=channel_id,
                text=f"⚡ <b>Log channel successfully connected with @{me.username}!</b>"
            )
        except Exception as err:
            await edit_or_reply(query, 
                f"❌ <b>Failed to connect channel!</b>\n\nMake sure <b>@{me.username}</b> is an <b>ADMIN</b> in the channel with post permissions.\n\n<code>Error: {err}</code>",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="master_log_channel")]])
            )
            raise StopPropagation

        await update_user_info(query.from_user.id, {"log_channel": channel_id, "log_channel_title": channel_title})
        await edit_or_reply(query, 
            f"⚡ <b>SUCCESSFULLY ADDED YOUR LOG CHANNEL - {channel_title}</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="master_log_channel")]])
        )
        raise StopPropagation

    if data == "master_delete_log_channel":
        await update_user_info(query.from_user.id, {"log_channel": None, "log_channel_title": None})
        await query.answer("🗑️ Successfully deleted your log channel", show_alert=False)
        await edit_or_reply(query, 
            "🗑️ <b>SUCCESSFULLY DELETED LOG CHANNEL</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="master_log_channel")]])
        )
        raise StopPropagation

    if data in ("database_channel", "master_database_channel"):
        user = await get_user(query.from_user.id)
        db_ch = user.get("database_channel")
        db_title = user.get("database_channel_title")
        if db_ch:
            status_text = f"<b>YOUR DATABASE CHANNEL - {db_title or db_ch}</b>"
        else:
            status_text = "<b>YOU DIDN'T ADDED ANY DATABASE CHANNEL ❗</b>"

        text = (
            "☁️ <b>DATABASE CHANNEL:</b>\n\n"
            "<b>WHAT IS DATABASE CHANNEL ❓</b>\n\n"
            "<b>DATABASE CHANNEL MEANS WHEN YOU STORE ANYTHING IN FILE STORE BOT ALL MESSAGES BOT WILL STORE IN YOUR DATABASE CHANNEL IF YOU DELETE THAT MESSAGE THEN BOT CAN NOT GIVE IT TO ANYONE.</b>\n\n"
            f"{status_text}"
        )
        markup = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("SET CHANNEL", callback_data="master_set_database_channel"),
                InlineKeyboardButton("DELETE CHANNEL", callback_data="master_delete_database_channel")
            ],
            [InlineKeyboardButton("‹ BACK", callback_data="master_settings")]
        ])
        await edit_or_reply(query, text, reply_markup=markup)
        await query.answer()
        raise StopPropagation

    if data == "master_set_database_channel":
        await query.answer()
        me = client.me or (await client.get_me())
        prompt_text = (
            "<b>FORWARD DATABASE CHANNEL ANY MESSAGE TO ME,\n"
            f"AND MAKE SURE @{me.username} IS ADMIN IN YOUR CHANNEL.</b>\n\n"
            "<code>/cancel</code> - <b>CANCEL THIS PROCESS.</b>"
        )
        await edit_or_reply(query, 
            prompt_text,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="master_database_channel")]])
        )
        try:
            ch_msg = await client.listen(chat_id=query.from_user.id, timeout=120)
        except Exception:
            raise StopPropagation

        ch_raw = (ch_msg.text or "").strip()
        try:
            await ch_msg.delete()
        except Exception:
            pass

        if ch_raw.lower() == "/cancel":
            await edit_or_reply(query, 
                "❌ <b>Process Cancelled.</b>",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="master_database_channel")]])
            )
            raise StopPropagation

        channel_id = None
        channel_title = None

        if ch_msg.forward_from_chat:
            channel_id = ch_msg.forward_from_chat.id
            channel_title = ch_msg.forward_from_chat.title
        elif ch_raw.startswith("-100") or (ch_raw.startswith("-") and ch_raw[1:].isdigit()):
            channel_id = int(ch_raw)
        elif ch_raw.isdigit():
            channel_id = int(f"-100{ch_raw}")
        elif ch_raw.startswith("@"):
            try:
                chat = await client.get_chat(ch_raw)
                channel_id = chat.id
                channel_title = chat.title
            except Exception:
                pass

        if not channel_id:
            await edit_or_reply(query, 
                "❌ <b>Invalid Channel! Please forward a message directly from your channel.</b>",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="master_database_channel")]])
            )
            raise StopPropagation

        try:
            chat = await client.get_chat(channel_id)
            channel_title = chat.title or channel_title or str(channel_id)
            await client.send_message(
                chat_id=channel_id,
                text=f"⚡ <b>Database channel successfully connected with @{me.username}!</b>"
            )
        except Exception as err:
            await edit_or_reply(query, 
                f"❌ <b>Failed to connect channel!</b>\n\nMake sure <b>@{me.username}</b> is an <b>ADMIN</b> in the channel with post permissions.\n\n<code>Error: {err}</code>",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="master_database_channel")]])
            )
            raise StopPropagation

        await update_user_info(query.from_user.id, {"database_channel": channel_id, "database_channel_title": channel_title})
        await edit_or_reply(query, 
            f"⚡ <b>SUCCESSFULLY ADDED YOUR DATABASE CHANNEL - {channel_title}</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="master_database_channel")]])
        )
        raise StopPropagation

    if data == "master_delete_database_channel":
        await update_user_info(query.from_user.id, {"database_channel": None, "database_channel_title": None})
        await query.answer("🗑️ Successfully deleted your database channel", show_alert=False)
        await edit_or_reply(query, 
            "🗑️ <b>SUCCESSFULLY DELETED DATABASE CHANNEL</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="master_database_channel")]])
        )
        raise StopPropagation

    if data == "link_shortener":
        user = await get_user(query.from_user.id)
        site = user.get("base_site")
        api = user.get("shortener_api")
        if not (site and api):
            text = (
                "<b>Link Shortener</b>\n\n"
                "To shorten your links using your preferred provider, make sure to connect it with me first."
            )
            markup = InlineKeyboardMarkup([
                [InlineKeyboardButton("Add Shortener", callback_data="master_add_shortener")],
                [InlineKeyboardButton("back", callback_data="master_settings")]
            ])
            await edit_or_reply(query, text, reply_markup=markup)
            await query.answer()
            raise StopPropagation

        text = (
            "<b>Link Shortener</b>\n\n"
            f"- Shortener: {site}\n"
            f"- Shortener Api: {api}\n\n"
            "You can now use the /shortener command to shorten any links."
        )
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("Delete shortener", callback_data="delete_shortener")],
            [InlineKeyboardButton("back", callback_data="master_settings")]
        ])
        await edit_or_reply(query, text, reply_markup=markup)
        await query.answer()
        raise StopPropagation

    if data == "master_add_shortener":
        await query.answer()
        await edit_or_reply(query, 
            "Send your shortener site url\n\neg: https://droplink.co",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="link_shortener")]]),
            disable_web_page_preview=True
        )
        try:
            site_msg = await client.listen(chat_id=query.from_user.id, timeout=120)
        except Exception:
            raise StopPropagation

        site_raw = (site_msg.text or "").strip()
        try:
            await site_msg.delete()
        except Exception:
            pass

        if not site_raw or site_raw.startswith("/"):
            await edit_or_reply(query, "❌ Cancelled.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="link_shortener")]]))
            raise StopPropagation
        site_clean = site_raw.replace("https://", "").replace("http://", "").split("/")[0].strip()
        if not site_clean or "." not in site_clean:
            await edit_or_reply(query, "❌ Invalid site URL.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="link_shortener")]]))
            raise StopPropagation

        await edit_or_reply(query, 
            f"Send your shortener ({site_clean}) api token, get it from <a href='https://{site_clean}/member/tools/api'>here</a>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="link_shortener")]]),
            disable_web_page_preview=True
        )

        try:
            api_msg = await client.listen(chat_id=query.from_user.id, timeout=120)
        except Exception:
            raise StopPropagation

        api_raw = (api_msg.text or "").strip()
        try:
            await api_msg.delete()
        except Exception:
            pass

        if not api_raw or api_raw.startswith("/"):
            await edit_or_reply(query, "❌ Cancelled.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="link_shortener")]]))
            raise StopPropagation

        is_valid = await validate_shortener_token(site_clean, api_raw)
        if not is_valid:
            await edit_or_reply(query, 
                "The given Shortener Api Token is invalid",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="link_shortener")]])
            )
            raise StopPropagation

        await update_user_info(query.from_user.id, {"base_site": site_clean, "shortener_api": api_raw})
        await edit_or_reply(query, 
            f"✨ <b>Successfully {site_clean} added as your link shortener Provider</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="link_shortener")]])
        )
        raise StopPropagation

    if data == "delete_shortener":
        await update_user_info(query.from_user.id, {"base_site": None, "shortener_api": None})
        await query.answer("✨ Successfully deleted your link shortener provider", show_alert=False)
        text = "✨ <b>Successfully deleted your link shortener provider</b>"
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("‹ BACK", callback_data="link_shortener")]
        ])
        await edit_or_reply(query, text, reply_markup=markup)
        raise StopPropagation

    if data == "custom_caption":
        user = await get_user(query.from_user.id)
        text = (
            "<b>Custom Caption:</b>\n"
            "You can add a custom caption to your media messages instead of its original caption\n\n"
            "<b>Fillings:</b>\n"
            "• {file_name} : File Name\n"
            "• {file_size} : File Size\n"
            "• {caption} : Orginal Caption"
        )
        cap = user.get("custom_caption")
        if cap:
            text += f"\n\n<b>Current:</b> <code>{cap}</code>"
        markup = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Edit", callback_data="caption_edit"),
                InlineKeyboardButton("See", callback_data="caption_see"),
                InlineKeyboardButton("Delete", callback_data="caption_delete")
            ],
            [InlineKeyboardButton("‹ back", callback_data="master_settings")]
        ])
        await edit_or_reply(query, text, reply_markup=markup)
        await query.answer()
        raise StopPropagation

    if data == "caption_see":
        user = await get_user(query.from_user.id)
        cap = user.get("custom_caption")
        if cap:
            text = (
                "<b>👀 Current Custom Caption:</b>\n\n"
                f"<code>{cap}</code>\n\n"
                "<b>Fillings:</b>\n"
                "• {file_name} : File Name\n"
                "• {file_size} : File Size\n"
                "• {caption} : Orginal Caption"
            )
        else:
            text = (
                "<b>👀 Current Custom Caption:</b>\n\n"
                "<i>No custom caption set. Default caption will be used.</i>\n\n"
                "<b>Fillings:</b>\n"
                "• {file_name} : File Name\n"
                "• {file_size} : File Size\n"
                "• {caption} : Orginal Caption"
            )
        await query.answer()
        markup = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Edit", callback_data="caption_edit"),
                InlineKeyboardButton("Delete", callback_data="caption_delete")
            ],
            [InlineKeyboardButton("‹ back", callback_data="custom_caption")]
        ])
        await edit_or_reply(query, text, reply_markup=markup)
        raise StopPropagation

    if data == "caption_delete":
        await update_user_info(query.from_user.id, {"custom_caption": None})
        await query.answer("Custom caption deleted.", show_alert=True)
        text = (
            "<b>Custom Caption:</b>\n"
            "You can add a custom caption to your media messages instead of its original caption\n\n"
            "<b>Fillings:</b>\n"
            "• {file_name} : File Name\n"
            "• {file_size} : File Size\n"
            "• {caption} : Orginal Caption"
        )
        markup = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Edit", callback_data="caption_edit"),
                InlineKeyboardButton("See", callback_data="caption_see"),
                InlineKeyboardButton("Delete", callback_data="caption_delete")
            ],
            [InlineKeyboardButton("‹ back", callback_data="master_settings")]
        ])
        await edit_or_reply(query, text, reply_markup=markup)
        raise StopPropagation

    if data == "caption_edit":
        await query.answer("Send /caption <Your Text> to update caption.", show_alert=True)
        raise StopPropagation

    if data == "custom_button":
        text = "<b>Custom Button:</b>\nYou can add a custom button to your message"
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕", callback_data="button_add")],
            [InlineKeyboardButton("‹ back", callback_data="master_settings"), InlineKeyboardButton("Delete", callback_data="button_delete")]
        ])
        await edit_or_reply(query, text, reply_markup=markup)
        await query.answer()
        raise StopPropagation

    if data == "button_add":
        await query.answer("Send /button <Button Text> - <URL> to set custom button.", show_alert=True)
        raise StopPropagation

    if data == "button_delete":
        await update_user_info(query.from_user.id, {"custom_buttons": []})
        await query.answer("Custom button deleted.", show_alert=True)
        raise StopPropagation

    if data == "protect_menu":
        user = await get_user(query.from_user.id)
        is_on = bool(user.get("protect_content", False))
        status_str = "ENABLED ✅" if is_on else "DISABLED ❌"
        text = (
            "<b>Protect Content</b>\n"
            "Restrict other users from forwarding contents from your shareable link.\n\n"
            "<b>Available Mode's:</b>\n"
            "1) Enable: Forwarding is blocked. Once you create a link with this mode, the restriction remains even if you later disabled this feature.\n"
            "2) Disable: Forwarding restrictions depend on whether the \"no forward\" feature is currently enabled in the bot. If enabled, no forward is restricted. This applies to all links, including those created before; if disabled, forwarding is allowed.\n\n"
            f"- status: {status_str}"
        )
        btn = InlineKeyboardButton("Disable ❌", callback_data="protect_toggle_off") if is_on else InlineKeyboardButton("Enable ✅", callback_data="protect_toggle_on")
        markup = InlineKeyboardMarkup([
            [btn],
            [InlineKeyboardButton("‹ back", callback_data="master_settings")]
        ])
        await edit_or_reply(query, text, reply_markup=markup)
        await query.answer()
        raise StopPropagation

    if data in ("protect_toggle_on", "protect_toggle_off"):
        val = (data == "protect_toggle_on")
        await update_user_info(query.from_user.id, {"protect_content": val})
        status_str = "ENABLED ✅" if val else "DISABLED ❌"
        text = (
            "<b>Protect Content</b>\n"
            "Restrict other users from forwarding contents from your shareable link.\n\n"
            "<b>Available Mode's:</b>\n"
            "1) Enable: Forwarding is blocked. Once you create a link with this mode, the restriction remains even if you later disabled this feature.\n"
            "2) Disable: Forwarding restrictions depend on whether the \"no forward\" feature is currently enabled in the bot. If enabled, no forward is restricted. This applies to all links, including those created before; if disabled, forwarding is allowed.\n\n"
            f"- status: {status_str}"
        )
        btn = InlineKeyboardButton("Disable ❌", callback_data="protect_toggle_off") if val else InlineKeyboardButton("Enable ✅", callback_data="protect_toggle_on")
        markup = InlineKeyboardMarkup([
            [btn],
            [InlineKeyboardButton("‹ back", callback_data="master_settings")]
        ])
        await edit_or_reply(query, text, reply_markup=markup)
        await query.answer()
        raise StopPropagation

    if data == "start_photo_menu":
        user = await get_user(query.from_user.id)
        has_pic = bool(user.get("start_pic"))
        status_str = "CUSTOM PHOTO SET ✅" if has_pic else "DEFAULT PHOTO 🖼️"
        text = (
            "<b>Start Message Photo:</b>\n"
            "You can set a custom photo/banner that appears on /start command.\n\n"
            f"• <b>Status:</b> {status_str}\n\n"
            "• <b>Set/Edit:</b> Send <code>/set_pic https://example.com/image.jpg</code> or reply to a photo with <code>/set_pic</code>\n"
            "• <b>See:</b> View your current start photo\n"
            "• <b>Delete:</b> Reset to default photo"
        )
        markup = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Edit", callback_data="start_pic_edit"),
                InlineKeyboardButton("See", callback_data="start_pic_see"),
                InlineKeyboardButton("Delete", callback_data="start_pic_delete")
            ],
            [InlineKeyboardButton("‹ back", callback_data="master_settings")]
        ])
        await edit_or_reply(query, text, reply_markup=markup)
        await query.answer()
        raise StopPropagation

    if data == "start_pic_edit":
        await query.answer("Send /set_pic <Image_URL> or reply to a photo with /set_pic", show_alert=True)
        raise StopPropagation

    if data == "start_pic_see":
        user = await get_user(query.from_user.id)
        pic = user.get("start_pic")
        if pic:
            try:
                await client.send_photo(chat_id=query.from_user.id, photo=pic, caption="🖼️ <b>Your Custom Start Photo</b>")
                await query.answer()
            except Exception:
                await query.answer(f"Photo URL:\n{pic}", show_alert=True)
        else:
            await query.answer("You are currently using the default start photo.", show_alert=True)
        raise StopPropagation

    if data == "start_pic_delete":
        await update_user_info(query.from_user.id, {"start_pic": None})
        await query.answer("Start photo reset to default.", show_alert=True)
        text = (
            "<b>Start Message Photo:</b>\n"
            "You can set a custom photo/banner that appears on /start command.\n\n"
            "• <b>Status:</b> DEFAULT PHOTO 🖼️\n\n"
            "• <b>Set/Edit:</b> Send <code>/set_pic https://example.com/image.jpg</code> or reply to a photo with <code>/set_pic</code>\n"
            "• <b>See:</b> View your current start photo\n"
            "• <b>Delete:</b> Reset to default photo"
        )
        markup = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Edit", callback_data="start_pic_edit"),
                InlineKeyboardButton("See", callback_data="start_pic_see"),
                InlineKeyboardButton("Delete", callback_data="start_pic_delete")
            ],
            [InlineKeyboardButton("‹ back", callback_data="master_settings")]
        ])
        await edit_or_reply(query, text, reply_markup=markup)
        raise StopPropagation

    # ---------------- TOKEN VERIFICATION ----------------
    if data.startswith("master_token_verification:"):
        slot = int(data.split(":")[1])
        user = await get_user(query.from_user.id)
        v_key = f"verify_{slot}" if slot > 1 else "verify_1"
        v_cfg = user.get(v_key, {})
        is_on = bool(v_cfg.get("is_on", False))
        
        prefix = "VERIFY" if slot == 1 else ("SECOND" if slot == 2 else "THIRD")
        next_slot = (slot % 3) + 1
        next_name = "SECOND VERIFICATION" if slot == 1 else ("THIRD VERIFICATION" if slot == 2 else "FIRST VERIFICATION")
        status_text = "VERIFY IS ON - ✅" if is_on else "VERIFY IS OFF - ❌"

        text = "<b>MANAGE YOUR TOKEN VERIFICATION SETTINGS FROM HERE GIVEN BELOW BUTTONS</b>"
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"🔗 {prefix} SHORTNER", callback_data=f"master_v_shortner:{slot}")],
            [InlineKeyboardButton(f"🎬 {prefix} TUTORIAL", callback_data=f"master_v_tutorial:{slot}")],
            [InlineKeyboardButton(f"⏳ {prefix} TIME", callback_data=f"master_v_time:{slot}")],
            [InlineKeyboardButton(f"⏰ {next_name}", callback_data=f"master_token_verification:{next_slot}")],
            [InlineKeyboardButton(f"🔒 {status_text}", callback_data=f"master_v_toggle:{slot}")],
            [InlineKeyboardButton("‹ BACK", callback_data="master_settings")]
        ])
        await edit_or_reply(query, text, reply_markup=markup)
        await query.answer()
        raise StopPropagation

    if data.startswith("master_v_toggle:"):
        slot = int(data.split(":")[1])
        user = await get_user(query.from_user.id)
        v_key = f"verify_{slot}" if slot > 1 else "verify_1"
        v_cfg = user.get(v_key, {})
        curr_state = bool(v_cfg.get("is_on", False))
        
        site = v_cfg.get("site") or user.get("base_site")
        api = v_cfg.get("api") or user.get("shortener_api")
        tut = v_cfg.get("tutorial")
        
        if not curr_state and (not site or not api or not tut):
            await query.answer("YOU DON NOT ADDED SHORTLINK AND TUTORIAL LINK FOR VERIFICATION, FIRST ADD IT THEN TURN ME ON", show_alert=True)
            raise StopPropagation
        
        new_state = not curr_state
        v_cfg["is_on"] = new_state
        await update_user_info(query.from_user.id, {v_key: v_cfg})
        
        prefix = "VERIFY" if slot == 1 else ("SECOND" if slot == 2 else "THIRD")
        next_slot = (slot % 3) + 1
        next_name = "SECOND VERIFICATION" if slot == 1 else ("THIRD VERIFICATION" if slot == 2 else "FIRST VERIFICATION")
        status_text = "VERIFY IS ON - ✅" if new_state else "VERIFY IS OFF - ❌"

        text = "<b>MANAGE YOUR TOKEN VERIFICATION SETTINGS FROM HERE GIVEN BELOW BUTTONS</b>"
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"🔗 {prefix} SHORTNER", callback_data=f"master_v_shortner:{slot}")],
            [InlineKeyboardButton(f"🎬 {prefix} TUTORIAL", callback_data=f"master_v_tutorial:{slot}")],
            [InlineKeyboardButton(f"⏳ {prefix} TIME", callback_data=f"master_v_time:{slot}")],
            [InlineKeyboardButton(f"⏰ {next_name}", callback_data=f"master_token_verification:{next_slot}")],
            [InlineKeyboardButton(f"🔒 {status_text}", callback_data=f"master_v_toggle:{slot}")],
            [InlineKeyboardButton("‹ BACK", callback_data="master_settings")]
        ])
        await edit_or_reply(query, text, reply_markup=markup)
        await query.answer()
        raise StopPropagation

    if data.startswith("master_v_shortner:"):
        slot = int(data.split(":")[1])
        await query.answer()
        prompt_text = (
            "<b>SEND ME A SHORTLINK URL...</b>\n\n"
            "<b>FORMAT :</b>\n"
            "<code>https://vjlink.online</code> - ❌\n"
            "<code>vjlink.online</code> - ✅\n\n"
            "<code>/cancel</code> - <b>Cancel THIS PROCESS.</b>"
        )
        await edit_or_reply(query, 
            prompt_text,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data=f"master_token_verification:{slot}")]])
        )
        try:
            site_msg = await client.listen(chat_id=query.from_user.id, timeout=120)
        except Exception:
            raise StopPropagation

        site_raw = (site_msg.text or "").strip()
        try:
            await site_msg.delete()
        except Exception:
            pass

        if site_raw.lower() == "/cancel":
            await edit_or_reply(query, "❌ <b>Process Cancelled.</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data=f"master_token_verification:{slot}")]]))
            raise StopPropagation

        site_clean = site_raw.replace("https://", "").replace("http://", "").split("/")[0].strip()
        if not site_clean or "." not in site_clean:
            await edit_or_reply(query, "❌ <b>Invalid site URL.</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data=f"master_token_verification:{slot}")]]))
            raise StopPropagation

        await edit_or_reply(query, 
            "<b>SEND ME SHORTLINK API...</b>\n\n"
            "<code>/cancel</code> - <b>Cancel THIS PROCESS.</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data=f"master_token_verification:{slot}")]])
        )
        try:
            api_msg = await client.listen(chat_id=query.from_user.id, timeout=120)
        except Exception:
            raise StopPropagation

        api_raw = (api_msg.text or "").strip()
        try:
            await api_msg.delete()
        except Exception:
            pass

        if api_raw.lower() == "/cancel":
            await edit_or_reply(query, "❌ <b>Process Cancelled.</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data=f"master_token_verification:{slot}")]]))
            raise StopPropagation

        is_valid = await validate_shortener_token(site_clean, api_raw)
        if not is_valid:
            await edit_or_reply(query, 
                "❌ <b>The given Shortener Api Token is invalid</b>",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data=f"master_token_verification:{slot}")]])
            )
            raise StopPropagation

        user = await get_user(query.from_user.id)
        v_key = f"verify_{slot}" if slot > 1 else "verify_1"
        v_cfg = user.get(v_key, {})
        v_cfg["site"] = site_clean
        v_cfg["api"] = api_raw
        await update_user_info(query.from_user.id, {v_key: v_cfg, "base_site": site_clean, "shortener_api": api_raw})

        await edit_or_reply(query, 
            "<b>SUCCESSFULLY SET SHORTLINK ✅</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data=f"master_token_verification:{slot}")]])
        )
        raise StopPropagation

    if data.startswith("master_v_tutorial:"):
        slot = int(data.split(":")[1])
        user = await get_user(query.from_user.id)
        v_key = f"verify_{slot}" if slot > 1 else "verify_1"
        v_cfg = user.get(v_key, {})
        tut = v_cfg.get("tutorial") or "Not set"

        text = (
            "<b>HERE YOU CAN MANAGE YOUR BOT TOKEN VERIFICATION LINK SHORTNER TUTORIAL VIDEO LINK FOR HOW TO OPEN LINK.</b>\n\n"
            f"<b>LINK -</b> {tut}"
        )
        markup = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("SET TUTORIAL", callback_data=f"master_v_set_tut:{slot}"),
                InlineKeyboardButton("DELETE TUTORIAL", callback_data=f"master_v_del_tut:{slot}")
            ],
            [InlineKeyboardButton("‹ BACK", callback_data=f"master_token_verification:{slot}")]
        ])
        await edit_or_reply(query, text, reply_markup=markup, disable_web_page_preview=True)
        await query.answer()
        raise StopPropagation

    if data.startswith("master_v_set_tut:"):
        slot = int(data.split(":")[1])
        await query.answer()
        await edit_or_reply(query, 
            "<b>SEND ME A TUTORIAL LINK...</b>\n\n"
            "<code>/cancel</code> - <b>Cancel THIS PROCESS.</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data=f"master_v_tutorial:{slot}")]])
        )
        try:
            t_msg = await client.listen(chat_id=query.from_user.id, timeout=120)
        except Exception:
            raise StopPropagation

        t_raw = (t_msg.text or "").strip()
        try:
            await t_msg.delete()
        except Exception:
            pass

        if t_raw.lower() == "/cancel":
            await edit_or_reply(query, "❌ <b>Process Cancelled.</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data=f"master_v_tutorial:{slot}")]]))
            raise StopPropagation

        user = await get_user(query.from_user.id)
        v_key = f"verify_{slot}" if slot > 1 else "verify_1"
        v_cfg = user.get(v_key, {})
        v_cfg["tutorial"] = t_raw
        await update_user_info(query.from_user.id, {v_key: v_cfg})

        await edit_or_reply(query, 
            "<b>SUCCESSFULLY SET TUTORIAL LINK ✅</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data=f"master_v_tutorial:{slot}")]])
        )
        raise StopPropagation

    if data.startswith("master_v_del_tut:"):
        slot = int(data.split(":")[1])
        user = await get_user(query.from_user.id)
        v_key = f"verify_{slot}" if slot > 1 else "verify_1"
        v_cfg = user.get(v_key, {})
        v_cfg["tutorial"] = None
        await update_user_info(query.from_user.id, {v_key: v_cfg})
        await query.answer("Tutorial link deleted.", show_alert=True)
        await edit_or_reply(query, 
            "🗑️ <b>SUCCESSFULLY DELETED TUTORIAL LINK</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data=f"master_v_tutorial:{slot}")]])
        )
        raise StopPropagation

    if data.startswith("master_v_time:"):
        slot = int(data.split(":")[1])
        user = await get_user(query.from_user.id)
        v_key = f"verify_{slot}" if slot > 1 else "verify_1"
        v_cfg = user.get(v_key, {})
        mins = v_cfg.get("time_minutes", 480)
        time_str = format_time_minutes(mins)

        text = (
            "<b>HERE YOU CAN MANAGE YOUR BOT VERIFICATION TIME SETTING.</b>\n\n"
            f"<b>TIME -</b> {time_str}"
        )
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("SET TIME", callback_data=f"master_v_set_time:{slot}")],
            [InlineKeyboardButton("‹ BACK", callback_data=f"master_token_verification:{slot}")]
        ])
        await edit_or_reply(query, text, reply_markup=markup)
        await query.answer()
        raise StopPropagation

    if data.startswith("master_v_set_time:"):
        slot = int(data.split(":")[1])
        await query.answer()
        await edit_or_reply(query, 
            "<b>SEND ME A TIME IN LIKE THIS - 1h OR 15m</b>\n\n"
            "<code>/cancel</code> - <b>Cancel THIS PROCESS.</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data=f"master_v_time:{slot}")]])
        )
        try:
            tm_msg = await client.listen(chat_id=query.from_user.id, timeout=120)
        except Exception:
            raise StopPropagation

        tm_raw = (tm_msg.text or "").strip()
        try:
            await tm_msg.delete()
        except Exception:
            pass

        if tm_raw.lower() == "/cancel":
            await edit_or_reply(query, "❌ <b>Process Cancelled.</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data=f"master_v_time:{slot}")]]))
            raise StopPropagation

        mins = parse_time_string(tm_raw)
        user = await get_user(query.from_user.id)
        v_key = f"verify_{slot}" if slot > 1 else "verify_1"
        v_cfg = user.get(v_key, {})
        v_cfg["time_minutes"] = mins
        await update_user_info(query.from_user.id, {v_key: v_cfg})

        formatted = format_time_minutes(mins)
        await edit_or_reply(query, 
            f"🧭 <b>SUCCESSFULLY SET VERIFY TIME - {formatted}</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data=f"master_token_verification:{slot}")]])
        )
        raise StopPropagation

    # ---------------- PREMIUM PLAN ----------------
    if data == "master_premium_plan":
        user = await get_user(query.from_user.id)
        prem_on = bool(user.get("premium_is_on", False))
        prem_status = "PREMIUM IS ON - ✅" if prem_on else "PREMIUM IS OFF - ❌"
        text = (
            "<b>HERE YOU CAN MANAGE YOUR PREMIUM SETTINGS HERE</b>\n\n"
            "<b>THIS FEATURE WORK ONLY WHEN TOKEN VERIFICATION IS ENABLED</b>"
        )
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("📝 PREMIUM PLAN TEXT 📝", callback_data="master_prem_text")],
            [InlineKeyboardButton("➕ ADD PREMIUM USER ➕", callback_data="master_prem_add")],
            [InlineKeyboardButton("➖ REMOVE PREMIUM USER ➖", callback_data="master_prem_rem")],
            [InlineKeyboardButton("👥 PREMIUM USERS LIST 👥", callback_data="master_prem_list")],
            [InlineKeyboardButton(f"🔒 {prem_status}", callback_data="master_prem_toggle")],
            [InlineKeyboardButton("‹ BACK", callback_data="master_settings")]
        ])
        await edit_or_reply(query, text, reply_markup=markup)
        await query.answer()
        raise StopPropagation

    if data == "master_prem_toggle":
        user = await get_user(query.from_user.id)
        new_on = not bool(user.get("premium_is_on", False))
        await update_user_info(query.from_user.id, {"premium_is_on": new_on})
        prem_status = "PREMIUM IS ON - ✅" if new_on else "PREMIUM IS OFF - ❌"
        text = (
            "<b>HERE YOU CAN MANAGE YOUR PREMIUM SETTINGS HERE</b>\n\n"
            "<b>THIS FEATURE WORK ONLY WHEN TOKEN VERIFICATION IS ENABLED</b>"
        )
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("📝 PREMIUM PLAN TEXT 📝", callback_data="master_prem_text")],
            [InlineKeyboardButton("➕ ADD PREMIUM USER ➕", callback_data="master_prem_add")],
            [InlineKeyboardButton("➖ REMOVE PREMIUM USER ➖", callback_data="master_prem_rem")],
            [InlineKeyboardButton("👥 PREMIUM USERS LIST 👥", callback_data="master_prem_list")],
            [InlineKeyboardButton(f"🔒 {prem_status}", callback_data="master_prem_toggle")],
            [InlineKeyboardButton("‹ BACK", callback_data="master_settings")]
        ])
        await edit_or_reply(query, text, reply_markup=markup)
        await query.answer()
        raise StopPropagation

    if data == "master_prem_text":
        user = await get_user(query.from_user.id)
        p_text = user.get("premium_plan_text") or "Not Set"
        p_photo = user.get("premium_plan_photo")
        text = (
            "<b>HERE YOU CAN MANAGE YOUR PREMIUM PLAN TEXT</b>\n\n"
            f"<b>text -</b>\n{p_text}"
        )
        if p_photo:
            text += "\n\n🖼️ <i>QR Code / UPI Photo is also set!</i>"
        markup = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("SET PREMIUM PLAN TEXT", callback_data="master_prem_set_text"),
                InlineKeyboardButton("DELETE PREMIUM PLAN TEXT", callback_data="master_prem_del_text")
            ],
            [InlineKeyboardButton("‹ BACK", callback_data="master_premium_plan")]
        ])
        await edit_or_reply(query, text, reply_markup=markup)
        await query.answer()
        raise StopPropagation

    if data == "master_prem_set_text":
        await query.answer()
        prompt_text = (
            "<b>NOW SEND ME YOUR PLAN TEXT</b>\n\n"
            "<b>NOTE -</b>\n"
            "PLAN TEXT MUST HAVE PRICE DETAILS OF 3 DAYS, 1 WEEK AND 1 MONTH PLAN AND CONTACT DETAILS IS MUST\n\n"
            "<i>And Send Plan Text In Minimum Words Because Of Telegram Limit</i>\n"
            "💡 <b>You can also send a Photo (QR Code / UPI) with caption!</b>\n\n"
            "<code>/cancel</code> - <b>Cancel THIS PROCESS.</b>"
        )
        await edit_or_reply(query, 
            prompt_text,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="master_prem_text")]])
        )
        try:
            pt_msg = await client.listen(chat_id=query.from_user.id, timeout=120)
        except Exception:
            raise StopPropagation

        if pt_msg.text and pt_msg.text.strip().lower() == "/cancel":
            try: await pt_msg.delete()
            except Exception: pass
            await edit_or_reply(query, "❌ <b>Process Cancelled.</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="master_prem_text")]]))
            raise StopPropagation

        photo_id = None
        plan_str = ""
        if pt_msg.photo:
            photo_id = pt_msg.photo.file_id
            plan_str = pt_msg.caption or ""
        elif pt_msg.text:
            plan_str = pt_msg.text.strip()
        
        try: await pt_msg.delete()
        except Exception: pass

        await update_user_info(query.from_user.id, {"premium_plan_text": plan_str, "premium_plan_photo": photo_id})
        await edit_or_reply(query, 
            "<b>SUCCESSFULLY SET PREMIUM PLAN TEXT ✅</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="master_prem_text")]])
        )
        raise StopPropagation

    if data == "master_prem_del_text":
        await update_user_info(query.from_user.id, {"premium_plan_text": None, "premium_plan_photo": None})
        await query.answer("Premium plan text deleted.", show_alert=True)
        await edit_or_reply(query, 
            "🗑️ <b>SUCCESSFULLY DELETED PREMIUM PLAN TEXT</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="master_prem_text")]])
        )
        raise StopPropagation

    if data == "master_prem_add":
        await query.answer()
        await edit_or_reply(query, 
            "<b>NOW SEND ME USER ID</b>\n\n"
            "<code>/cancel</code> - <b>Cancel THIS PROCESS.</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="master_premium_plan")]])
        )
        try:
            uid_msg = await client.listen(chat_id=query.from_user.id, timeout=120)
        except Exception:
            raise StopPropagation

        uid_raw = (uid_msg.text or "").strip()
        try: await uid_msg.delete()
        except Exception: pass

        if uid_raw.lower() == "/cancel":
            await edit_or_reply(query, "❌ <b>Process Cancelled.</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="master_premium_plan")]]))
            raise StopPropagation

        if not uid_raw.isdigit():
            await edit_or_reply(query, 
                "<b>Not A Valid Integer, Start your process again.</b>",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="master_prem_add")]])
            )
            raise StopPropagation

        target_uid = int(uid_raw)
        text = (
            "<b>CHOOSE YOUR PLAN VALIDITY FOR THIS USER</b>\n\n"
            "<code>/cancel</code> - <b>Cancel THIS PROCESS.</b>"
        )
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("3 Days", callback_data=f"master_prem_val:{target_uid}:3d")],
            [InlineKeyboardButton("1 Week", callback_data=f"master_prem_val:{target_uid}:1w")],
            [InlineKeyboardButton("1 Month", callback_data=f"master_prem_val:{target_uid}:1mo")],
            [InlineKeyboardButton("Custom Time", callback_data=f"master_prem_val:{target_uid}:custom")],
            [InlineKeyboardButton("‹ BACK", callback_data="master_premium_plan")]
        ])
        await edit_or_reply(query, text, reply_markup=markup)
        raise StopPropagation

    if data.startswith("master_prem_val:"):
        _, target_uid_s, val_code = data.split(":")
        target_uid = int(target_uid_s)
        now = int(time.time())

        if val_code == "custom":
            await query.answer()
            await edit_or_reply(query, 
                "<b>SEND ME CUSTOM VALIDITY LIKE - 1h, 10d, 2mo, 1y</b>\n\n"
                "<code>/cancel</code> - <b>Cancel THIS PROCESS.</b>",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="master_prem_add")]])
            )
            try:
                c_msg = await client.listen(chat_id=query.from_user.id, timeout=120)
            except Exception:
                raise StopPropagation

            c_raw = (c_msg.text or "").strip()
            try: await c_msg.delete()
            except Exception: pass

            if c_raw.lower() == "/cancel":
                await edit_or_reply(query, "❌ <b>Process Cancelled.</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="master_premium_plan")]]))
                raise StopPropagation

            mins = parse_time_string(c_raw)
            exp = now + mins * 60
            dur_str = format_time_minutes(mins)
        else:
            if val_code == "3d":
                exp = now + 3 * 86400
                dur_str = "3 Days"
            elif val_code == "1w":
                exp = now + 7 * 86400
                dur_str = "1 Week"
            else:
                exp = now + 30 * 86400
                dur_str = "1 Month"

        user = await get_user(query.from_user.id)
        p_users = list(user.get("premium_users", []))
        p_users = [u for u in p_users if int(u.get("user_id", 0)) != target_uid]
        p_users.append({"user_id": target_uid, "expires_at": exp, "added_at": now})
        await update_user_info(query.from_user.id, {"premium_users": p_users})

        await edit_or_reply(query, 
            f"✨ <b>SUCCESSFULLY ADDED USER <code>{target_uid}</code> AS PREMIUM USER FOR {dur_str} ✅</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="master_premium_plan")]])
        )
        raise StopPropagation

    if data == "master_prem_rem":
        await query.answer()
        await edit_or_reply(query, 
            "<b>SEND USER ID TO REMOVE FROM PREMIUM:</b>\n\n"
            "<code>/cancel</code> - <b>Cancel THIS PROCESS.</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="master_premium_plan")]])
        )
        try:
            r_msg = await client.listen(chat_id=query.from_user.id, timeout=120)
        except Exception:
            raise StopPropagation

        r_raw = (r_msg.text or "").strip()
        try: await r_msg.delete()
        except Exception: pass

        if r_raw.lower() == "/cancel":
            await edit_or_reply(query, "❌ <b>Process Cancelled.</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="master_premium_plan")]]))
            raise StopPropagation

        if not r_raw.isdigit():
            await edit_or_reply(query, "<b>Not A Valid Integer.</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="master_premium_plan")]]))
            raise StopPropagation

        rem_uid = int(r_raw)
        user = await get_user(query.from_user.id)
        p_users = [u for u in user.get("premium_users", []) if int(u.get("user_id", 0)) != rem_uid]
        await update_user_info(query.from_user.id, {"premium_users": p_users})

        await edit_or_reply(query, 
            f"🗑️ <b>SUCCESSFULLY REMOVED USER <code>{rem_uid}</code> FROM PREMIUM!</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="master_premium_plan")]])
        )
        raise StopPropagation

    if data == "master_prem_list":
        user = await get_user(query.from_user.id)
        p_users = user.get("premium_users", [])
        now = int(time.time())
        lines = []
        for pu in p_users:
            uid = pu.get("user_id")
            exp = int(pu.get("expires_at", 0))
            if exp > now:
                rem_mins = (exp - now) // 60
                lines.append(f"• <code>{uid}</code> - Expires in: {format_time_minutes(rem_mins)}")
        
        if lines:
            text = f"👥 <b>ACTIVE PREMIUM USERS:</b>\n\n" + "\n".join(lines) + f"\n\n<b>Total:</b> {len(lines)} users"
        else:
            text = "👥 <b>NO ACTIVE PREMIUM USERS FOUND!</b>"

        markup = InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="master_premium_plan")]])
        await edit_or_reply(query, text, reply_markup=markup)
        await query.answer()
        raise StopPropagation

    # ---------------- FORCE SUBSCRIBE ----------------
    if data == "master_fsub_menu":
        user = await get_user(query.from_user.id)
        channels = user.get("force_channels", [])
        ch_text = "\n".join([f"• <code>{c}</code>" for c in channels]) if channels else "None"
        text = (
            "📢 <b>CUSTOM FORCE SUBSCRIBE:</b>\n\n"
            "Users must join these channels to use your bot.\n\n"
            f"<b>Connected Channels:</b>\n{ch_text}"
        )
        markup = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("➕ ADD CHANNEL", callback_data="master_fsub_add"),
                InlineKeyboardButton("🗑️ CLEAR ALL", callback_data="master_fsub_del")
            ],
            [InlineKeyboardButton("‹ BACK", callback_data="master_settings")]
        ])
        await edit_or_reply(query, text, reply_markup=markup)
        await query.answer()
        raise StopPropagation

    if data == "master_fsub_add":
        await query.answer()
        me = client.me or (await client.get_me())
        prompt_text = (
            "<b>FORWARD A MESSAGE FROM CHANNEL TO ME,\n"
            f"AND MAKE SURE @{me.username} IS ADMIN IN THAT CHANNEL.</b>\n\n"
            "<code>/cancel</code> - <b>Cancel THIS PROCESS.</b>"
        )
        await edit_or_reply(query, prompt_text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="master_fsub_menu")]]))
        try:
            f_msg = await client.listen(chat_id=query.from_user.id, timeout=120)
        except Exception:
            raise StopPropagation

        f_raw = (f_msg.text or "").strip()
        try: await f_msg.delete()
        except Exception: pass

        if f_raw.lower() == "/cancel":
            await edit_or_reply(query, "❌ <b>Process Cancelled.</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="master_fsub_menu")]]))
            raise StopPropagation

        cid = None
        if f_msg.forward_from_chat:
            cid = f_msg.forward_from_chat.id
        elif f_raw.startswith("-100") or (f_raw.startswith("-") and f_raw[1:].isdigit()):
            cid = int(f_raw)
        elif f_raw.isdigit():
            cid = int(f"-100{f_raw}")

        if not cid:
            await edit_or_reply(query, "❌ <b>Invalid Channel.</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="master_fsub_menu")]]))
            raise StopPropagation

        user = await get_user(query.from_user.id)
        chs = list(user.get("force_channels", []))
        if cid not in chs:
            chs.append(cid)
            await update_user_info(query.from_user.id, {"force_channels": chs})

        await edit_or_reply(query, "✅ <b>SUCCESSFULLY ADDED FORCE SUBSCRIBE CHANNEL!</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="master_fsub_menu")]]))
        raise StopPropagation

    if data == "master_fsub_del":
        await update_user_info(query.from_user.id, {"force_channels": []})
        await query.answer("Cleared force sub channels.", show_alert=True)
        await edit_or_reply(query, "🗑️ <b>CLEARED ALL FORCE SUBSCRIBE CHANNELS</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="master_fsub_menu")]]))
        raise StopPropagation

    # ---------------- AUTO DELETE ----------------
    if data == "master_auto_delete_menu":
        user = await get_user(query.from_user.id)
        ad_on = bool(user.get("auto_delete_enabled", False))
        ad_mins = int(user.get("auto_delete_minutes", 15))
        status_str = f"ENABLED ({ad_mins} mins) ✅" if ad_on else "DISABLED ❌"

        text = (
            "♻️ <b>AUTO DELETE SETTINGS:</b>\n\n"
            "Automatically deletes files delivered by your bot after a set duration to prevent copyright issues.\n\n"
            f"• <b>Status:</b> <code>{status_str}</code>"
        )
        markup = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("5 min", callback_data="master_ad_set:5"),
                InlineKeyboardButton("10 min", callback_data="master_ad_set:10"),
                InlineKeyboardButton("15 min", callback_data="master_ad_set:15"),
                InlineKeyboardButton("30 min", callback_data="master_ad_set:30")
            ],
            [InlineKeyboardButton("DISABLE ❌" if ad_on else "ENABLE ✅", callback_data="master_ad_toggle")],
            [InlineKeyboardButton("‹ BACK", callback_data="master_settings")]
        ])
        await edit_or_reply(query, text, reply_markup=markup)
        await query.answer()
        raise StopPropagation

    if data.startswith("master_ad_set:"):
        mins = int(data.split(":")[1])
        await update_user_info(query.from_user.id, {"auto_delete_enabled": True, "auto_delete_minutes": mins})
        await query.answer(f"Auto delete set to {mins} minutes!", show_alert=True)
        return await callbacks(client, type('Q', (), {'data': 'master_auto_delete_menu', 'from_user': query.from_user, 'message': query.message, 'answer': query.answer})())

    if data == "master_ad_toggle":
        user = await get_user(query.from_user.id)
        new_on = not bool(user.get("auto_delete_enabled", False))
        await update_user_info(query.from_user.id, {"auto_delete_enabled": new_on})
        await query.answer(f"Auto delete {'enabled' if new_on else 'disabled'}!", show_alert=True)
        return await callbacks(client, type('Q', (), {'data': 'master_auto_delete_menu', 'from_user': query.from_user, 'message': query.message, 'answer': query.answer})())

    if data == "settings_back":
        buttons = [[
            InlineKeyboardButton('💝 sᴜʙsᴄʀɪʙᴇ ᴍʏ ʏᴏᴜᴛᴜʙᴇ ᴄʜᴀɴɴᴇʟ', url='https://www.youtube.com/@tech_as_0')
        ],[
            InlineKeyboardButton('🔍 sᴜᴘᴘᴏʀᴛ ɢʀᴏᴜᴘ', url=tg_link(SUPPORT_GROUP, 'ash_movie_j')),
            InlineKeyboardButton('🤖 ᴜᴘᴅᴀᴛᴇ ᴄʜᴀɴɴᴇʟ', url=tg_link(UPDATE_CHANNEL, 'MoviesGroupG3'))
        ],[
            InlineKeyboardButton('💁‍♀️ ʜᴇʟᴘ', callback_data='help'),
            InlineKeyboardButton('😊 ᴀʙᴏᴜᴛ', callback_data='about')
        ],[
            InlineKeyboardButton('🤖 ᴄʀᴇᴀᴛᴇ ʏᴏᴜʀ ᴏᴡɴ ᴄʟᴏɴᴇ ʙᴏᴛ', callback_data='settings')
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        me = client.me or (await client.get_me())
        caption = script.START_TXT.format(query.from_user.mention, me.mention)
        if query.message.photo:
            await query.message.edit_caption(caption=caption, reply_markup=reply_markup)
        else:
            await edit_or_reply(query, text=caption, reply_markup=reply_markup)
        await query.answer()
        raise StopPropagation

    if data.startswith("manage_clone:"):
        await manage_clone(client, query)
        raise StopPropagation
    if data.startswith("cm:"):
        await clone_manage_action(client, query)
        raise StopPropagation
    if data.startswith("cmdelete:"):
        await clone_delete(client, query)
        raise StopPropagation


async def set_pic_cmd(client, message):
    user_id = message.from_user.id
    pic_url = None
    if message.reply_to_message and message.reply_to_message.photo:
        pic_url = message.reply_to_message.photo.file_id
    elif len(message.command) > 1:
        pic_url = message.command[1].strip()
    if not pic_url:
        return await message.reply_text("❌ <b>Usage:</b>\nSend <code>/set_pic https://example.com/image.jpg</code> or reply to a photo with <code>/set_pic</code>")
    await update_user_info(user_id, {"start_pic": pic_url})
    await message.reply_text("✅ <b>Custom start photo saved successfully!</b>")


async def del_pic_cmd(client, message):
    user_id = message.from_user.id
    await update_user_info(user_id, {"start_pic": None})
    await message.reply_text("✅ <b>Start photo reset to default.</b>")


async def get_pic_cmd(client, message):
    user_id = message.from_user.id
    user = await get_user(user_id)
    pic = user.get("start_pic")
    if pic:
        try:
            return await message.reply_photo(photo=pic, caption="🖼️ <b>Your Custom Start Photo</b>")
        except Exception:
            return await message.reply_text(f"🖼️ <b>Your Custom Start Photo URL:</b>\n{pic}")
    await message.reply_text("ℹ️ <b>You are using default start photo.</b>")


async def caption_cmd(client, message):
    user_id = message.from_user.id
    if len(message.command) == 1:
        user = await get_user(user_id)
        cap = user.get("custom_caption")
        if cap:
            return await message.reply_text(f"📝 <b>Your Custom Caption:</b>\n\n<code>{cap}</code>\n\nUse <code>/del_caption</code> to remove or <code>/caption [new text]</code> to change.")
        return await message.reply_text("📝 <b>Custom Caption</b>\n\n<b>Usage:</b> <code>/caption Your custom caption {file_name} {file_size}</code>\n\n<b>Fillings:</b>\n• {file_name} : File Name\n• {file_size} : File Size\n• {caption} : Original Caption")
    raw = message.text.split(None, 1)[1].strip()
    if raw.lower() in ("off", "none", "delete", "clear"):
        await update_user_info(user_id, {"custom_caption": None})
        return await message.reply_text("✅ <b>Custom caption deleted successfully!</b>")
    await update_user_info(user_id, {"custom_caption": raw})
    await message.reply_text(f"✅ <b>Custom caption saved successfully!</b>\n\n<b>Preview:</b>\n{raw}")


async def del_caption_cmd(client, message):
    user_id = message.from_user.id
    await update_user_info(user_id, {"custom_caption": None})
    await message.reply_text("✅ <b>Custom caption deleted successfully!</b>")


async def button_cmd(client, message):
    user_id = message.from_user.id
    if len(message.command) == 1:
        user = await get_user(user_id)
        btns = user.get("custom_buttons") or []
        if btns:
            btn_lines = "\n".join([f"• [{b.get('text')}]({b.get('url')})" for b in btns])
            return await message.reply_text(f"➕ <b>Your Custom Buttons:</b>\n\n{btn_lines}\n\nUse <code>/button [Text] - [URL]</code> to add or <code>/del_button</code> to clear.", disable_web_page_preview=True)
        return await message.reply_text("➕ <b>Custom Button</b>\n\n<b>Usage:</b> <code>/button Join Channel - https://t.me/channel</code>\nUse <code>/del_button</code> to remove.")
    raw = message.text.split(None, 1)[1].strip()
    if raw.lower() in ("off", "none", "delete", "clear"):
        await update_user_info(user_id, {"custom_buttons": []})
        return await message.reply_text("✅ <b>Custom buttons cleared!</b>")
    if "-" not in raw:
        return await message.reply_text("❌ <b>Invalid Format:</b>\nUse <code>/button Button Text - https://link.com</code>")
    btn_text, btn_url = [x.strip() for x in raw.split("-", 1)]
    if not (btn_url.startswith("http://") or btn_url.startswith("https://") or btn_url.startswith("tg://")):
        return await message.reply_text("❌ URL must start with http://, https:// or tg://")
    user = await get_user(user_id)
    btns = list(user.get("custom_buttons") or [])
    btns.append({"text": btn_text, "url": btn_url})
    await update_user_info(user_id, {"custom_buttons": btns})
    await message.reply_text(f"✅ <b>Custom button added:</b> [{btn_text}]({btn_url})", disable_web_page_preview=True)


async def del_button_cmd(client, message):
    user_id = message.from_user.id
    await update_user_info(user_id, {"custom_buttons": []})
    await message.reply_text("✅ <b>Custom buttons cleared!</b>")


async def protect_cmd(client, message):
    user_id = message.from_user.id
    if len(message.command) == 1:
        user = await get_user(user_id)
        state = bool(user.get("protect_content", False))
        return await message.reply_text(f"🛡️ <b>Protect Content:</b> <code>{'ENABLED ✅' if state else 'DISABLED ❌'}</code>\n\nUse <code>/protect on</code> or <code>/protect off</code> to toggle.")
    arg = message.command[1].strip().lower()
    val = arg in ("on", "enable", "1", "yes", "true")
    await update_user_info(user_id, {"protect_content": val})
    await message.reply_text(f"🛡️ <b>Protect Content has been {'ENABLED ✅' if val else 'DISABLED ❌'}</b>")


async def shortener_cmd(client, message):
    user_id = message.from_user.id
    user = await get_user(user_id)
    site = user.get("base_site") or "Not set"
    api = user.get("shortener_api") or "Not set"
    await message.reply_text(
        f"🔗 <b>Link Shortener Settings</b>\n\n"
        f"• <b>Base Site:</b> <code>{site}</code>\n"
        f"• <b>API Key:</b> <code>{api}</code>\n\n"
        f"<b>Commands to configure:</b>\n"
        f"• <code>/base_site yoursite.com</code> (or <code>/base_site None</code> to remove)\n"
        f"• <code>/api your_api_key</code>"
    )


def register(client):
    client.add_handler(MessageHandler(settings, filters.command("settings") & filters.private), group=-1)
    client.add_handler(MessageHandler(set_pic_cmd, filters.command(["set_pic", "setpic"]) & filters.private), group=-1)
    client.add_handler(MessageHandler(del_pic_cmd, filters.command(["del_pic", "delpic"]) & filters.private), group=-1)
    client.add_handler(MessageHandler(get_pic_cmd, filters.command(["get_pic", "getpic"]) & filters.private), group=-1)
    client.add_handler(MessageHandler(caption_cmd, filters.command(["caption", "set_caption"]) & filters.private), group=-1)
    client.add_handler(MessageHandler(del_caption_cmd, filters.command(["del_caption", "delcaption"]) & filters.private), group=-1)
    client.add_handler(MessageHandler(button_cmd, filters.command(["button", "set_button"]) & filters.private), group=-1)
    client.add_handler(MessageHandler(del_button_cmd, filters.command(["del_button", "delbutton"]) & filters.private), group=-1)
    client.add_handler(MessageHandler(protect_cmd, filters.command(["protect", "protect_content"]) & filters.private), group=-1)
    client.add_handler(MessageHandler(shortener_cmd, filters.command("shortener") & filters.private), group=-1)
    client.add_handler(
        CallbackQueryHandler(
            callbacks,
            filters.regex(r"^(settings|master_settings|settings_back|log_channel|master_log_channel|master_set_log_channel|master_delete_log_channel|database_channel|master_database_channel|master_set_database_channel|master_delete_database_channel|my_clone|my_clones|add_clone_prompt|clone|google_backup|master_google_backup|google_connect|link_shortener|delete_shortener|custom_caption|caption_see|caption_delete|caption_edit|custom_button|button_add|button_delete|protect_menu|protect_toggle_on|protect_toggle_off|start_photo_menu|start_pic_edit|start_pic_see|start_pic_delete|manage_clone:\d+|cm:\d+:[a-z_]+|cmdelete:\d+|master_token_verification:\d+|master_v_[a-z_]+:\d+|master_premium_plan|master_prem_[a-z_]+|master_prem_val:\d+:[a-z0-9]+|master_fsub_[a-z_]+|master_auto_delete_[a-z_]+|master_ad_[a-z_]+|master_ad_set:\d+)$"),
        ),
        group=-1,
    )
