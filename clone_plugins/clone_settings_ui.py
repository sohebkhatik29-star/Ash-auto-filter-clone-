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


def settings_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 LOG CHANNEL", callback_data="log_channel")],
        [InlineKeyboardButton("☁️ DATABASE CHANNEL", callback_data="database_channel")],
        [InlineKeyboardButton("👥 ADMINS", callback_data="admins_menu")],
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
        return await query.message.edit_text(text, reply_markup=markup)

    if data == "set_log_channel":
        await query.answer()
        me = client.me or (await client.get_me())
        prompt_text = (
            "<b>FORWARD LOG CHANNEL ANY MESSAGE TO ME,\n"
            f"AND MAKE SURE @{me.username} IS ADMIN IN YOUR CHANNEL.</b>\n\n"
            "<code>/cancel</code> - <b>CANCEL THIS PROCESS.</b>"
        )
        await query.message.edit_text(
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
            return await query.message.edit_text(
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
            return await query.message.edit_text(
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
            return await query.message.edit_text(
                f"❌ <b>Failed to connect channel!</b>\n\nMake sure <b>@{me.username}</b> is an <b>ADMIN</b> in the channel with post permissions.\n\n<code>Error: {err}</code>",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❮ BACK", callback_data="log_channel")]])
            )

        save(client, log_channel=channel_id, log_channel_title=channel_title)
        return await query.message.edit_text(
            f"⚡ <b>SUCCESSFULLY ADDED YOUR LOG CHANNEL - {channel_title}</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❮ BACK", callback_data="log_channel")]])
        )

    if data == "delete_log_channel":
        save(client, log_channel=None, log_channel_title=None)
        await query.answer("🗑️ Successfully deleted your log channel", show_alert=False)
        return await query.message.edit_text(
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
        return await query.message.edit_text(text, reply_markup=markup)

    if data == "set_database_channel":
        await query.answer()
        me = client.me or (await client.get_me())
        prompt_text = (
            "<b>FORWARD DATABASE CHANNEL ANY MESSAGE TO ME,\n"
            f"AND MAKE SURE @{me.username} IS ADMIN IN YOUR CHANNEL.</b>\n\n"
            "<code>/cancel</code> - <b>CANCEL THIS PROCESS.</b>"
        )
        await query.message.edit_text(
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
            return await query.message.edit_text(
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
            return await query.message.edit_text(
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
            return await query.message.edit_text(
                f"❌ <b>Failed to connect channel!</b>\n\nMake sure <b>@{me.username}</b> is an <b>ADMIN</b> in the channel with post permissions.\n\n<code>Error: {err}</code>",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❮ BACK", callback_data="database_channel")]])
            )

        save(client, database_channel=channel_id, database_channel_title=channel_title)
        return await query.message.edit_text(
            f"⚡ <b>SUCCESSFULLY ADDED YOUR DATABASE CHANNEL - {channel_title}</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❮ BACK", callback_data="database_channel")]])
        )

    if data == "delete_database_channel":
        save(client, database_channel=None, database_channel_title=None)
        await query.answer("🗑️ Successfully deleted your database channel", show_alert=False)
        return await query.message.edit_text(
            "🗑️ <b>SUCCESSFULLY DELETED DATABASE CHANNEL</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❮ BACK", callback_data="database_channel")]])
        )

    if data == "admins_menu":
        if not (is_bot_owner(client, user_id) or has_permission(client, user_id, "add_admins")):
            return await query.answer("❌ You don't have permission to manage admins.", show_alert=True)
        return await query.message.edit_text(
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
        await query.message.edit_text(
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
            return await query.message.edit_text(
                "❌ <b>Process Cancelled.</b>",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❮ BACK", callback_data="admins_menu")]])
            )

        if not (raw_uid.isdigit() or (raw_uid.startswith("-") and raw_uid[1:].isdigit())):
            return await query.message.edit_text(
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
        return await query.message.edit_text(
            "<b>SUCCESSFULLY UPDATED</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❮ BACK", callback_data="admins_menu")]])
        )

    if data.startswith("admin_info:"):
        target_uid = int(data.split(":")[1])
        adm = get_admin_data(client, target_uid)
        if not adm:
            return await query.answer("❌ Admin not found!", show_alert=True)
        return await query.message.edit_text(
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
            return await query.message.edit_text(
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
        return await query.message.edit_text(
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
        return await query.message.edit_text(
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
        return await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup([
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
        return await query.message.edit_text(
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
        return await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Edit", callback_data="caption_edit"), InlineKeyboardButton("See", callback_data="caption_see"), InlineKeyboardButton("Delete", callback_data="caption_delete")],
            [InlineKeyboardButton("back", callback_data="settings_back")]
        ]))

    if data == "caption_edit":
        await query.answer()
        await query.message.edit_text(
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
            return await query.message.edit_text("❌ Cancelled.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❮ BACK", callback_data="custom_caption")]]))
        save(client, custom_caption=cap_text)
        await update_user_info(user_id, {"custom_caption": cap_text})
        return await query.message.edit_text(
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
        return await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(rows))

    if data == "button_add":
        await query.answer()
        await query.message.edit_text(
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
            return await query.message.edit_text("❌ Cancelled.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❮ BACK", callback_data="custom_button")]]))
        
        await query.message.edit_text(
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
            return await query.message.edit_text("❌ URL must start with http://, https:// or tg://", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❮ BACK", callback_data="custom_button")]]))
        if btn_url.startswith("t.me/"):
            btn_url = "https://" + btn_url
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
            "<b>Custom Button:</b>\n\nYou can add a custom button to your message\n\n<i>All buttons deleted.</i>",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ Add Button", callback_data="button_add")],
                [InlineKeyboardButton("back", callback_data="settings_back")]
            ])
        )


def register(client):
    client.add_handler(MessageHandler(settings, filters.command("settings") & filters.private), group=0)
    client.add_handler(CallbackQueryHandler(callbacks, filters.regex(r"^(settings|settings_back|log_channel|set_log_channel|delete_log_channel|database_channel|set_database_channel|delete_database_channel|admins_menu|add_admin_prompt|admin_info:\d+|adm_tgl:\d+:[a-z_]+|adm_trans:\d+|adm_rem:\d+|link_shortener|add_shortener|delete_shortener|protect_menu|protect_toggle|custom_caption|caption_see|caption_delete|caption_edit|custom_button|button_add|button_delete)$")), group=0)
    return client

