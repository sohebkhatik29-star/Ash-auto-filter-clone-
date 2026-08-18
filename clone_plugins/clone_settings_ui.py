# ASH FILE STORE & CLONE MANAGER - SETTINGS UI
import asyncio
import time
import re
from pyrogram import filters
from pyrogram.handlers import MessageHandler, CallbackQueryHandler
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from clone_plugins.users_api import (
    get_user, update_user_info, get_short_link, validate_shortener_token,
    parse_time_string, format_time_minutes, is_user_premium
)
from config import ADMINS, BOT_USERNAME


def db():
    from plugins.clone import mongo_db
    return mongo_db


def record(client):
    m = db()
    if m is None:
        return {}
    return m.bots.find_one({"bot_id": client.me.id}) or {}


def is_bot_owner(client, uid):
    try:
        if int(uid) in [int(x) for x in ADMINS if str(x).strip().lstrip("-").isdigit()]:
            return True
    except Exception:
        pass
    r = record(client)
    try:
        if int(r.get("user_id", 0)) == int(uid):
            return True
    except Exception:
        pass
    return False


def get_bot_admins(client):
    r = record(client)
    adms = r.get("admins", [])
    if isinstance(adms, dict):
        return list(adms.values())
    elif isinstance(adms, list):
        return adms
    return []


def get_admin_data(client, uid):
    for a in get_bot_admins(client):
        if int(a.get("user_id", 0)) == int(uid):
            return a
    return None


def has_permission(client, uid, perm):
    if is_bot_owner(client, uid):
        return True
    a = get_admin_data(client, uid)
    if a and bool(a.get(perm, False)):
        return True
    return False


def owner(client, uid):
    if is_bot_owner(client, uid):
        return True
    r = record(client)
    try:
        if int(uid) in [int(x) for x in r.get("moderators", [])]:
            return True
    except Exception:
        pass
    if get_admin_data(client, uid):
        return True
    return False


def save(client, **data):
    m = db()
    if m is not None:
        m.bots.update_one({"bot_id": client.me.id}, {"$set": data}, upsert=True)


def admins_menu_text():
    return (
        "👥 <b>ADMINS:</b>\n\n"
        "<b>YOU CAN CHANGE WHAT ADMINS CAN USE OR NOT BY CLICKING ON ADMIN NAME BUTTON.</b>\n\n"
        "<b>YOU CAN CUSTOMISE FOLLOWING ADMINS SETTINGS:</b>\n\n"
        "- <b>CAN DO BROADCAST</b>\n"
        "- <b>CAN USE CLONE BOT CUSTOMISATION</b>\n"
        "- <b>CAN ADD ADMINS OR CHANGE ADMIN SETTINGS</b>\n"
        "- <b>CAN DELETE BOT</b>\n\n"
        "<b>YOU CAN CUSTOMISE THE EACH ADMIN SETTINGS THAT WHAT THEY CAN USE OR WHAT THEY CAN NOT USE.</b>"
    )


def admins_menu_markup(client):
    rows = []
    admins = get_bot_admins(client)
    for adm in admins:
        name = adm.get("name") or f"Admin {adm.get('user_id')}"
        rows.append([InlineKeyboardButton(f"{name}", callback_data=f"admin_info:{adm.get('user_id')}")])
    rows.append([InlineKeyboardButton("➕ ADD ADMIN ➕", callback_data="add_admin_prompt")])
    rows.append([InlineKeyboardButton("❮ BACK", callback_data="settings_back")])
    return InlineKeyboardMarkup(rows)


def admin_info_text(adm):
    name = adm.get("name") or f"Admin {adm.get('user_id')}"
    uid = adm.get("user_id")
    uname = adm.get("username")
    uname_str = f"@{uname}" if uname else "None"
    return (
        "🪪 <b>ADMIN INFO:</b>\n\n"
        f"- <b>NAME:</b> {name}\n"
        f"- <b>USER ID:</b> <code>{uid}</code>\n"
        f"- <b>USERNAME:</b> {uname_str}\n\n"
        "<b>IF YOU ENABLE ALL SETTINGS WHICH IS GIVEN BELOW OF THIS ADMINS IT MEANS THIS ADMINS CAN DO EVERYTHING WHICH CAN DONE BY OWNER AND THIS ALSO HELP IF BY MISTAKE YOUR MAIN TELEGRAM ACCOUNT DELETED BUT ADMIN CAN NOT TRANSFER OWNERSHIP TO OTHER ADMIN ONLY OWNER CAN.</b>\n\n"
        "<b>YOU CAN CUSTOMISE THE EACH ADMIN SETTINGS THAT WHAT THEY CAN USE OR WHAT THEY CAN NOT USE.</b>"
    )


def admin_info_markup(adm):
    uid = adm.get("user_id")
    b_icon = "✅" if adm.get("broadcast") else "❌"
    s_icon = "✅" if adm.get("settings") else "❌"
    a_icon = "✅" if adm.get("add_admins") else "❌"
    d_icon = "✅" if adm.get("delete_bot") else "❌"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"📢 BROADCAST - {b_icon}", callback_data=f"adm_tgl:{uid}:broadcast")],
        [InlineKeyboardButton(f"⚙️ CLONE BOT SETTINGS - {s_icon}", callback_data=f"adm_tgl:{uid}:settings")],
        [InlineKeyboardButton(f"👥 ADD ADMINS - {a_icon}", callback_data=f"adm_tgl:{uid}:add_admins")],
        [InlineKeyboardButton(f"🚫 DELETE BOT - {d_icon}", callback_data=f"adm_tgl:{uid}:delete_bot")],
        [InlineKeyboardButton("♻️ TRANSFER CLONE OWNERSHIP", callback_data=f"adm_trans:{uid}")],
        [InlineKeyboardButton("🗑️ REMOVE ADMIN", callback_data=f"adm_rem:{uid}")],
        [InlineKeyboardButton("❮ BACK", callback_data="admins_menu")]
    ])


def cancel_user_listeners(client, chat_id):
    try:
        if hasattr(client, "cancel_listener"):
            client.cancel_listener(chat_id=chat_id)
    except Exception:
        pass
    try:
        listeners = getattr(client, "_listeners", None) or getattr(client, "listeners", None)
        if isinstance(listeners, dict) and chat_id in listeners:
            del listeners[chat_id]
    except Exception:
        pass


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


def settings_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🤖 MY CLONE BOT ↗", callback_data="clone_my_clone_info")],
        [InlineKeyboardButton("💳 PREMIUM PLAN", callback_data="cset_premium_plan")],
        [InlineKeyboardButton("🔗 LINK SHORTNER", callback_data="link_shortener")],
        [InlineKeyboardButton("⏰ TOKEN VERIFICATION", callback_data="cset_token_verification:1")],
        [InlineKeyboardButton("🍿 CUSTOM CAPTION", callback_data="custom_caption")],
        [InlineKeyboardButton("📢 CUSTOM FORCE SUBSCRIBE", callback_data="cset_fsub_menu")],
        [InlineKeyboardButton("🔘 CUSTOM BUTTON", callback_data="custom_button")],
        [InlineKeyboardButton("♻️ AUTO DELETE", callback_data="cset_auto_delete_menu")],
        [InlineKeyboardButton("🔒 PROTECT CONTENT", callback_data="protect_menu")],
        [InlineKeyboardButton("👥 ADMINS", callback_data="admins_menu")],
        [InlineKeyboardButton("‹ BACK", callback_data="start_back")],
    ])


async def settings(client, message):
    text = "🛠️ <b>Settings</b>\n\nCustomize your settings as your need"
    await message.reply(text, reply_markup=settings_menu())


async def callbacks(client, query):
    data = query.data
    try:
        cancel_user_listeners(client, query.from_user.id)
    except Exception:
        pass
    r = record(client)
    user_id = query.from_user.id
    user = await get_user(user_id)

    if data in ("settings", "settings_back", "cset:home"):
        text = "🛠️ <b>Settings</b>\n\nCustomize your settings as your need"
        try:
            return await edit_or_reply(query, text, reply_markup=settings_menu())
        except Exception:
            return await query.message.reply(text, reply_markup=settings_menu())

    if data == "log_channel":
        r = record(client)
        log_ch = r.get("log_channel")
        log_title = r.get("log_channel_title")
        if log_ch:
            status_text = f"<b>YOUR LOG CHANNEL - {log_title or log_ch}</b>"
        else:
            status_text = "<b>YOU DIDN'T ADDED ANY LOG CHANNEL ❗</b>"

        text = (
            "📢 <b>LOG CHANNEL:</b>\n\n"
            "<b>\"WHAT IS LOG CHANNEL ??\"</b>\n"
            "IF NEW USERS START YOUR CLONE BOT THEN BOT NOTIFIES YOU.\n\n"
            f"{status_text}"
        )
        markup = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("SET CHANNEL", callback_data="set_log_channel"),
                InlineKeyboardButton("DELETE CHANNEL", callback_data="delete_log_channel")
            ],
            [InlineKeyboardButton("❮ BACK", callback_data="settings_back")]
        ])
        return await edit_or_reply(query, text, reply_markup=markup)

    if data == "set_log_channel":
        await query.answer()
        me = client.me or (await client.get_me())
        prompt_text = (
            "<b>FORWARD LOG CHANNEL ANY MESSAGE TO ME,\n"
            f"AND MAKE SURE @{me.username} IS ADMIN IN YOUR CHANNEL.</b>\n\n"
            "<code>/cancel</code> - <b>CANCEL THIS PROCESS.</b>"
        )
        await edit_or_reply(query, 
            prompt_text,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❮ BACK", callback_data="log_channel")]])
        )
        try:
            ch_msg = await client.listen(chat_id=user_id, timeout=120)
        except Exception:
            return

        ch_raw = (ch_msg.text or "").strip()
        try:
            await ch_msg.delete()
        except Exception:
            pass

        if ch_raw.lower() == "/cancel":
            return await edit_or_reply(query, 
                "❌ <b>Process Cancelled.</b>",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❮ BACK", callback_data="log_channel")]])
            )

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
            return await edit_or_reply(query, 
                "❌ <b>Invalid Channel! Please forward a message directly from your channel.</b>",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❮ BACK", callback_data="log_channel")]])
            )

        try:
            chat = await client.get_chat(channel_id)
            channel_title = chat.title or channel_title or str(channel_id)
            await client.send_message(
                chat_id=channel_id,
                text=f"⚡ <b>Log channel successfully connected with @{me.username}!</b>"
            )
        except Exception as err:
            return await edit_or_reply(query, 
                f"❌ <b>Failed to connect channel!</b>\n\nMake sure <b>@{me.username}</b> is an <b>ADMIN</b> in the channel with post permissions.\n\n<code>Error: {err}</code>",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❮ BACK", callback_data="log_channel")]])
            )

        save(client, log_channel=channel_id, log_channel_title=channel_title)
        return await edit_or_reply(query, 
            f"⚡ <b>SUCCESSFULLY ADDED YOUR LOG CHANNEL - {channel_title}</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❮ BACK", callback_data="log_channel")]])
        )

    if data == "delete_log_channel":
        save(client, log_channel=None, log_channel_title=None)
        await query.answer("🗑️ Successfully deleted your log channel", show_alert=False)
        return await edit_or_reply(query, 
            "🗑️ <b>SUCCESSFULLY DELETED LOG CHANNEL</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❮ BACK", callback_data="log_channel")]])
        )

    if data == "database_channel":
        r = record(client)
        db_ch = r.get("database_channel")
        db_title = r.get("database_channel_title")
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
                InlineKeyboardButton("SET CHANNEL", callback_data="set_database_channel"),
                InlineKeyboardButton("DELETE CHANNEL", callback_data="delete_database_channel")
            ],
            [InlineKeyboardButton("❮ BACK", callback_data="settings_back")]
        ])
        return await edit_or_reply(query, text, reply_markup=markup)

    if data == "set_database_channel":
        await query.answer()
        me = client.me or (await client.get_me())
        prompt_text = (
            "<b>FORWARD DATABASE CHANNEL ANY MESSAGE TO ME,\n"
            f"AND MAKE SURE @{me.username} IS ADMIN IN YOUR CHANNEL.</b>\n\n"
            "<code>/cancel</code> - <b>CANCEL THIS PROCESS.</b>"
        )
        await edit_or_reply(query, 
            prompt_text,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❮ BACK", callback_data="database_channel")]])
        )
        try:
            ch_msg = await client.listen(chat_id=user_id, timeout=120)
        except Exception:
            return

        ch_raw = (ch_msg.text or "").strip()
        try:
            await ch_msg.delete()
        except Exception:
            pass

        if ch_raw.lower() == "/cancel":
            return await edit_or_reply(query, 
                "❌ <b>Process Cancelled.</b>",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❮ BACK", callback_data="database_channel")]])
            )

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
            return await edit_or_reply(query, 
                "❌ <b>Invalid Channel! Please forward a message directly from your channel.</b>",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❮ BACK", callback_data="database_channel")]])
            )

        try:
            chat = await client.get_chat(channel_id)
            channel_title = chat.title or channel_title or str(channel_id)
            await client.send_message(
                chat_id=channel_id,
                text=f"⚡ <b>Database channel successfully connected with @{me.username}!</b>"
            )
        except Exception as err:
            return await edit_or_reply(query, 
                f"❌ <b>Failed to connect channel!</b>\n\nMake sure <b>@{me.username}</b> is an <b>ADMIN</b> in the channel with post permissions.\n\n<code>Error: {err}</code>",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❮ BACK", callback_data="database_channel")]])
            )

        save(client, database_channel=channel_id, database_channel_title=channel_title)
        return await edit_or_reply(query, 
            f"⚡ <b>SUCCESSFULLY ADDED YOUR DATABASE CHANNEL - {channel_title}</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❮ BACK", callback_data="database_channel")]])
        )

    if data == "delete_database_channel":
        save(client, database_channel=None, database_channel_title=None)
        await query.answer("🗑️ Successfully deleted your database channel", show_alert=False)
        return await edit_or_reply(query, 
            "🗑️ <b>SUCCESSFULLY DELETED DATABASE CHANNEL</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❮ BACK", callback_data="database_channel")]])
        )

    if data == "admins_menu":
        if not (is_bot_owner(client, user_id) or has_permission(client, user_id, "add_admins")):
            return await query.answer("❌ You don't have permission to manage admins.", show_alert=True)
        return await edit_or_reply(query, 
            admins_menu_text(),
            reply_markup=admins_menu_markup(client)
        )

    if data == "add_admin_prompt":
        if not (is_bot_owner(client, user_id) or has_permission(client, user_id, "add_admins")):
            return await query.answer("❌ You don't have permission to add admins.", show_alert=True)
        await query.answer()
        prompt_text = (
            "<b>NOW SEND ME USER ID</b>\n\n"
            "<b>FOR USER ID , TOLD THAT USER TO GIVE <code>/id</code> COMMAND IN THIS BOT TO GET THAT USER ID</b>\n\n"
            "<b>AND MAKE SURE YOUR ADMIN START THIS BOT ELSE YOU WILL GET ERROR THAT THIS IS NOT USER ID</b>\n\n"
            "<code>/cancel</code> - <b>CANCEL THIS PROCESS</b>"
        )
        await edit_or_reply(query, 
            prompt_text,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❮ BACK", callback_data="admins_menu")]])
        )
        try:
            uid_msg = await client.listen(chat_id=user_id, timeout=120)
        except Exception:
            return

        raw_uid = (uid_msg.text or "").strip()
        try:
            await uid_msg.delete()
        except Exception:
            pass

        if raw_uid.lower() == "/cancel":
            return await edit_or_reply(query, 
                "❌ <b>Process Cancelled.</b>",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❮ BACK", callback_data="admins_menu")]])
            )

        if not (raw_uid.isdigit() or (raw_uid.startswith("-") and raw_uid[1:].isdigit())):
            return await edit_or_reply(query, 
                "❌ <b>Invalid User ID!</b>\n\nPlease make sure the user starts the bot and gives their numeric User ID.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❮ BACK", callback_data="admins_menu")]])
            )

        target_uid = int(raw_uid)
        admin_name = f"User {target_uid}"
        admin_uname = None

        try:
            user_obj = await client.get_users(target_uid)
            if user_obj:
                admin_name = (user_obj.first_name or "") + (" " + user_obj.last_name if user_obj.last_name else "")
                admin_name = admin_name.strip() or f"User {target_uid}"
                admin_uname = user_obj.username
        except Exception:
            try:
                chat_obj = await client.get_chat(target_uid)
                if chat_obj:
                    admin_name = (chat_obj.first_name or "") + (" " + chat_obj.last_name if chat_obj.last_name else "")
                    admin_name = admin_name.strip() or f"User {target_uid}"
                    admin_uname = chat_obj.username
            except Exception:
                pass

        admins = get_bot_admins(client)
        found = False
        for a in admins:
            if int(a.get("user_id", 0)) == target_uid:
                a["name"] = admin_name
                a["username"] = admin_uname
                found = True
                break
        if not found:
            admins.append({
                "user_id": target_uid,
                "name": admin_name,
                "username": admin_uname,
                "broadcast": False,
                "settings": False,
                "add_admins": False,
                "delete_bot": False
            })
        save(client, admins=admins)
        return await edit_or_reply(query, 
            "<b>SUCCESSFULLY UPDATED</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❮ BACK", callback_data="admins_menu")]])
        )

    if data.startswith("admin_info:"):
        target_uid = int(data.split(":")[1])
        adm = get_admin_data(client, target_uid)
        if not adm:
            return await query.answer("❌ Admin not found!", show_alert=True)
        return await edit_or_reply(query, 
            admin_info_text(adm),
            reply_markup=admin_info_markup(adm)
        )

    if data.startswith("adm_tgl:"):
        if not (is_bot_owner(client, user_id) or has_permission(client, user_id, "add_admins")):
            return await query.answer("❌ You don't have permission to modify admin settings.", show_alert=True)
        _, target_uid_str, perm = data.split(":")
        target_uid = int(target_uid_str)
        admins = get_bot_admins(client)
        found_adm = None
        for a in admins:
            if int(a.get("user_id", 0)) == target_uid:
                a[perm] = not bool(a.get(perm, False))
                found_adm = a
                break
        if found_adm:
            save(client, admins=admins)
            await query.answer()
            return await edit_or_reply(query, 
                admin_info_text(found_adm),
                reply_markup=admin_info_markup(found_adm)
            )
        return await query.answer("❌ Admin not found!", show_alert=True)

    if data.startswith("adm_trans:"):
        target_uid = int(data.split(":")[1])
        if not is_bot_owner(client, user_id):
            return await query.answer("❌ Only the clone owner can transfer ownership!", show_alert=True)
        save(client, user_id=target_uid)
        await query.answer("⚡ Ownership successfully transferred to admin!", show_alert=True)
        return await edit_or_reply(query, 
            admins_menu_text(),
            reply_markup=admins_menu_markup(client)
        )

    if data.startswith("adm_rem:"):
        if not (is_bot_owner(client, user_id) or has_permission(client, user_id, "add_admins")):
            return await query.answer("❌ You don't have permission to remove admins.", show_alert=True)
        target_uid = int(data.split(":")[1])
        admins = [a for a in get_bot_admins(client) if int(a.get("user_id", 0)) != target_uid]
        save(client, admins=admins)
        await query.answer("🗑️ Admin successfully removed!", show_alert=False)
        return await edit_or_reply(query, 
            admins_menu_text(),
            reply_markup=admins_menu_markup(client)
        )

    if data == "link_shortener":
        user = await get_user(user_id)
        r = record(client)
        site = user.get("base_site") or r.get("base_site")
        api = user.get("shortener_api") or r.get("shortener_api")
        if not (site and api):
            text = (
                "<b>HERE YOU CAN MANAGE YOUR BOT URL SHORTNER DETAILS</b>\n\n"
                "<b>Website -</b> <code>Not set</code>\n"
                "<b>API Token -</b> <code>Not set</code>"
            )
            markup = InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ ADD SHORTNER", callback_data="add_shortener")],
                [InlineKeyboardButton("‹ BACK", callback_data="settings_back")]
            ])
            return await edit_or_reply(query, text, reply_markup=markup)

        text = (
            "<b>HERE YOU CAN MANAGE YOUR BOT URL SHORTNER DETAILS</b>\n\n"
            f"<b>Website -</b> <code>{site}</code>\n"
            f"<b>API Token -</b> <code>{api}</code>"
        )
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ ADD NEW SHORTNER", callback_data="add_shortener")],
            [InlineKeyboardButton("🗑️ DELETE SHORTNER", callback_data="delete_shortener")],
            [InlineKeyboardButton("‹ BACK", callback_data="settings_back")]
        ])
        return await edit_or_reply(query, text, reply_markup=markup)

    if data == "add_shortener":
        await query.answer()
        prompt_text = (
            "<b>SEND ME A SHORTLINK URL...</b>\n\n"
            "<b>FORMAT :</b>\n"
            "<code>https://ashlink.online</code> - ❌\n"
            "<code>ashlink.online</code> - ✅\n\n"
            "<code>/cancel</code> - <b>Cancel THIS PROCESS.</b>"
        )
        await edit_or_reply(query, 
            prompt_text,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="link_shortener")]]),
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

        if site_raw.lower() == "/cancel":
            return await edit_or_reply(query, "❌ <b>Process Cancelled.</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="link_shortener")]]))

        site_clean = site_raw.replace("https://", "").replace("http://", "").split("/")[0].strip()
        if not site_clean or "." not in site_clean:
            return await edit_or_reply(query, "❌ <b>Invalid site URL.</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="link_shortener")]]))

        await edit_or_reply(query, 
            "<b>SEND ME SHORTLINK API...</b>\n\n"
            "<code>/cancel</code> - <b>Cancel THIS PROCESS.</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="link_shortener")]])
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

        if api_raw.lower() == "/cancel":
            return await edit_or_reply(query, "❌ <b>Process Cancelled.</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="link_shortener")]]))

        is_valid = await validate_shortener_token(site_clean, api_raw)
        if not is_valid:
            return await edit_or_reply(query, 
                "❌ <b>The given Shortener Api Token is invalid</b>",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="link_shortener")]])
            )

        await update_user_info(user_id, {"base_site": site_clean, "shortener_api": api_raw})
        save(client, base_site=site_clean, shortener_api=api_raw)
        confirm_text = (
            "✅ <b>SHORTNER SET HO GAYI!</b>\n\n"
            f"🌐 <b>Website:</b> <code>{site_clean}</code>\n"
            f"🔑 <b>API Token:</b> <code>{api_raw}</code>"
        )
        confirm_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ ADD NEW SHORTNER", callback_data="add_shortener")],
            [InlineKeyboardButton("‹ BACK", callback_data="link_shortener")]
        ])
        return await edit_or_reply(query, confirm_text, reply_markup=confirm_markup)

    if data == "delete_shortener":
        await update_user_info(user_id, {"base_site": None, "shortener_api": None})
        save(client, base_site=None, shortener_api=None)
        await query.answer("✨ Successfully deleted your link shortener provider", show_alert=False)
        return await edit_or_reply(query, 
            "✨ <b>SUCCESSFULLY DELETED YOUR LINK SHORTENER PROVIDER</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="link_shortener")]])
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
        return await edit_or_reply(query, text, reply_markup=markup)

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
        return await edit_or_reply(query, text, reply_markup=markup)

    if data == "custom_caption":
        cap = r.get("custom_caption")
        cap_status = f"\n\n<b>Current:</b> <code>{cap}</code>" if cap else "\n\n<b>Current:</b> <i>Not set (Default)</i>"
        text = (
            "<b>Custom Caption:</b>\n\n"
            "You can add a custom caption to your media messages instead of its original caption."
            f"{cap_status}\n\n"
            "<b>Fillings:</b>\n"
            "• {file_name} : File Name\n"
            "• {file_size} : File Size\n"
            "• {caption} : Orginal Caption"
        )
        return await edit_or_reply(query, text, reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Edit", callback_data="caption_edit"), InlineKeyboardButton("See", callback_data="caption_see"), InlineKeyboardButton("Delete", callback_data="caption_delete")],
            [InlineKeyboardButton("back", callback_data="settings_back")]
        ]))

    if data == "caption_see":
        cap = r.get("custom_caption")
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
        return await edit_or_reply(query, 
            text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Edit", callback_data="caption_edit"), InlineKeyboardButton("Delete", callback_data="caption_delete")],
                [InlineKeyboardButton("❮ back", callback_data="custom_caption")]
            ])
        )

    if data == "caption_delete":
        save(client, custom_caption=None)
        await update_user_info(user_id, {"custom_caption": None})
        await query.answer("✨ Custom caption deleted.", show_alert=False)
        text = (
            "<b>Custom Caption:</b>\n\n"
            "You can add a custom caption to your media messages instead of its original caption.\n\n"
            "<b>Current:</b> <i>Not set (Default)</i>\n\n"
            "<b>Fillings:</b>\n"
            "• {file_name} : File Name\n"
            "• {file_size} : File Size\n"
            "• {caption} : Orginal Caption"
        )
        return await edit_or_reply(query, text, reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Edit", callback_data="caption_edit"), InlineKeyboardButton("See", callback_data="caption_see"), InlineKeyboardButton("Delete", callback_data="caption_delete")],
            [InlineKeyboardButton("back", callback_data="settings_back")]
        ]))

    if data == "caption_edit":
        await query.answer()
        await edit_or_reply(query, 
            "Send Your New Custom Caption\n\nSend /cancel to abort.",
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
            return await edit_or_reply(query, "❌ Cancelled.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❮ BACK", callback_data="custom_caption")]]))
        save(client, custom_caption=cap_text)
        await update_user_info(user_id, {"custom_caption": cap_text})
        return await edit_or_reply(query, 
            f"✨ <b>Successfully Saved Your Caption</b>\n\n<code>{cap_text}</code>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❮ BACK", callback_data="custom_caption")]])
        )

    if data == "custom_button":
        buttons = r.get("custom_buttons", [])
        rows = []
        for b in buttons:
            if isinstance(b, dict) and b.get("text") and b.get("url"):
                rows.append([InlineKeyboardButton(b["text"], url=b["url"])])
        rows.append([InlineKeyboardButton("➕ Add Button", callback_data="button_add"), InlineKeyboardButton("🗑️ Delete All", callback_data="button_delete")])
        rows.append([InlineKeyboardButton("back", callback_data="settings_back")])
        text = "<b>Custom Button:</b>\n\nYou can add custom buttons to your shared messages."
        if buttons:
            text += f"\n\n<b>Configured Buttons:</b> {len(buttons)}"
        else:
            text += "\n\n<i>No custom buttons set.</i>"
        return await edit_or_reply(query, text, reply_markup=InlineKeyboardMarkup(rows))

    if data == "button_add":
        await query.answer()
        await edit_or_reply(query, 
            "Send text for button\n\nSend /cancel to abort.",
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
            return await edit_or_reply(query, "❌ Cancelled.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❮ BACK", callback_data="custom_button")]]))
        
        await edit_or_reply(query, 
            f"<b>Button Text:</b> <code>{btn_txt}</code>\n\nSend url for button\n(e.g., https://t.me/yourchannel)\n\nSend /cancel to abort.",
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
        if not (btn_url.startswith("http://") or btn_url.startswith("https://") or btn_url.startswith("tg://") or btn_url.startswith("t.me/")):
            return await edit_or_reply(query, "❌ URL must start with http://, https:// or tg://", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❮ BACK", callback_data="custom_button")]]))
        if btn_url.startswith("t.me/"):
            btn_url = "https://" + btn_url
        btns = list(r.get("custom_buttons", []))
        btns.append({"text": btn_txt[:64], "url": btn_url})
        save(client, custom_buttons=btns)
        await update_user_info(user_id, {"custom_buttons": btns})
        return await edit_or_reply(query, 
            "✨ <b>Successfully Button Added</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❮ BACK", callback_data="custom_button")]])
        )

    if data == "button_delete":
        save(client, custom_buttons=[])
        await update_user_info(user_id, {"custom_buttons": []})
        await query.answer("Custom buttons deleted.", show_alert=True)
        return await edit_or_reply(query, 
            "<b>Custom Button:</b>\n\nYou can add a custom button to your message\n\n<i>All buttons deleted.</i>",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ Add Button", callback_data="button_add")],
                [InlineKeyboardButton("back", callback_data="settings_back")]
            ])
        )


    if data == "clone_my_clone_info":
        me = client.me or (await client.get_me())
        text = (
            "🤖 <b>MY CLONE BOT INFO:</b>\n\n"
            f"• <b>Name:</b> {me.first_name}\n"
            f"• <b>Username:</b> @{me.username}\n"
            f"• <b>Bot ID:</b> <code>{me.id}</code>\n\n"
            "You can manage all settings of your clone bot using the menu below."
        )
        markup = InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="settings_back")]])
        return await edit_or_reply(query, text, reply_markup=markup)

    # ---------------- TOKEN VERIFICATION ----------------
    if data.startswith("cset_token_verification:"):
        slot = int(data.split(":")[1])
        r = record(client)
        v_key = f"verify_{slot}" if slot > 1 else "verify_1"
        v_cfg = r.get(v_key, {})
        is_on = bool(v_cfg.get("is_on", False))
        
        site = v_cfg.get("site") or r.get("base_site") or "Not set"
        api = v_cfg.get("api") or r.get("shortener_api") or "Not set"
        tut = v_cfg.get("tutorial") or "Not set"
        mins = v_cfg.get("time_minutes", 480)
        time_str = format_time_minutes(mins)

        prefix = "VERIFY" if slot == 1 else ("SECOND" if slot == 2 else "THIRD")
        next_slot = (slot % 3) + 1
        next_name = "SECOND VERIFICATION" if slot == 1 else ("THIRD VERIFICATION" if slot == 2 else "FIRST VERIFICATION")
        status_text = "VERIFY IS ON - ✅" if is_on else "VERIFY IS OFF - ❌"

        text = (
            "<b>MANAGE YOUR TOKEN VERIFICATION SETTINGS FROM HERE GIVEN BELOW BUTTONS</b>\n\n"
            f"<b>Slot {slot} Shortener Website :</b> <code>{site}</code>\n"
            f"<b>Slot {slot} API Token :</b> <code>{api}</code>\n"
            f"<b>Slot {slot} Tutorial Link :</b> <code>{tut}</code>\n"
            f"<b>Slot {slot} Verification Time :</b> <code>{time_str}</code>"
        )
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"🔗 {prefix} SHORTNER", callback_data=f"cset_v_shortner:{slot}")],
            [InlineKeyboardButton(f"🎬 {prefix} TUTORIAL", callback_data=f"cset_v_tutorial:{slot}")],
            [InlineKeyboardButton(f"⏳ {prefix} TIME", callback_data=f"cset_v_time:{slot}")],
            [InlineKeyboardButton(f"⏰ {next_name}", callback_data=f"cset_token_verification:{next_slot}")],
            [InlineKeyboardButton(f"🔒 {status_text}", callback_data=f"cset_v_toggle:{slot}")],
            [InlineKeyboardButton("➕ ADD NEW SHORTNER", callback_data=f"cset_v_shortner:{slot}")],
            [InlineKeyboardButton("‹ BACK", callback_data="settings_back")]
        ])
        return await edit_or_reply(query, text, reply_markup=markup, disable_web_page_preview=True)

    if data.startswith("cset_v_toggle:"):
        slot = int(data.split(":")[1])
        r = record(client)
        v_key = f"verify_{slot}" if slot > 1 else "verify_1"
        v_cfg = r.get(v_key, {})
        curr_state = bool(v_cfg.get("is_on", False))
        
        site = v_cfg.get("site") or r.get("base_site")
        api = v_cfg.get("api") or r.get("shortener_api")
        tut = v_cfg.get("tutorial")
        
        if not curr_state and (not site or not api or not tut):
            return await query.answer("YOU DON NOT ADDED SHORTLINK AND TUTORIAL LINK FOR VERIFICATION, FIRST ADD IT THEN TURN ME ON", show_alert=True)
        
        new_state = not curr_state
        v_cfg["is_on"] = new_state
        save(client, **{v_key: v_cfg})
        
        prefix = "VERIFY" if slot == 1 else ("SECOND" if slot == 2 else "THIRD")
        next_slot = (slot % 3) + 1
        next_name = "SECOND VERIFICATION" if slot == 1 else ("THIRD VERIFICATION" if slot == 2 else "FIRST VERIFICATION")
        status_text = "VERIFY IS ON - ✅" if new_state else "VERIFY IS OFF - ❌"

        site_val = v_cfg.get("site") or r.get("base_site") or "Not set"
        api_val = v_cfg.get("api") or r.get("shortener_api") or "Not set"
        tut_val = v_cfg.get("tutorial") or "Not set"
        mins_val = v_cfg.get("time_minutes", 480)
        time_str_val = format_time_minutes(mins_val)

        text = (
            "<b>MANAGE YOUR TOKEN VERIFICATION SETTINGS FROM HERE GIVEN BELOW BUTTONS</b>\n\n"
            f"<b>Slot {slot} Shortener Website :</b> <code>{site_val}</code>\n"
            f"<b>Slot {slot} API Token :</b> <code>{api_val}</code>\n"
            f"<b>Slot {slot} Tutorial Link :</b> <code>{tut_val}</code>\n"
            f"<b>Slot {slot} Verification Time :</b> <code>{time_str_val}</code>"
        )
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"🔗 {prefix} SHORTNER", callback_data=f"cset_v_shortner:{slot}")],
            [InlineKeyboardButton(f"🎬 {prefix} TUTORIAL", callback_data=f"cset_v_tutorial:{slot}")],
            [InlineKeyboardButton(f"⏳ {prefix} TIME", callback_data=f"cset_v_time:{slot}")],
            [InlineKeyboardButton(f"⏰ {next_name}", callback_data=f"cset_token_verification:{next_slot}")],
            [InlineKeyboardButton(f"🔒 {status_text}", callback_data=f"cset_v_toggle:{slot}")],
            [InlineKeyboardButton("➕ ADD NEW SHORTNER", callback_data=f"cset_v_shortner:{slot}")],
            [InlineKeyboardButton("‹ BACK", callback_data="settings_back")]
        ])
        return await edit_or_reply(query, text, reply_markup=markup, disable_web_page_preview=True)

    if data.startswith("cset_v_shortner:"):
        slot = int(data.split(":")[1])
        await query.answer()
        prompt_text = (
            "<b>SEND ME A SHORTLINK URL...</b>\n\n"
            "<b>FORMAT :</b>\n"
            "<code>https://ashlink.online</code> - ❌\n"
            "<code>ashlink.online</code> - ✅\n\n"
            "<code>/cancel</code> - <b>Cancel THIS PROCESS.</b>"
        )
        await edit_or_reply(query, 
            prompt_text,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data=f"cset_token_verification:{slot}")]])
        )
        try:
            site_msg = await client.listen(chat_id=user_id, timeout=120)
        except Exception:
            return

        site_raw = (site_msg.text or "").strip()
        try: await site_msg.delete()
        except Exception: pass

        if site_raw.lower() == "/cancel":
            return await edit_or_reply(query, "❌ <b>Process Cancelled.</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data=f"cset_token_verification:{slot}")]]))

        site_clean = site_raw.replace("https://", "").replace("http://", "").split("/")[0].strip()
        if not site_clean or "." not in site_clean:
            return await edit_or_reply(query, "❌ <b>Invalid site URL.</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data=f"cset_token_verification:{slot}")]]))

        await edit_or_reply(query, 
            "<b>SEND ME SHORTLINK API...</b>\n\n"
            "<code>/cancel</code> - <b>Cancel THIS PROCESS.</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data=f"cset_token_verification:{slot}")]])
        )
        try:
            api_msg = await client.listen(chat_id=user_id, timeout=120)
        except Exception:
            return

        api_raw = (api_msg.text or "").strip()
        try: await api_msg.delete()
        except Exception: pass

        if api_raw.lower() == "/cancel":
            return await edit_or_reply(query, "❌ <b>Process Cancelled.</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data=f"cset_token_verification:{slot}")]]))

        is_valid = await validate_shortener_token(site_clean, api_raw)
        if not is_valid:
            return await edit_or_reply(query, 
                "❌ <b>The given Shortener Api Token is invalid</b>",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data=f"cset_token_verification:{slot}")]])
            )

        r = record(client)
        v_key = f"verify_{slot}" if slot > 1 else "verify_1"
        v_cfg = r.get(v_key, {})
        v_cfg["site"] = site_clean
        v_cfg["api"] = api_raw
        save(client, **{v_key: v_cfg, "base_site": site_clean, "shortener_api": api_raw})

        confirm_text = (
            "✅ <b>SHORTNER SET HO GAYI!</b>\n\n"
            f"🌐 <b>Website:</b> <code>{site_clean}</code>\n"
            f"🔑 <b>API Token:</b> <code>{api_raw}</code>"
        )
        confirm_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ ADD NEW SHORTNER", callback_data=f"cset_v_shortner:{slot}")],
            [InlineKeyboardButton("‹ BACK", callback_data=f"cset_token_verification:{slot}")]
        ])
        return await edit_or_reply(query, confirm_text, reply_markup=confirm_markup)

    if data.startswith("cset_v_tutorial:"):
        slot = int(data.split(":")[1])
        r = record(client)
        v_key = f"verify_{slot}" if slot > 1 else "verify_1"
        v_cfg = r.get(v_key, {})
        tut = v_cfg.get("tutorial") or "Not set"

        text = (
            "<b>HERE YOU CAN MANAGE YOUR BOT TOKEN VERIFICATION LINK SHORTNER TUTORIAL VIDEO LINK FOR HOW TO OPEN LINK.</b>\n\n"
            f"<b>LINK -</b> {tut}"
        )
        markup = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("SET TUTORIAL", callback_data=f"cset_v_set_tut:{slot}"),
                InlineKeyboardButton("DELETE TUTORIAL", callback_data=f"cset_v_del_tut:{slot}")
            ],
            [InlineKeyboardButton("‹ BACK", callback_data=f"cset_token_verification:{slot}")]
        ])
        await edit_or_reply(query, text, reply_markup=markup, disable_web_page_preview=True)
        return

    if data.startswith("cset_v_set_tut:"):
        slot = int(data.split(":")[1])
        await query.answer()
        await edit_or_reply(query, 
            "<b>SEND ME A TUTORIAL LINK...</b>\n\n"
            "<code>/cancel</code> - <b>Cancel THIS PROCESS.</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data=f"cset_v_tutorial:{slot}")]])
        )
        try:
            t_msg = await client.listen(chat_id=user_id, timeout=120)
        except Exception:
            return

        t_raw = (t_msg.text or "").strip()
        try: await t_msg.delete()
        except Exception: pass

        if t_raw.lower() == "/cancel":
            return await edit_or_reply(query, "❌ <b>Process Cancelled.</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data=f"cset_v_tutorial:{slot}")]]))

        r = record(client)
        v_key = f"verify_{slot}" if slot > 1 else "verify_1"
        v_cfg = r.get(v_key, {})
        v_cfg["tutorial"] = t_raw
        save(client, **{v_key: v_cfg})

        return await edit_or_reply(query, 
            "<b>SUCCESSFULLY SET TUTORIAL LINK ✅</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data=f"cset_v_tutorial:{slot}")]])
        )

    if data.startswith("cset_v_del_tut:"):
        slot = int(data.split(":")[1])
        r = record(client)
        v_key = f"verify_{slot}" if slot > 1 else "verify_1"
        v_cfg = r.get(v_key, {})
        v_cfg["tutorial"] = None
        save(client, **{v_key: v_cfg})
        await query.answer("Tutorial link deleted.", show_alert=True)
        return await edit_or_reply(query, 
            "🗑️ <b>SUCCESSFULLY DELETED TUTORIAL LINK</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data=f"cset_v_tutorial:{slot}")]])
        )

    if data.startswith("cset_v_time:"):
        slot = int(data.split(":")[1])
        r = record(client)
        v_key = f"verify_{slot}" if slot > 1 else "verify_1"
        v_cfg = r.get(v_key, {})
        mins = v_cfg.get("time_minutes", 480)
        time_str = format_time_minutes(mins)

        text = (
            "<b>HERE YOU CAN MANAGE YOUR BOT VERIFICATION TIME SETTING.</b>\n\n"
            f"<b>TIME -</b> {time_str}"
        )
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("SET TIME", callback_data=f"cset_v_set_time:{slot}")],
            [InlineKeyboardButton("‹ BACK", callback_data=f"cset_token_verification:{slot}")]
        ])
        return await edit_or_reply(query, text, reply_markup=markup)

    if data.startswith("cset_v_set_time:"):
        slot = int(data.split(":")[1])
        await query.answer()
        await edit_or_reply(query, 
            "<b>SEND ME A TIME IN LIKE THIS - 1h OR 15m</b>\n\n"
            "<code>/cancel</code> - <b>Cancel THIS PROCESS.</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data=f"cset_v_time:{slot}")]])
        )
        try:
            tm_msg = await client.listen(chat_id=user_id, timeout=120)
        except Exception:
            return

        tm_raw = (tm_msg.text or "").strip()
        try: await tm_msg.delete()
        except Exception: pass

        if tm_raw.lower() == "/cancel":
            return await edit_or_reply(query, "❌ <b>Process Cancelled.</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data=f"cset_v_time:{slot}")]]))

        mins = parse_time_string(tm_raw)
        r = record(client)
        v_key = f"verify_{slot}" if slot > 1 else "verify_1"
        v_cfg = r.get(v_key, {})
        v_cfg["time_minutes"] = mins
        save(client, **{v_key: v_cfg})

        formatted = format_time_minutes(mins)
        return await edit_or_reply(query, 
            f"🧭 <b>SUCCESSFULLY SET VERIFY TIME - {formatted}</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data=f"cset_token_verification:{slot}")]])
        )

    # ---------------- PREMIUM PLAN ----------------
    if data == "cset_premium_plan":
        r = record(client)
        prem_on = bool(r.get("premium_is_on", False))
        prem_status = "PREMIUM IS ON - ✅" if prem_on else "PREMIUM IS OFF - ❌"
        text = (
            "<b>HERE YOU CAN MANAGE YOUR PREMIUM SETTINGS HERE</b>\n\n"
            "<b>THIS FEATURE WORK ONLY WHEN TOKEN VERIFICATION IS ENABLED</b>"
        )
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("📝 PREMIUM PLAN TEXT 📝", callback_data="cset_prem_text")],
            [InlineKeyboardButton("➕ ADD PREMIUM USER ➕", callback_data="cset_prem_add")],
            [InlineKeyboardButton("➖ REMOVE PREMIUM USER ➖", callback_data="cset_prem_rem")],
            [InlineKeyboardButton("👥 PREMIUM USERS LIST 👥", callback_data="cset_prem_list")],
            [InlineKeyboardButton("💳 SET / MANAGE QR & UPI 🖼️", callback_data="cset_qr_upi_menu")],
            [InlineKeyboardButton(f"🔒 {prem_status}", callback_data="cset_prem_toggle")],
            [InlineKeyboardButton("‹ BACK", callback_data="settings_back")]
        ])
        return await edit_or_reply(query, text, reply_markup=markup)

    if data == "cset_qr_upi_menu":
        r = record(client)
        p_photo = r.get("premium_plan_photo")
        p_upi = r.get("premium_upi_id")
        photo_str = "✅ Photo Set" if p_photo else "❌ Not Set"
        upi_str = p_upi if p_upi else "Not Set"

        text = (
            "<b>MANAGE QR CODE PHOTO & UPI ID FOR PREMIUM PAYMENTS</b>\n\n"
            f"🖼️ <b>QR Code Photo:</b> {photo_str}\n"
            f"💳 <b>UPI ID:</b> <code>{upi_str}</code>"
        )
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("🖼️ SET QR PHOTO", callback_data="cset_set_qr"), InlineKeyboardButton("🗑️ DELETE QR PHOTO", callback_data="cset_del_qr")],
            [InlineKeyboardButton("💳 SET UPI ID", callback_data="cset_set_upi"), InlineKeyboardButton("🗑️ DELETE UPI ID", callback_data="cset_del_upi")],
            [InlineKeyboardButton("‹ BACK", callback_data="cset_premium_plan")]
        ])
        return await edit_or_reply(query, text, reply_markup=markup)

    if data == "cset_del_qr":
        save(client, premium_plan_photo=None)
        await query.answer("QR Code Photo deleted.", show_alert=True)
        return await callbacks(client, type('Q', (), {'data': 'cset_qr_upi_menu', 'from_user': query.from_user, 'message': query.message, 'answer': query.answer})())

    if data == "cset_del_upi":
        save(client, premium_upi_id=None)
        await query.answer("UPI ID deleted.", show_alert=True)
        return await callbacks(client, type('Q', (), {'data': 'cset_qr_upi_menu', 'from_user': query.from_user, 'message': query.message, 'answer': query.answer})())

    if data == "cset_set_qr":
        await query.answer()
        prompt_text = (
            "<b>PLEASE SEND YOUR QR CROP PHOTO...</b>\n\n"
            "📸 <i>Send the cropped QR photo/image directly in this chat.</i>\n\n"
            "<code>/cancel</code> - <b>Cancel THIS PROCESS.</b>"
        )
        await edit_or_reply(query, prompt_text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="cset_qr_upi_menu")]]))
        try:
            q_msg = await client.listen(chat_id=user_id, timeout=120)
        except Exception:
            return

        if q_msg.text and q_msg.text.strip().lower() == "/cancel":
            try: await q_msg.delete()
            except Exception: pass
            return await edit_or_reply(query, "❌ <b>Process Cancelled.</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="cset_qr_upi_menu")]]))

        photo_id = None
        if q_msg.photo:
            photo_id = q_msg.photo.file_id
        elif q_msg.document and q_msg.document.mime_type and q_msg.document.mime_type.startswith("image/"):
            photo_id = q_msg.document.file_id

        try: await q_msg.delete()
        except Exception: pass

        if not photo_id:
            return await edit_or_reply(query, "❌ <b>Please send a valid cropped photo/image.</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="cset_qr_upi_menu")]]))

        save(client, premium_plan_photo=photo_id)
        confirm_text = "✅ <b>QR CODE PHOTO SET HO GAYI!</b>"
        confirm_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("🖼️ CHANGE QR PHOTO", callback_data="cset_set_qr")],
            [InlineKeyboardButton("‹ BACK", callback_data="cset_qr_upi_menu")]
        ])
        return await edit_or_reply(query, confirm_text, reply_markup=confirm_markup)

    if data == "cset_set_upi":
        await query.answer()
        prompt_text = (
            "<b>PLEASE SEND YOUR UPI ID...</b>\n\n"
            "💳 <i>Example:</i> <code>ash@upi</code> or <code>username@okhdfcbank</code>\n\n"
            "<code>/cancel</code> - <b>Cancel THIS PROCESS.</b>"
        )
        await edit_or_reply(query, prompt_text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="cset_qr_upi_menu")]]))
        try:
            u_msg = await client.listen(chat_id=user_id, timeout=120)
        except Exception:
            return

        u_raw = (u_msg.text or "").strip()
        try: await u_msg.delete()
        except Exception: pass

        if u_raw.lower() == "/cancel":
            return await edit_or_reply(query, "❌ <b>Process Cancelled.</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="cset_qr_upi_menu")]]))

        if not u_raw or " " in u_raw:
            return await edit_or_reply(query, "❌ <b>Invalid UPI ID format.</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="cset_qr_upi_menu")]]))

        save(client, premium_upi_id=u_raw)
        confirm_text = f"✅ <b>UPI ID SET HO GAYI:</b> <code>{u_raw}</code>"
        confirm_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("💳 CHANGE UPI ID", callback_data="cset_set_upi")],
            [InlineKeyboardButton("‹ BACK", callback_data="cset_qr_upi_menu")]
        ])
        return await edit_or_reply(query, confirm_text, reply_markup=confirm_markup)

    if data == "cset_prem_toggle":
        r = record(client)
        new_on = not bool(r.get("premium_is_on", False))
        save(client, premium_is_on=new_on)
        prem_status = "PREMIUM IS ON - ✅" if new_on else "PREMIUM IS OFF - ❌"
        text = (
            "<b>HERE YOU CAN MANAGE YOUR PREMIUM SETTINGS HERE</b>\n\n"
            "<b>THIS FEATURE WORK ONLY WHEN TOKEN VERIFICATION IS ENABLED</b>"
        )
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("📝 PREMIUM PLAN TEXT 📝", callback_data="cset_prem_text")],
            [InlineKeyboardButton("➕ ADD PREMIUM USER ➕", callback_data="cset_prem_add")],
            [InlineKeyboardButton("➖ REMOVE PREMIUM USER ➖", callback_data="cset_prem_rem")],
            [InlineKeyboardButton("👥 PREMIUM USERS LIST 👥", callback_data="cset_prem_list")],
            [InlineKeyboardButton("💳 SET / MANAGE QR & UPI 🖼️", callback_data="cset_qr_upi_menu")],
            [InlineKeyboardButton(f"🔒 {prem_status}", callback_data="cset_prem_toggle")],
            [InlineKeyboardButton("‹ BACK", callback_data="settings_back")]
        ])
        return await edit_or_reply(query, text, reply_markup=markup)

    if data == "cset_prem_text":
        r = record(client)
        p_text = r.get("premium_plan_text") or "Not Set"
        p_photo = r.get("premium_plan_photo")
        text = (
            "<b>HERE YOU CAN MANAGE YOUR PREMIUM PLAN TEXT</b>\n\n"
            f"<b>text -</b>\n{p_text}"
        )
        if p_photo:
            text += "\n\n🖼️ <i>QR Code / UPI Photo is also set!</i>"
        markup = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("SET PREMIUM PLAN TEXT", callback_data="cset_prem_set_text"),
                InlineKeyboardButton("DELETE PREMIUM PLAN TEXT", callback_data="cset_prem_del_text")
            ],
            [InlineKeyboardButton("‹ BACK", callback_data="cset_premium_plan")]
        ])
        return await edit_or_reply(query, text, reply_markup=markup)

    if data == "cset_prem_set_text":
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
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="cset_prem_text")]])
        )
        try:
            pt_msg = await client.listen(chat_id=user_id, timeout=120)
        except Exception:
            return

        if pt_msg.text and pt_msg.text.strip().lower() == "/cancel":
            try: await pt_msg.delete()
            except Exception: pass
            return await edit_or_reply(query, "❌ <b>Process Cancelled.</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="cset_prem_text")]]))

        photo_id = None
        plan_str = ""
        if pt_msg.photo:
            photo_id = pt_msg.photo.file_id
            plan_str = pt_msg.caption or ""
        elif pt_msg.text:
            plan_str = pt_msg.text.strip()
        
        try: await pt_msg.delete()
        except Exception: pass

        save(client, premium_plan_text=plan_str, premium_plan_photo=photo_id)
        return await edit_or_reply(query, 
            "<b>SUCCESSFULLY SET PREMIUM PLAN TEXT ✅</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="cset_prem_text")]])
        )

    if data == "cset_prem_del_text":
        save(client, premium_plan_text=None, premium_plan_photo=None)
        await query.answer("Premium plan text deleted.", show_alert=True)
        return await edit_or_reply(query, 
            "🗑️ <b>SUCCESSFULLY DELETED PREMIUM PLAN TEXT</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="cset_prem_text")]])
        )

    if data == "cset_prem_add":
        await query.answer()
        await edit_or_reply(query, 
            "<b>NOW SEND ME USER ID</b>\n\n"
            "<code>/cancel</code> - <b>Cancel THIS PROCESS.</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="cset_premium_plan")]])
        )
        try:
            uid_msg = await client.listen(chat_id=user_id, timeout=120)
        except Exception:
            return

        uid_raw = (uid_msg.text or "").strip()
        try: await uid_msg.delete()
        except Exception: pass

        if uid_raw.lower() == "/cancel":
            return await edit_or_reply(query, "❌ <b>Process Cancelled.</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="cset_premium_plan")]]))

        if not uid_raw.isdigit():
            return await edit_or_reply(query, 
                "<b>Not A Valid Integer, Start your process again.</b>",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="cset_prem_add")]])
            )

        target_uid = int(uid_raw)
        text = (
            "<b>CHOOSE YOUR PLAN VALIDITY FOR THIS USER</b>\n\n"
            "<code>/cancel</code> - <b>Cancel THIS PROCESS.</b>"
        )
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("3 Days", callback_data=f"cset_prem_val:{target_uid}:3d")],
            [InlineKeyboardButton("1 Week", callback_data=f"cset_prem_val:{target_uid}:1w")],
            [InlineKeyboardButton("1 Month", callback_data=f"cset_prem_val:{target_uid}:1mo")],
            [InlineKeyboardButton("Custom Time", callback_data=f"cset_prem_val:{target_uid}:custom")],
            [InlineKeyboardButton("‹ BACK", callback_data="cset_premium_plan")]
        ])
        return await edit_or_reply(query, text, reply_markup=markup)

    if data.startswith("cset_prem_val:"):
        _, target_uid_s, val_code = data.split(":")
        target_uid = int(target_uid_s)
        now = int(time.time())

        if val_code == "custom":
            await query.answer()
            await edit_or_reply(query, 
                "<b>SEND ME CUSTOM VALIDITY LIKE - 1h, 10d, 2mo, 1y</b>\n\n"
                "<code>/cancel</code> - <b>Cancel THIS PROCESS.</b>",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="cset_prem_add")]])
            )
            try:
                c_msg = await client.listen(chat_id=user_id, timeout=120)
            except Exception:
                return

            c_raw = (c_msg.text or "").strip()
            try: await c_msg.delete()
            except Exception: pass

            if c_raw.lower() == "/cancel":
                return await edit_or_reply(query, "❌ <b>Process Cancelled.</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="cset_premium_plan")]]))

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

        r = record(client)
        p_users = list(r.get("premium_users", []))
        p_users = [u for u in p_users if int(u.get("user_id", 0)) != target_uid]
        p_users.append({"user_id": target_uid, "expires_at": exp, "added_at": now})
        save(client, premium_users=p_users)

        return await edit_or_reply(query, 
            f"✨ <b>SUCCESSFULLY ADDED USER <code>{target_uid}</code> AS PREMIUM USER FOR {dur_str} ✅</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="cset_premium_plan")]])
        )

    if data == "cset_prem_rem":
        await query.answer()
        await edit_or_reply(query, 
            "<b>SEND USER ID TO REMOVE FROM PREMIUM:</b>\n\n"
            "<code>/cancel</code> - <b>Cancel THIS PROCESS.</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="cset_premium_plan")]])
        )
        try:
            r_msg = await client.listen(chat_id=user_id, timeout=120)
        except Exception:
            return

        r_raw = (r_msg.text or "").strip()
        try: await r_msg.delete()
        except Exception: pass

        if r_raw.lower() == "/cancel":
            return await edit_or_reply(query, "❌ <b>Process Cancelled.</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="cset_premium_plan")]]))

        if not r_raw.isdigit():
            return await edit_or_reply(query, "<b>Not A Valid Integer.</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="cset_premium_plan")]]) )

        rem_uid = int(r_raw)
        r = record(client)
        p_users = [u for u in r.get("premium_users", []) if int(u.get("user_id", 0)) != rem_uid]
        save(client, premium_users=p_users)

        return await edit_or_reply(query, 
            f"🗑️ <b>SUCCESSFULLY REMOVED USER <code>{rem_uid}</code> FROM PREMIUM!</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="cset_premium_plan")]])
        )

    if data == "cset_prem_list":
        r = record(client)
        p_users = r.get("premium_users", [])
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

        markup = InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="cset_premium_plan")]])
        return await edit_or_reply(query, text, reply_markup=markup)

    # ---------------- FORCE SUBSCRIBE ----------------
    if data == "cset_fsub_menu":
        r = record(client)
        channels = r.get("force_channels", [])
        ch_text = "\n".join([f"• <code>{c}</code>" for c in channels]) if channels else "None"
        text = (
            "📢 <b>CUSTOM FORCE SUBSCRIBE:</b>\n\n"
            "Users must join these channels to use your bot.\n\n"
            f"<b>Connected Channels:</b>\n{ch_text}"
        )
        markup = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("➕ ADD CHANNEL", callback_data="cset_fsub_add"),
                InlineKeyboardButton("🗑️ CLEAR ALL", callback_data="cset_fsub_del")
            ],
            [InlineKeyboardButton("‹ BACK", callback_data="settings_back")]
        ])
        return await edit_or_reply(query, text, reply_markup=markup)

    if data == "cset_fsub_add":
        await query.answer()
        me = client.me or (await client.get_me())
        prompt_text = (
            "<b>FORWARD A MESSAGE FROM CHANNEL TO ME,\n"
            f"AND MAKE SURE @{me.username} IS ADMIN IN THAT CHANNEL.</b>\n\n"
            "<code>/cancel</code> - <b>Cancel THIS PROCESS.</b>"
        )
        await edit_or_reply(query, prompt_text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="cset_fsub_menu")]]))
        try:
            f_msg = await client.listen(chat_id=user_id, timeout=120)
        except Exception:
            return

        f_raw = (f_msg.text or "").strip()
        try: await f_msg.delete()
        except Exception: pass

        if f_raw.lower() == "/cancel":
            return await edit_or_reply(query, "❌ <b>Process Cancelled.</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="cset_fsub_menu")]]))

        cid = None
        if f_msg.forward_from_chat:
            cid = f_msg.forward_from_chat.id
        elif f_raw.startswith("-100") or (f_raw.startswith("-") and f_raw[1:].isdigit()):
            cid = int(f_raw)
        elif f_raw.isdigit():
            cid = int(f"-100{f_raw}")

        if not cid:
            return await edit_or_reply(query, "❌ <b>Invalid Channel.</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="cset_fsub_menu")]]))

        r = record(client)
        chs = list(r.get("force_channels", []))
        if cid not in chs:
            chs.append(cid)
            save(client, force_channels=chs)

        return await edit_or_reply(query, "✅ <b>SUCCESSFULLY ADDED FORCE SUBSCRIBE CHANNEL!</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="cset_fsub_menu")]]))

    if data == "cset_fsub_del":
        save(client, force_channels=[])
        await query.answer("Cleared force sub channels.", show_alert=True)
        return await edit_or_reply(query, "🗑️ <b>CLEARED ALL FORCE SUBSCRIBE CHANNELS</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="cset_fsub_menu")]]))

    # ---------------- AUTO DELETE ----------------
    if data == "cset_auto_delete_menu":
        r = record(client)
        ad_on = bool(r.get("auto_delete_enabled", False))
        ad_mins = int(r.get("auto_delete_minutes", 15))
        status_str = f"ENABLED ({ad_mins} mins) ✅" if ad_on else "DISABLED ❌"

        text = (
            "♻️ <b>AUTO DELETE SETTINGS:</b>\n\n"
            "Automatically deletes files delivered by your bot after a set duration to prevent copyright issues.\n\n"
            f"• <b>Status:</b> <code>{status_str}</code>"
        )
        markup = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("5 min", callback_data="cset_ad_set:5"),
                InlineKeyboardButton("10 min", callback_data="cset_ad_set:10"),
                InlineKeyboardButton("15 min", callback_data="cset_ad_set:15"),
                InlineKeyboardButton("30 min", callback_data="cset_ad_set:30")
            ],
            [InlineKeyboardButton("DISABLE ❌" if ad_on else "ENABLE ✅", callback_data="cset_ad_toggle")],
            [InlineKeyboardButton("‹ BACK", callback_data="settings_back")]
        ])
        return await edit_or_reply(query, text, reply_markup=markup)

    if data.startswith("cset_ad_set:"):
        mins = int(data.split(":")[1])
        save(client, auto_delete_enabled=True, auto_delete_minutes=mins)
        await query.answer(f"Auto delete set to {mins} minutes!", show_alert=True)
        return await callbacks(client, type('Q', (), {'data': 'cset_auto_delete_menu', 'from_user': query.from_user, 'message': query.message, 'answer': query.answer})())

    if data == "cset_ad_toggle":
        r = record(client)
        new_on = not bool(r.get("auto_delete_enabled", False))
        save(client, auto_delete_enabled=new_on)
        await query.answer(f"Auto delete {'enabled' if new_on else 'disabled'}!", show_alert=True)
        return await callbacks(client, type('Q', (), {'data': 'cset_auto_delete_menu', 'from_user': query.from_user, 'message': query.message, 'answer': query.answer})())


def register(client):
    client.add_handler(MessageHandler(settings, filters.command("settings") & filters.private), group=0)
    client.add_handler(CallbackQueryHandler(callbacks, filters.regex(r"^(settings|settings_back|log_channel|set_log_channel|delete_log_channel|database_channel|set_database_channel|delete_database_channel|admins_menu|add_admin_prompt|admin_info:|adm_tgl:|adm_trans:|adm_rem:|link_shortener|add_shortener|delete_shortener|protect_menu|protect_toggle|custom_caption|caption_see|caption_delete|caption_edit|custom_button|button_add|button_delete|clone_my_clone_info|cset_)")), group=0)
    return client

