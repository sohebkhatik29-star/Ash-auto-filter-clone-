# ASH FILE STORE & CLONE MANAGER
import asyncio
import random
import base64
import secrets
import time
from pyrogram import filters, enums
from pyrogram.handlers import MessageHandler, CallbackQueryHandler
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from clone_plugins.dbusers import clonedb
from clone_plugins.users_api import (
    get_user, update_user_info, get_short_link, format_caption,
    is_user_premium, check_user_verified, set_user_verified,
    create_verify_token, consume_verify_token, format_time_minutes,
    format_auto_delete_time, parse_auto_delete_time
)
from plugins.clone import mongo_db
from config import BOT_USERNAME, PICS, CUSTOM_FILE_CAPTION, ADMINS, UPDATE_CHANNEL, tg_link
from Script import script
from validators import domain


def get_size(size):
    units = ["Bytes", "KB", "MB", "GB", "TB", "PB", "EB"]
    size = float(size); i = 0
    while size >= 1024.0 and i < len(units) - 1:
        i += 1; size /= 1024.0
    return f"{size:.2f} {units[i]}"


def bot_record(client):
    if mongo_db is None: return {}
    try:
        b_id = getattr(client, "me", None) and client.me.id
        if b_id:
            rec = mongo_db.bots.find_one({"bot_id": int(b_id)})
            if rec: return rec
            rec = mongo_db.bots.find_one({"token": getattr(client, "_token", "")})
            if rec: return rec
        m_rec = mongo_db.master_settings.find_one({"type": "master_config"}) or mongo_db.master_settings.find_one({})
        return m_rec or {}
    except Exception:
        return {}


def owner_id(client): return int(bot_record(client).get("user_id", 0))


def is_owner_or_mod(client, user_id):
    uid = int(user_id)
    try:
        if uid in [int(x) for x in ADMINS if str(x).strip().lstrip("-").isdigit()]:
            return True
    except Exception:
        pass
    rec = bot_record(client)
    if not rec:
        from config import PUBLIC_FILE_STORE
        return bool(PUBLIC_FILE_STORE)
    if int(rec.get("user_id", 0)) == uid:
        return True
    if uid in [int(x) for x in rec.get("moderators", [])]:
        return True
    if rec.get("mode") == "public":
        return True
    from config import PUBLIC_FILE_STORE
    return bool(PUBLIC_FILE_STORE)


def make_file_link(bot_username, file_id, protected=False):
    prefix = "filep" if protected else "file"
    raw = f"{prefix}_{file_id}".encode()
    payload = base64.urlsafe_b64encode(raw).decode().rstrip("=")
    return f"https://t.me/{bot_username}?start={payload}"


async def force_markup(client, user_id, original_payload):
    rec = bot_record(client)
    if not rec:
        return None
    if not rec.get("fsub_enabled", False):
        if not rec.get("force_channels") and not rec.get("force_sub"):
            return None

    channels = rec.get("fsub_channels", [])
    if not channels and rec.get("force_channels"):
        channels = rec.get("force_channels", [])
    if not channels and rec.get("force_sub"):
        channels = [rec.get("force_sub")]

    if not channels:
        return None

    missing = []
    for idx, ch in enumerate(channels):
        if isinstance(ch, dict):
            chat_id = ch.get("chat_id")
            mode = ch.get("mode", "normal")
            title = ch.get("title") or f"Channel {idx+1}"
            link = ch.get("invite_link")
        else:
            chat_id = ch
            mode = "normal"
            title = f"Channel {idx+1}"
            link = None

        if not chat_id:
            continue

        is_sub = False
        try:
            member = await client.get_chat_member(chat_id, user_id)
            if member.status not in (enums.ChatMemberStatus.LEFT, enums.ChatMemberStatus.BANNED):
                is_sub = True
        except Exception:
            pass

        if not is_sub and mode == "request" and mongo_db is not None:
            try:
                req_doc = mongo_db.join_requests.find_one({"bot_id": client.me.id, "chat_id": chat_id, "user_id": user_id})
                if req_doc:
                    is_sub = True
            except Exception:
                pass

        if not is_sub:
            if not link:
                try:
                    c_obj = await client.get_chat(chat_id)
                    link = c_obj.invite_link or (f"https://t.me/{c_obj.username}" if c_obj.username else None)
                except Exception:
                    pass
            missing.append({
                "chat_id": chat_id,
                "title": title,
                "link": link or f"https://t.me/{chat_id}",
                "idx": idx + 1
            })

    if not missing:
        return None

    buttons = []
    # 1. Missing channel join buttons
    for item in missing:
        btn_title = f"Join {item['title']} ↗️" if len(item['title']) <= 25 else f"Join Channel {item['idx']} ↗️"
        buttons.append([InlineKeyboardButton(btn_title, url=item["link"])])

    # 2. Custom fake buttons if set
    fsub_btns = rec.get("fsub_buttons", [])
    for r_item in fsub_btns:
        row = []
        if isinstance(r_item, dict) and "buttons" in r_item:
            for b in r_item["buttons"]:
                row.append(InlineKeyboardButton(f"{b['text']} ↗️", url=b["url"]))
        elif isinstance(r_item, dict) and "text" in r_item:
            row.append(InlineKeyboardButton(f"{r_item['text']} ↗️", url=r_item.get("url", "https://t.me")))
        if row:
            buttons.append(row)

    # 3. Try again button
    me = client.me or (await client.get_me())
    if original_payload:
        try_again_url = f"https://t.me/{me.username}?start={original_payload}"
        buttons.append([InlineKeyboardButton("🔄 TRY AGAIN 🔄", url=try_again_url)])
    else:
        buttons.append([InlineKeyboardButton("🔄 TRY AGAIN 🔄", callback_data=f"verify:{original_payload}")])

    return InlineKeyboardMarkup(buttons)


async def send_fsub_prompt(client, message, payload):
    markup = await force_markup(client, message.from_user.id, payload)
    if not markup:
        return False
    rec = bot_record(client)
    custom_text = rec.get("fsub_text")
    if custom_text:
        text = custom_text.replace("{user_mention}", message.from_user.mention).replace("{mention}", message.from_user.mention)
    else:
        text = "👉 <b>PLEASE JOIN MY UPDATES CHANNEL AND THEN CLICK ON TRY AGAIN BUTTON</b> 👇"

    fsub_pic = rec.get("fsub_pic")
    has_spoiler = bool(rec.get("fsub_pic_spoiler", False))
    invert_cap = bool(rec.get("fsub_pic_invert", False))

    if fsub_pic:
        # 1. Try sending directly (works if file path, URL, or native file_id)
        try:
            await message.reply_photo(
                photo=fsub_pic,
                caption=text,
                reply_markup=markup,
                has_spoiler=has_spoiler,
                show_caption_above_media=invert_cap
            )
            return True
        except Exception:
            try:
                await message.reply_photo(
                    photo=fsub_pic,
                    caption=text,
                    reply_markup=markup,
                    has_spoiler=has_spoiler
                )
                return True
            except Exception:
                pass

        # 2. If direct send failed (e.g. cross-bot file_id), check local cache or download via Master bot
        import os
        bot_id = rec.get("bot_id") or (client.me.id if client.me else None)
        local_cache_path = f"cache/fsub_pics/{bot_id}.jpg" if bot_id else None

        if not local_cache_path or not os.path.exists(local_cache_path):
            try:
                from AshCore.bot import StreamBot
                os.makedirs("cache/fsub_pics", exist_ok=True)
                target_path = local_cache_path or f"cache/fsub_pics/{str(fsub_pic)[:15]}.jpg"
                downloaded = await StreamBot.download_media(fsub_pic, file_name=target_path)
                if downloaded and os.path.exists(downloaded):
                    local_cache_path = downloaded
            except Exception:
                pass

        if local_cache_path and os.path.exists(local_cache_path):
            try:
                await message.reply_photo(
                    photo=local_cache_path,
                    caption=text,
                    reply_markup=markup,
                    has_spoiler=has_spoiler,
                    show_caption_above_media=invert_cap
                )
                return True
            except Exception:
                try:
                    await message.reply_photo(
                        photo=local_cache_path,
                        caption=text,
                        reply_markup=markup,
                        has_spoiler=has_spoiler
                    )
                    return True
                except Exception:
                    pass

    await message.reply_text(text, reply_markup=markup, disable_web_page_preview=True)
    return True


async def access_verification(client, user_id, original_payload=""):
    rec = bot_record(client)
    if not rec:
        return None, None
    if is_user_premium(user_id, rec):
        return None, None

    # Collect all active verification slots (1, 2, 3)
    active_slots = []
    for s in (1, 2, 3):
        v_key = f"verify_{s}" if s > 1 else "verify_1"
        v_cfg = rec.get(v_key, {})
        site = v_cfg.get("shortner_site") or v_cfg.get("site") or rec.get("base_site")
        api = v_cfg.get("shortner_api") or v_cfg.get("api") or rec.get("shortener_api")
        if v_cfg.get("is_on") and site and api:
            active_slots.append((s, v_cfg, site, api))

    # Fallback to legacy verify configuration if enabled
    if not active_slots:
        if rec.get("verify_enabled") and rec.get("base_site") and rec.get("shortener_api"):
            active_slots.append((1, {
                "tutorial": rec.get("verify_tutorial"),
                "time": rec.get("verify_ttl", 480) // 60
            }, rec.get("base_site"), rec.get("shortener_api")))

    if not active_slots:
        return None, None

    # Find the first slot that user has not verified
    pending_slot_num = None
    pending_slot_cfg = None
    site_to_use = None
    api_to_use = None
    step_index = 0
    total_steps = len(active_slots)

    for idx, (s_num, s_cfg, s_site, s_api) in enumerate(active_slots):
        if not check_user_verified(user_id, client.me.id, slot=s_num):
            pending_slot_num = s_num
            pending_slot_cfg = s_cfg
            site_to_use = s_site
            api_to_use = s_api
            step_index = idx + 1
            break

    if not pending_slot_num:
        return None, None

    tutorial = pending_slot_cfg.get("tutorial") or rec.get("verify_tutorial")
    mins = int(pending_slot_cfg.get("time", pending_slot_cfg.get("time_minutes", 1440)))
    time_str = format_time_minutes(mins)

    token = create_verify_token(user_id, client.me.id, original_payload, slot=pending_slot_num)
    me = client.me or (await client.get_me())
    raw_verify_url = f"https://t.me/{me.username}?start=verify_{token}"
    try:
        short_url = await get_short_link({"base_site": site_to_use, "shortener_api": api_to_use}, raw_verify_url)
    except Exception:
        short_url = raw_verify_url
    if not short_url:
        short_url = raw_verify_url

    first_name = "User"
    try:
        u = await client.get_users(user_id)
        first_name = u.first_name or "User"
    except Exception:
        pass

    text = (
        f"Hey <b>{first_name}</b>,\n\n"
        f"<blockquote>YOU ARE NOT VERIFIED TODAY, PLEASE CLICK ON VERIFY BUTTON AND GET UNLIMITED ACCESS FOR NEXT {time_str}.\n\n"
        f"IF YOU DONOT KNOW HOW TO VERIFY THEN CLICK ON HOW TO VERIFY BUTTON AND WATCH THE VIDEO.\n\n"
        f"THIS IS AN ADS-BASED ACCESS TOKEN. IF YOU PASS ONE ACCESS TOKEN, YOU CAN ACCESS MESSAGES FROM LINKS FOR NEXT {time_str}.</blockquote>\n\n"
        f"<b>#VERIFICATION:-</b> {step_index}/{total_steps}\n\n"
        f"<blockquote>IF YOU WANT DIRECT FILES WITHOUT ANY VERIFICATIONS THEN BUY BOT SUBSCRIPTION 🥲\n\n"
        f"💳 CLICK ON BUY PREMIUM BUTTON TO BUY SUBSCRIPTION</blockquote>"
    )

    buttons = [
        [InlineKeyboardButton("🟢 VERIFY 🟢", url=short_url)]
    ]
    if tutorial:
        buttons.append([InlineKeyboardButton("🍿 HOW TO VERIFY 🍿", url=tutorial)])
    cb_data = f"c_buy_prem:{original_payload}" if original_payload else "c_buy_prem"
    buttons.append([InlineKeyboardButton("💎 BUY PREMIUM - NO NEED TO VERIFY 💎", callback_data=cb_data)])

    return text, InlineKeyboardMarkup(buttons)


def settings_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 LOG CHANNEL", callback_data="log_channel")],
        [InlineKeyboardButton("☁️ DATABASE CHANNEL", callback_data="database_channel")],
        [InlineKeyboardButton("👥 ADMINS", callback_data="admins_menu")],
        [InlineKeyboardButton("LINK SHORTENER 🔗", callback_data="link_shortener")],
        [InlineKeyboardButton("CUSTOM CAPTION 🖊️", callback_data="custom_caption")],
        [InlineKeyboardButton("CUSTOM BUTTON ➕", callback_data="custom_button")],
        [InlineKeyboardButton("PROTECT CONTENT ☂️", callback_data="protect_menu")],
        [InlineKeyboardButton("🔎 MORE FEATURES ↗", url=f"https://t.me/{BOT_USERNAME}?start=clone")],
        [InlineKeyboardButton("❮ BACK", callback_data="start_back")],
    ])


async def deliver_file(client, user_id, file_id, protected=False):
    rec = bot_record(client)
    protected = protected or bool(rec.get("protect_content", False)) or bool(rec.get("no_forward", False))
    msg = await client.send_cached_media(user_id, file_id, protect_content=protected)
    media = getattr(msg, msg.media.value, None) if msg.media else None
    size = get_size(media.file_size) if media and getattr(media, "file_size", None) else "Unknown"
    name = getattr(media, "file_name", None) if media else None or "File"
    caption_template = rec.get("custom_caption") or CUSTOM_FILE_CAPTION or f"<code>{name}</code>\n<code>Size: {size}</code>"
    caption = format_caption(caption_template, media=media, source_msg=msg, default_caption=f"<code>{name}</code>\n<code>Size: {size}</code>")
    try:
        await msg.edit_caption(caption, parse_mode=enums.ParseMode.HTML)
    except Exception:
        try:
            await msg.edit_caption(caption)
        except Exception:
            pass
    buttons = rec.get("custom_buttons", [])
    rows = [[InlineKeyboardButton(b["text"], url=b["url"])] for b in buttons if b.get("text") and b.get("url")]
    if rows:
        try: await msg.edit_reply_markup(InlineKeyboardMarkup(rows))
        except Exception: pass
    if rec.get("auto_delete_enabled", False):
        ad_sec = int(rec.get("auto_delete_time") or (int(rec.get("auto_delete_minutes", 15)) * 60))
        time_str = format_auto_delete_time(ad_sec)
        u_mention = f"<a href='tg://user?id={user_id}'>User</a>"
        try:
            u_obj = await client.get_users(user_id)
            if u_obj:
                u_mention = getattr(u_obj, "mention", u_obj.first_name)
        except Exception:
            pass

        raw_ad_text = rec.get("auto_delete_text") or (
            "<b><u>❗️❗️❗️IMPORTANT❗️️❗️❗️</u></b>\n\n"
            "This Movie File/Video will be deleted in <b><u>{time}</u> 🫥 <i></b>(Due to Copyright Issues)</i>.\n\n"
            "<b><i>Please forward this File/Video to your Saved Messages and Start Download there</b>"
        )
        ad_text = raw_ad_text.replace("{time}", time_str).replace("{user_mention}", u_mention)

        # Build custom buttons if any
        ad_btns_cfg = rec.get("auto_delete_buttons", [])
        ad_rows = []
        for r_item in ad_btns_cfg:
            row_b = []
            if isinstance(r_item, dict) and "buttons" in r_item:
                for b in r_item["buttons"]:
                    row_b.append(InlineKeyboardButton(b["text"], url=b["url"]))
            elif isinstance(r_item, dict) and "text" in r_item:
                row_b.append(InlineKeyboardButton(r_item["text"], url=r_item.get("url", "https://t.me")))
            elif isinstance(r_item, list):
                for b in r_item:
                    if isinstance(b, dict) and b.get("text"):
                        row_b.append(InlineKeyboardButton(b["text"], url=b.get("url", "https://t.me")))
            if row_b:
                ad_rows.append(row_b)
        ad_markup = InlineKeyboardMarkup(ad_rows) if ad_rows else None

        ad_pic = rec.get("auto_delete_pic")
        ad_spoil = bool(rec.get("auto_delete_pic_spoiler", False))
        ad_invert = bool(rec.get("auto_delete_pic_invert_caption", False))

        warning = None
        if ad_pic:
            try:
                warning = await client.send_photo(
                    chat_id=user_id,
                    photo=ad_pic,
                    caption=ad_text,
                    has_spoiler=ad_spoil,
                    show_caption_above_media=ad_invert,
                    reply_markup=ad_markup
                )
            except Exception:
                try:
                    warning = await client.send_photo(
                        chat_id=user_id,
                        photo=ad_pic,
                        caption=ad_text,
                        has_spoiler=ad_spoil,
                        reply_markup=ad_markup
                    )
                except Exception:
                    try:
                        import os
                        from AshCore.bot import StreamBot
                        os.makedirs("cache/ad_pics", exist_ok=True)
                        bot_id = rec.get("bot_id") or (client.me.id if getattr(client, "me", None) else None)
                        target_path = f"cache/ad_pics/{bot_id or 'shared'}.jpg"
                        downloaded = await StreamBot.download_media(ad_pic, file_name=target_path)
                        if downloaded and os.path.exists(downloaded):
                            warning = await client.send_photo(
                                chat_id=user_id,
                                photo=downloaded,
                                caption=ad_text,
                                has_spoiler=ad_spoil,
                                reply_markup=ad_markup
                            )
                    except Exception:
                        pass

        if not warning:
            try:
                warning = await client.send_message(
                    chat_id=user_id,
                    text=ad_text,
                    reply_markup=ad_markup
                )
            except Exception:
                pass

        async def _auto_del():
            await asyncio.sleep(ad_sec)
            try:
                await msg.delete()
            except Exception:
                pass
            if warning:
                try:
                    await warning.delete()
                except Exception:
                    pass

            get_again_on = bool(rec.get("auto_delete_get_again", True))
            if get_again_on:
                try:
                    again_kb = InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔒 CLOSE 🔒", callback_data="close_data")]
                    ])
                    del_txt = (
                        "🎁 <b>PREVIOUS MESSAGE IS DELETED</b>\n\n"
                        "<b>IF YOU WANT THIS PREVIOUS MESSAGE AGAIN THEN CLICK ON BELOW BUTTON OTHERWISE CLICK ON CLOSE BUTTON.</b>"
                    )
                    await client.send_message(chat_id=user_id, text=del_txt, reply_markup=again_kb)
                except Exception:
                    pass
        asyncio.create_task(_auto_del())
    return msg



async def start(client, message):
    me = await client.get_me()
    is_new_user = False
    try:
        if not await clonedb.is_user_exist(me.id, message.from_user.id):
            await clonedb.add_user(me.id, message.from_user.id)
            is_new_user = True
    except Exception:
        pass

    rec = bot_record(client)
    log_ch = rec.get("log_channel")
    if log_ch and is_new_user:
        try:
            u = message.from_user
            log_text = (
                "❓ <b>USER INFO:</b>\n\n"
                f"🪪 <b>Mention:</b> {u.mention}\n"
                f"🆔 <b>User ID:</b> <code>{u.id}</code>\n"
                f"👤 <b>First Name:</b> {u.first_name or 'None'}\n"
                f"👤 <b>Last Name:</b> {u.last_name or 'None'}\n"
                f"📎 <b>Username:</b> @{u.username or 'None'}\n\n"
                f"🌐 <b>Language:</b> {getattr(u, 'language_code', None) or 'None'}\n"
                f"⭐️ <b>Premium:</b> {bool(getattr(u, 'is_premium', False))}\n"
                f"🤖 <b>Bot:</b> {bool(getattr(u, 'is_bot', False))}\n"
                f"🚨 <b>Scam:</b> {bool(getattr(u, 'is_scam', False))}\n"
                f"⚠️ <b>Fake:</b> {bool(getattr(u, 'is_fake', False))}\n"
                f"🛡️ <b>Support:</b> {bool(getattr(u, 'is_support', False))}\n"
                f"✅ <b>Verified:</b> {bool(getattr(u, 'is_verified', False))}\n"
                f"⛔️ <b>Restricted:</b> {bool(getattr(u, 'is_restricted', False))}\n"
                f"🌐 <b>DC ID:</b> {getattr(u, 'dc_id', None) or 'None'}"
            )
            await client.send_message(chat_id=int(log_ch), text=log_text)
        except Exception:
            pass

    if len(message.command) != 2:
        buttons = [
            [InlineKeyboardButton("⚙️ SETTINGS", callback_data="settings"), InlineKeyboardButton("🤖 MY OWN BOT", url=f"https://t.me/{BOT_USERNAME}?start=clone")],
            [InlineKeyboardButton("💁 HELP", callback_data="help"), InlineKeyboardButton("ℹ️ ABOUT", callback_data="about")],
            [InlineKeyboardButton("📢 UPDATE CHANNEL", url=tg_link(UPDATE_CHANNEL, "MoviesGroupG3"))]
        ]
        
        # Add custom start buttons if configured
        start_btns = rec.get("start_buttons", [])
        for r_item in start_btns:
            row_btns = []
            if isinstance(r_item, dict) and "buttons" in r_item:
                for b in r_item["buttons"]:
                    row_btns.append(InlineKeyboardButton(b["text"], url=b["url"]))
            elif isinstance(r_item, dict) and "text" in r_item:
                row_btns.append(InlineKeyboardButton(r_item["text"], url=r_item.get("url", "https://t.me")))
            if row_btns:
                buttons.append(row_btns)

        custom_text = rec.get("start_text")
        if custom_text:
            caption = custom_text.replace("{mention}", message.from_user.mention).replace("{bot_mention}", me.mention)
        else:
            caption = script.CLONE_START_TXT.format(message.from_user.mention, me.mention)

        has_spoiler = bool(rec.get("start_pic_spoiler", False))
        custom_pic = rec.get("start_pic")
        start_photo = custom_pic or (random.choice(PICS) if PICS else None)

        if start_photo:
            try:
                return await message.reply_photo(photo=start_photo, caption=caption, reply_markup=InlineKeyboardMarkup(buttons), has_spoiler=has_spoiler)
            except Exception:
                try:
                    return await message.reply_photo(photo=start_photo, caption=caption, reply_markup=InlineKeyboardMarkup(buttons))
                except Exception:
                    pass
        return await message.reply(caption, reply_markup=InlineKeyboardMarkup(buttons))

    data = message.command[1]
    if data.lower() == "clone":
        text = (
            "👑 <b>CLONE BOT CREATOR</b>\n\n"
            "<i>To create your own clone bot or manage your existing bots, please use our Master Parent Bot.</i>"
        )
        return await message.reply(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🤖 OPEN MASTER BOT ↗", url=f"https://t.me/{BOT_USERNAME}?start=clone")]]))
    if data.lower() == "settings":
        from clone_plugins import clone_settings_ui as cset
        return await cset.settings(client, message)

    # 1. Custom batch routing (plain or decoded)
    if data.startswith("batch_"):
        from clone_plugins import custom_batch
        return await custom_batch.batch_start(client, message)

    # 2. Channel batch routing (plain or decoded)
    if data.startswith("cbatch_"):
        from clone_plugins import channel_batch
        return await channel_batch.batch_start_deliver(client, message)

    # 3. Special link routing (plain or decoded)
    if data.startswith("special_"):
        from clone_plugins import special_link
        return await special_link.open_special(client, message)

    # 4. Single message / file link routing
    if data.startswith("msg_") or data.startswith("msM_"):
        from clone_plugins import single_link
        return await single_link.open_single(client, message)

    # 5. Check if base64 encoded payload
    try:
        pad = (4 - len(data) % 4) % 4
        raw_dec = base64.urlsafe_b64decode(data + "=" * pad).decode("utf-8", errors="ignore")
        if raw_dec.startswith("batch_"):
            message.command[1] = raw_dec
            from clone_plugins import custom_batch
            return await custom_batch.batch_start(client, message)
        if raw_dec.startswith("cbatch_"):
            message.command[1] = raw_dec
            from clone_plugins import channel_batch
            return await channel_batch.batch_start_deliver(client, message)
        if raw_dec.startswith("special_"):
            message.command[1] = raw_dec
            from clone_plugins import special_link
            return await special_link.open_special(client, message)
        if raw_dec.startswith("msg_") or raw_dec.startswith("msM_"):
            from clone_plugins import single_link
            return await single_link.open_single(client, message)
    except Exception:
        pass

    # 6. Check databases directly by token
    if mongo_db is not None:
        try:
            clean_tok = data.split("_", 1)[1] if "_" in data else data
            if mongo_db.share_links.find_one({"token": data}) or mongo_db.share_links.find_one({"token": clean_tok}):
                from clone_plugins import single_link
                return await single_link.open_single(client, message)
            if mongo_db.custom_batch_links.find_one({"token": data}) or mongo_db.custom_batch_links.find_one({"token": clean_tok}):
                message.command[1] = f"batch_{clean_tok}"
                from clone_plugins import custom_batch
                return await custom_batch.batch_start(client, message)
            if mongo_db.channel_batch_links.find_one({"token": data}) or mongo_db.channel_batch_links.find_one({"token": clean_tok}):
                message.command[1] = f"cbatch_{clean_tok}"
                from clone_plugins import channel_batch
                return await channel_batch.batch_start_deliver(client, message)
            if mongo_db.special_links.find_one({"token": data}) or mongo_db.special_links.find_one({"token": clean_tok}):
                message.command[1] = f"special_{clean_tok}"
                from clone_plugins import special_link
                return await special_link.open_special(client, message)
        except Exception:
            pass
        
    if data.startswith("verify_") or data.startswith("verify-"):
        token_str = data.split("_", 1)[1] if data.startswith("verify_") else data.split("-", 1)[1]
        orig_payload, slot_used = consume_verify_token(token_str, message.from_user.id, me.id)
        if orig_payload is None and mongo_db is not None:
            rec_t = mongo_db.access_tokens.find_one({"bot_id": me.id, "token": token_str, "user_id": int(message.from_user.id)})
            if rec_t:
                orig_payload = ""
                slot_used = 1
        
        if orig_payload is None:
            return await message.reply("❌ <b>Invalid or expired verification link!</b>\n\nPlease verify again.")
        
        v_key = f"verify_{slot_used}" if slot_used > 1 else "verify_1"
        v_cfg = rec.get(v_key, {})
        time_mins = int(v_cfg.get("time", v_cfg.get("time_minutes", 1440)))
        
        set_user_verified(message.from_user.id, me.id, duration_minutes=time_mins, slot=slot_used)
        dur_str = format_time_minutes(time_mins)
        
        # Send log to verify_log_channel if configured
        log_ch = rec.get("verify_log_channel")
        if log_ch:
            try:
                import datetime
                now_str = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
                log_text = (
                    "🎯 <b>NEW USER VERIFIED</b>\n\n"
                    f"👤 <b>User:</b> {message.from_user.mention} (<code>{message.from_user.id}</code>)\n"
                    f"⏰ <b>Validity:</b> <code>{dur_str}</code>\n"
                    f"🔢 <b>Step:</b> <code>{slot_used}</code>\n"
                    f"📅 <b>Date:</b> <code>{now_str}</code>"
                )
                await client.send_message(int(log_ch), log_text)
            except Exception:
                pass

        success_text = (
            f"✅ <b>Hey {message.from_user.mention}, you are successfully verified!</b>\n\n"
            f"Now you have unlimited access for all files for <b>{dur_str}</b>."
        )
        if orig_payload:
            markup = InlineKeyboardMarkup([[InlineKeyboardButton("📥 GET YOUR FILE", url=f"https://t.me/{me.username}?start={orig_payload}")]])
            await message.reply(success_text, reply_markup=markup)
            message.command = ["/start", orig_payload]
            return await start(client, message)
        return await message.reply(success_text)

    try:
        decoded = base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("ascii")
        prefix, file_id = decoded.split("_", 1)
    except Exception:
        if "_" in data:
            prefix, file_id = data.split("_", 1)
        else:
            return await message.reply("❌ Invalid or expired link.")

    if prefix not in ("file", "filep") or not file_id:
        return await message.reply("❌ Invalid or expired file link.")

    v_text, access_markup = await access_verification(client, message.from_user.id, data)
    if access_markup:
        return await message.reply(v_text, reply_markup=access_markup, disable_web_page_preview=True)

    if await send_fsub_prompt(client, message, data):
        return

    try:
        await deliver_file(client, message.from_user.id, file_id, protected=prefix == "filep")
    except Exception as e:
        await message.reply(f"❌ Unable to deliver file: <code>{e}</code>")


async def help_command(client, message):
    text = (
        "📚 <b>ASH FILE STORE — HELP</b>\n\n"
        "👤 <b>User Commands</b>\n"
        "• /start — Check bot / open file link\n"
        "• /help — Open this help\n"
        "• /getlink — Create a single shareable file link\n"
        "• /batch — Store multiple messages from a channel\n"
        "• /custom_batch — Create custom batch links\n"
        "• /special_link — Create a special link\n"
        "• /universal_link — Create a universal link\n"
        "• /shortener — Shortener settings\n"
        "• /settings — Customize bot\n"
        "• /api KEY — Set shortener API\n"
        "• /base_site SITE — Set shortener site\n"
        "• /clone — Create your own clone\n\n"
        "👑 <b>Owner / Moderator</b>\n"
        "• /admin • /stats • /broadcast\n"
        "• /ban • /unban • /force_sub\n"
        "• /caption • /button • /protect\n"
        "• /auto_delete • /no_forward • /moderator\n"
        "• /access_token • /transfer_db • /deactivate\n"
        "• /mode • /restart • /delete • /start_msg\n\n"
        "⚙️ Owner features are also available from <b>Settings → My Clone Bot</b>."
    )
    await message.reply(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚙️ SETTINGS", callback_data="settings")]]))


async def genlink(client, message):
    if not is_owner_or_mod(client,message.from_user.id) and bot_record(client).get("mode","private")=="private": return await message.reply("❌ Link generation is private. Only owner/moderators can use it.")
    replied=message.reply_to_message
    if not replied or not replied.media: return await message.reply("Reply to a video, audio or document and use <code>/link</code>.")
    media=getattr(replied,replied.media.value,None); file_id=getattr(media,"file_id",None)
    if not file_id: return await message.reply("❌ Supported media: video, audio or document.")
    rec=bot_record(client); protected=bool(rec.get("protect_content",False)) or bool(rec.get("no_forward",False)); username=(await client.get_me()).username; link=make_file_link(username,file_id,protected)
    await message.reply(f"🔗 <b>File Link:</b>\n{link}")


async def custom_batch(client,message): return await message.reply("Use /custom_batch or /batch.")
async def special_link(client,message): return await genlink(client,message)
async def universal_link(client,message): return await genlink(client,message)


async def api_handler(client,message):
    uid=owner_id(client) or message.from_user.id; user=await get_user(uid)
    if len(message.command)==1: return await message.reply(f"<b>Shortener API:</b> <code>{user.get('shortener_api') or 'Not set'}</code>\n<b>Base Site:</b> <code>{user.get('base_site') or 'Not set'}</code>")
    await update_user_info(uid,{"shortener_api":message.command[1].strip()}); await message.reply("✅ Shortener API updated successfully.")


async def base_site_handler(client,message):
    uid=owner_id(client) or message.from_user.id
    if len(message.command)==1:
        user=await get_user(uid); return await message.reply(f"<b>Current base site:</b> <code>{user.get('base_site') or 'Not set'}</code>")
    site=message.command[1].strip().replace("https://","").replace("http://","").rstrip("/")
    if site.lower()=="none": await update_user_info(uid,{"base_site":None}); return await message.reply("✅ Base site removed.")
    if not domain(site): return await message.reply("❌ Invalid domain.")
    await update_user_info(uid,{"base_site":site}); await message.reply("✅ Base site updated successfully.")


async def shortener(client, message):
    user_id = message.from_user.id
    user = await get_user(user_id)
    if not (user.get("base_site") and user.get("shortener_api")):
        rec = bot_record(client)
        if rec.get("base_site") and rec.get("shortener_api"):
            user = {"base_site": rec.get("base_site"), "shortener_api": rec.get("shortener_api")}
        else:
            return await message.reply(
                "<b>Link Shortener</b>\n\n"
                "To shorten your links using your preferred provider, make sure to connect it with me first.\n\n"
                "Use /settings to connect your shortener provider."
            )
    ans = await client.ask(message.chat.id, "Send your Link which you want to shorten", timeout=120)
    link = (ans.text or "").strip()
    if not link or link.startswith("/"):
        return await message.reply("❌ Invalid link or cancelled.")
    short_link = await get_short_link(user, link)
    if not short_link or short_link == link:
        return await message.reply("Something went wrong, please try later")
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔁 SHARE SHORTENED LINK ↗️", url=f"https://t.me/share/url?url={short_link}")]
    ])
    await message.reply(
        f"Here is your shortened link:\n\n{short_link}",
        reply_markup=markup,
        disable_web_page_preview=True
    )


async def id_command(client, message):
    uid = message.from_user.id
    return await message.reply(f"<code>{uid}</code>")


async def customize_command(client, message):
    from clone_plugins.clone_settings_ui import is_bot_owner, has_permission
    uid = message.from_user.id
    if not (is_bot_owner(client, uid) or has_permission(client, uid, "settings")):
        return await message.reply("❌ Only owner and authorized admins can customize this bot.")
    markup = InlineKeyboardMarkup([[InlineKeyboardButton("🤖 CUSTOMIZE YOUR BOT SETTINGS 🤖", callback_data="settings")]])
    return await message.reply("<b>YOU CAN CUSTOMISE YOUR BOT SETTINGS FROM BELOW BUTTON</b>", reply_markup=markup)


async def settings_command(client, message):
    from clone_plugins import clone_settings_ui as cset
    return await cset.settings(client, message)


async def callbacks(client, query):
    data = query.data
    if data == "close_data":
        return await query.message.delete()
    if data.startswith("verify:"):
        payload = data.split(":", 1)[1]
        markup = await force_markup(client, query.from_user.id, payload)
        if markup:
            return await query.answer("❌ Join all required channels first.", show_alert=True)
        await query.answer("✅ Verified!")
        try:
            await query.message.delete()
        except Exception:
            pass
        return await client.send_message(query.from_user.id, "<b>✅ Verification successful. Open your file link again.</b>")
    if data == "help":
        return await help_command(client, query.message)
    if data == "about":
        me = client.me or (await client.get_me())
        owner_id_val = owner_id(client) or query.from_user.id
        owner_name = "Ash"
        try:
            owner_user = await client.get_users(owner_id_val)
            owner_name = owner_user.first_name or "Owner"
        except Exception:
            pass
        about_text = script.CABOUT_TXT.format(
            me.first_name,
            BOT_USERNAME,
            "MD File Store Bot",
            owner_id_val,
            owner_name
        )
        markup = InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="start_back")]])
        if query.message.photo:
            return await query.message.edit_caption(caption=about_text, reply_markup=markup)
        return await query.message.edit_text(about_text, reply_markup=markup)
    if data == "start_back":
        me = client.me or (await client.get_me())
        buttons = [
            [InlineKeyboardButton("⚙️ SETTINGS", callback_data="settings"), InlineKeyboardButton("🤖 MY OWN BOT", url=f"https://t.me/{BOT_USERNAME}?start=clone")],
            [InlineKeyboardButton("💁 HELP", callback_data="help"), InlineKeyboardButton("ℹ️ ABOUT", callback_data="about")],
            [InlineKeyboardButton("📢 UPDATE CHANNEL", url=tg_link(UPDATE_CHANNEL, "MoviesGroupG3"))]
        ]
        caption = script.CLONE_START_TXT.format(query.from_user.mention, me.mention)
        if query.message.photo:
            return await query.message.edit_caption(caption=caption, reply_markup=InlineKeyboardMarkup(buttons))
        return await query.message.edit_text(caption, reply_markup=InlineKeyboardMarkup(buttons))
    if data.startswith("c_buy_prem") or data.startswith("c_prem_upi_view"):
        payload = data.split(":", 1)[1] if ":" in data else ""
        rec = bot_record(client)
        from settings_modules.premium_plan import handle_user_buy_premium_view
        return await handle_user_buy_premium_view(client, query, rec=rec, show_upi=data.startswith("c_prem_upi_view"), payload=payload)
    if data.startswith("c_prem_user_back"):
        payload = data.split(":", 1)[1] if ":" in data else ""
        try:
            await query.answer()
        except Exception:
            pass
        v_text, v_markup = await access_verification(client, query.from_user.id, payload)
        if v_text and v_markup:
            if query.message and query.message.photo:
                try:
                    await query.message.delete()
                except Exception:
                    pass
                return await client.send_message(query.from_user.id, v_text, reply_markup=v_markup, parse_mode=enums.ParseMode.HTML, disable_web_page_preview=True)
            elif query.message:
                try:
                    return await query.message.edit_text(v_text, reply_markup=v_markup, parse_mode=enums.ParseMode.HTML, disable_web_page_preview=True)
                except Exception:
                    pass
            return await client.send_message(query.from_user.id, v_text, reply_markup=v_markup, parse_mode=enums.ParseMode.HTML, disable_web_page_preview=True)
        # Fallback to start back
        if query.message and query.message.photo:
            try:
                await query.message.delete()
            except Exception:
                pass
            me = (await client.get_me()).mention
            buttons = [
                [InlineKeyboardButton("⚙️ SETTINGS", callback_data="settings"), InlineKeyboardButton("🤖 MY CLONE BOT", callback_data="my_clone")],
                [InlineKeyboardButton("💝 sᴜʙsᴄʀɪʙᴇ ᴍʏ ʏᴏᴜᴛᴜʙᴇ ᴄʜᴀɴɴᴇʟ", url="https://www.youtube.com/@tech_as_0")],
                [InlineKeyboardButton("ℹ️ ʜᴇʟᴘ", callback_data="help"), InlineKeyboardButton("😊 ᴀʙᴏᴜᴛ", callback_data="about")]
            ]
            return await client.send_message(
                chat_id=query.from_user.id,
                text=script.START_TXT.format(query.from_user.mention, me),
                reply_markup=InlineKeyboardMarkup(buttons),
                disable_web_page_preview=True
            )
        return await callbacks(client, type("Q", (), {"data": "start_back", "from_user": query.from_user, "message": query.message, "answer": query.answer})())

    # Settings and clone management callbacks are handled by dedicated modules
    if data in (
        "settings", "settings_back", "log_channel", "set_log_channel", "delete_log_channel",
        "database_channel", "set_database_channel", "delete_database_channel",
        "admins_menu", "add_admin_prompt", "my_clone", "my_clones", "clone_my_bots", "create_clone_prompt", "clone_limit",
        "link_shortener", "add_shortener", "delete_shortener",
        "custom_caption", "caption_see", "caption_delete", "caption_edit",
        "custom_button", "button_add", "button_delete", "protect_menu", "protect_toggle", "protect_on", "protect_off"
    ) or data.startswith(("admin_info:", "adm_tgl:", "adm_trans:", "adm_rem:", "clone_", "cset_", "manage_clone:", "cm:", "cad:", "cmdelete:")):
        return
    try:
        await query.answer()
    except Exception:
        pass


async def clone_command(client, message):
    text = (
        "👑 <b>CLONE BOT CREATOR</b>\n\n"
        "<i>To create your own clone bot or manage your existing bots, please use our Master Parent Bot.</i>"
    )
    return await message.reply(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🤖 OPEN MASTER BOT ↗", url=f"https://t.me/{BOT_USERNAME}?start=clone")]]))


def register(client):
    private=filters.private
    client.add_handler(MessageHandler(start,filters.command("start")&private),group=0)
    client.add_handler(MessageHandler(help_command,filters.command("help")&private),group=0)
    client.add_handler(MessageHandler(id_command,filters.command("id")&private),group=0)
    client.add_handler(MessageHandler(customize_command,filters.command("customize")&private),group=0)
    client.add_handler(MessageHandler(clone_command,filters.command("clone")&private),group=0)
    client.add_handler(MessageHandler(genlink,filters.command(["link","genlink"])&private),group=1)
    client.add_handler(MessageHandler(universal_link,filters.command("universal_link")&private),group=1)
    client.add_handler(MessageHandler(api_handler,filters.command("api")&private),group=1)
    client.add_handler(MessageHandler(base_site_handler,filters.command("base_site")&private),group=1)
    client.add_handler(MessageHandler(shortener,filters.command("shortener")&private),group=1)
    client.add_handler(MessageHandler(settings_command,filters.command("settings")&private),group=1)
    async def plan_cmd(c, m):
        from settings_modules.premium_plan import handle_user_buy_premium_view
        return await handle_user_buy_premium_view(c, m, rec=bot_record(c), show_upi=False)
    client.add_handler(MessageHandler(plan_cmd,filters.command(["plan", "premium", "buy_premium"])&private),group=1)
    client.add_handler(CallbackQueryHandler(callbacks,filters.regex(r"^(close_data|verify:.*|help|about|start_back|c_buy_prem(:.*)?|c_prem_upi_view(:.*)?|c_prem_user_back(:.*)?|settings|settings_back|log_channel|set_log_channel|delete_log_channel|database_channel|set_database_channel|delete_database_channel|admins_menu|add_admin_prompt|admin_info:\d+|adm_tgl:\d+:[a-z_]+|adm_trans:\d+|adm_rem:\d+|my_clone|google_backup|google_connect|link_shortener|add_shortener|delete_shortener|custom_caption|caption_see|caption_delete|caption_edit|custom_button|button_add|button_delete|protect_menu|protect_on|protect_off)$")),group=0)
    return client


# ---- VJ-style verify + bypass log patch (injected after base load) ----
import datetime as _dt
import time as _time

async def send_verify_log(client, user, log_type="verified", slot=1, validity=None, payload=None):
    """Send detailed verify/bypass log to verify_log_channel (VJ File Store style)."""
    rec = bot_record(client)
    if not rec:
        return
    log_ch = rec.get("verify_log_channel")
    if not log_ch:
        return
    try:
        ist = _dt.timezone(_dt.timedelta(hours=5, minutes=30))
        now_str = _dt.datetime.now(ist).strftime("%Y-%m-%d %H:%M:%S IST")
        u = user
        mention = getattr(u, "mention", None) or (getattr(u, "first_name", None) or "User")
        uid = getattr(u, "id", user) if not isinstance(user, int) else user
        first = getattr(u, "first_name", None) or "None"
        last = getattr(u, "last_name", None) or "None"
        uname = getattr(u, "username", None)
        uname_str = f"@{uname}" if uname else "None"
        if log_type == "bypass":
            log_text = (
                "🔓 <b>USER BYPASS KIYA</b>\n\n"
                "⚠️ <b>Isne bypass kiya</b> (Premium / No Verify)\n\n"
                f"👤 <b>Mention:</b> {mention}\n"
                f"🆔 <b>User ID:</b> <code>{uid}</code>\n"
                f"👤 <b>First Name:</b> {first}\n"
                f"👤 <b>Last Name:</b> {last}\n"
                f"📎 <b>Username:</b> {uname_str}\n"
                f"📅 <b>Date:</b> <code>{now_str}</code>"
            )
            if payload:
                log_text += f"\n🔗 <b>Payload:</b> <code>{str(payload)[:80]}</code>"
        else:
            log_text = (
                "🎯 <b>NEW USER VERIFIED</b>\n\n"
                f"👤 <b>Mention:</b> {mention}\n"
                f"🆔 <b>User ID:</b> <code>{uid}</code>\n"
                f"👤 <b>First Name:</b> {first}\n"
                f"👤 <b>Last Name:</b> {last}\n"
                f"📎 <b>Username:</b> {uname_str}\n"
                f"🔢 <b>Step / Slot:</b> <code>{slot}</code>\n"
            )
            if validity:
                log_text += f"⏰ <b>Validity:</b> <code>{validity}</code>\n"
            log_text += f"📅 <b>Date:</b> <code>{now_str}</code>"
            if payload:
                log_text += f"\n🔗 <b>Payload:</b> <code>{str(payload)[:80]}</code>"
        await client.send_message(int(log_ch), log_text)
    except Exception:
        pass

_orig_access_verification = access_verification

async def access_verification(client, user_id, original_payload=""):
    rec = bot_record(client)
    if not rec:
        return None, None

    # Collect active slots first (same as base)
    active_slots = []
    for s in (1, 2, 3):
        v_key = f"verify_{s}" if s > 1 else "verify_1"
        v_cfg = rec.get(v_key, {})
        site = v_cfg.get("shortner_site") or v_cfg.get("site") or rec.get("base_site")
        api = v_cfg.get("shortner_api") or v_cfg.get("api") or rec.get("shortener_api")
        if v_cfg.get("is_on") and site and api:
            active_slots.append((s, v_cfg, site, api))
    if not active_slots:
        if rec.get("verify_enabled") and rec.get("base_site") and rec.get("shortener_api"):
            active_slots.append((1, {
                "tutorial": rec.get("verify_tutorial"),
                "time": rec.get("verify_ttl", 480) // 60
            }, rec.get("base_site"), rec.get("shortener_api")))
    if not active_slots:
        return None, None

    # Premium bypass: log once/day when verify is ON
    if is_user_premium(user_id, rec):
        try:
            u_obj = await client.get_users(user_id)
        except Exception:
            class _U:
                pass
            u_obj = _U()
            u_obj.id = user_id
            u_obj.first_name = "User"
            u_obj.last_name = None
            u_obj.username = None
            u_obj.mention = f"<a href='tg://user?id={user_id}'>User</a>"
        try:
            ist = _dt.timezone(_dt.timedelta(hours=5, minutes=30))
            today = _dt.datetime.now(ist).strftime("%Y-%m-%d")
            if mongo_db is not None:
                already = mongo_db.bypass_logs.find_one({
                    "bot_id": int(client.me.id),
                    "user_id": int(user_id),
                    "date": today,
                })
                if not already:
                    mongo_db.bypass_logs.update_one(
                        {"bot_id": int(client.me.id), "user_id": int(user_id), "date": today},
                        {"$set": {"logged_at": int(_time.time())}},
                        upsert=True,
                    )
                    await send_verify_log(client, u_obj, log_type="bypass", payload=original_payload)
            else:
                await send_verify_log(client, u_obj, log_type="bypass", payload=original_payload)
        except Exception:
            try:
                await send_verify_log(client, u_obj, log_type="bypass", payload=original_payload)
            except Exception:
                pass
        return None, None

    return await _orig_access_verification(client, user_id, original_payload)

# Patch success log inside start() by wrapping the verify success block is hard;
# instead monkey-patch set_user_verified side-effect via a thin wrapper used only from start.
_orig_set_user_verified = set_user_verified

def set_user_verified(user_id, bot_id=0, duration_minutes=1440, slot=1, _log_user=None, _log_client=None, _payload=None):
    _orig_set_user_verified(user_id, bot_id=bot_id, duration_minutes=duration_minutes, slot=slot)
    # Logging is done from patched start path below when possible

_orig_start = start

async def start(client, message):
    # Intercept verify_* success path for detailed log
    if len(getattr(message, "command", []) or []) == 2:
        data = message.command[1]
        if data.startswith("verify_") or data.startswith("verify-"):
            me = client.me or (await client.get_me())
            token_str = data.split("_", 1)[1] if data.startswith("verify_") else data.split("-", 1)[1]
            from clone_plugins.users_api import consume_verify_token, format_time_minutes
            orig_payload, slot_used = consume_verify_token(token_str, message.from_user.id, me.id)
            if orig_payload is None and mongo_db is not None:
                rec_t = mongo_db.access_tokens.find_one({
                    "bot_id": me.id, "token": token_str, "user_id": int(message.from_user.id)
                })
                if rec_t:
                    orig_payload = ""
                    slot_used = 1
            if orig_payload is not None:
                rec = bot_record(client)
                v_key = f"verify_{slot_used}" if slot_used > 1 else "verify_1"
                v_cfg = rec.get(v_key, {})
                time_mins = int(v_cfg.get("time", v_cfg.get("time_minutes", 1440)))
                _orig_set_user_verified(message.from_user.id, me.id, duration_minutes=time_mins, slot=slot_used)
                dur_str = format_time_minutes(time_mins)
                await send_verify_log(
                    client, message.from_user, log_type="verified",
                    slot=slot_used, validity=dur_str, payload=orig_payload or None,
                )
                success_text = (
                    f"✅ <b>Hey {message.from_user.mention}, you are successfully verified!</b>\n\n"
                    f"Now you have unlimited access for all files for <b>{dur_str}</b>."
                )
                if orig_payload:
                    markup = InlineKeyboardMarkup([[InlineKeyboardButton(
                        "📥 GET YOUR FILE",
                        url=f"https://t.me/{me.username}?start={orig_payload}"
                    )]])
                    await message.reply(success_text, reply_markup=markup)
                    message.command = ["/start", orig_payload]
                    return await _orig_start(client, message)
                return await message.reply(success_text)
            # invalid token falls through to original (which will also reject)
    return await _orig_start(client, message)
