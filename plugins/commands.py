# Don't Remove Credit Tg - @movies_1780
# Subscribe YouTube Channel For Amazing Bot https://www.youtube.com/@tech_as_0
# Ask Doubt on telegram @movies_1780

import os
import logging
import random
import asyncio
from validators import domain
from Script import script
from plugins.dbusers import db
from pyrogram import Client, filters, enums
from plugins.users_api import (
    get_user, update_user_info, format_caption, get_short_link,
    is_user_premium, check_user_verified, set_user_verified,
    create_verify_token, consume_verify_token, format_time_minutes,
    format_auto_delete_time, parse_auto_delete_time
)
from pyrogram.errors import ChatAdminRequired, FloodWait
from pyrogram.types import *
from utils import verify_user, check_token, check_verification, get_token
from config import *
import re
import json
import base64
from urllib.parse import quote_plus
from AshCore.utils.file_properties import get_name, get_hash, get_media_file_size
logger = logging.getLogger(__name__)

BATCH_FILES = {}

# Don't Remove Credit Tg - @movies_1780
# Subscribe YouTube Channel For Amazing Bot https://www.youtube.com/@tech_as_0
# Ask Doubt on telegram @movies_1780


def get_size(size):
    """Get size in readable format"""

    units = ["Bytes", "KB", "MB", "GB", "TB", "PB", "EB"]
    size = float(size)
    i = 0
    while size >= 1024.0 and i < len(units):
        i += 1
        size /= 1024.0
    return "%.2f %s" % (size, units[i])

def formate_file_name(file_name):
    chars = ["[", "]", "(", ")"]
    for c in chars:
        file_name.replace(c, "")
    file_name = '@movies_1780 ' + ' '.join(filter(lambda x: not x.startswith('http') and not x.startswith('@') and not x.startswith('www.'), file_name.split()))
    return file_name

# Don't Remove Credit Tg - @movies_1780
# Subscribe YouTube Channel For Amazing Bot https://www.youtube.com/@tech_as_0
# Ask Doubt on telegram @movies_1780


async def get_master_config(client):
    try:
        admin_id = int(ADMINS[0])
        u = await get_user(admin_id)
        if u: return u
    except Exception:
        pass
    return await get_user(client.me.id)


async def check_master_verification(client, user_id, original_payload):
    master_cfg = await get_master_config(client)
    if not master_cfg:
        return None, None
    if is_user_premium(user_id, master_cfg):
        return None, None

    active_slots = []
    for s in (1, 2, 3):
        v_key = f"verify_{s}" if s > 1 else "verify_1"
        v_cfg = master_cfg.get(v_key, {})
        site = v_cfg.get("shortner_site") or v_cfg.get("site") or master_cfg.get("base_site")
        api = v_cfg.get("shortner_api") or v_cfg.get("api") or master_cfg.get("shortener_api")
        if v_cfg.get("is_on") and site and api:
            active_slots.append((s, v_cfg, site, api))

    if not active_slots:
        if VERIFY_MODE and master_cfg.get("base_site") and master_cfg.get("shortener_api"):
            active_slots.append((1, {
                "tutorial": VERIFY_TUTORIAL,
                "time": 480
            }, master_cfg.get("base_site"), master_cfg.get("shortener_api")))

    if not active_slots:
        return None, None

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

    tutorial = pending_slot_cfg.get("tutorial") or VERIFY_TUTORIAL
    mins = int(pending_slot_cfg.get("time", pending_slot_cfg.get("time_minutes", 1440)))
    time_str = format_time_minutes(mins)

    token = create_verify_token(user_id, client.me.id, original_payload, slot=pending_slot_num)
    me = client.me or (await client.get_me())
    raw_url = f"https://telegram.me/{me.username}?start=verify_{token}"
    short_url = await get_short_link({"base_site": site_to_use, "shortener_api": api_to_use}, raw_url)

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
        f"<blockquote>IF YOU WANT DIRECT FILES WITHOUT ANY VERIFICATIONS THEN BUY BOT SUBSCRIPTION 😴\n\n"
        f"▶️ CLICK ON BUY PREMIUM BUTTON TO BUY SUBSCRIPTION</blockquote>"
    )

    btn = [[InlineKeyboardButton("🟢 VERIFY 🔗", url=short_url)]]
    if tutorial:
        btn.append([InlineKeyboardButton("🎬 HOW TO VERIFY ↗️", url=tutorial)])
    if master_cfg.get("premium_is_on") or master_cfg.get("premium_users") is not None:
        btn.append([InlineKeyboardButton("⭐ BUY PREMIUM - NO NEED TO VERIFY ⭐", callback_data="m_buy_prem")])

    return text, InlineKeyboardMarkup(btn)


async def check_master_fsub(client, user_id, original_payload):
    master_cfg = await get_master_config(client)
    if not master_cfg.get("fsub_enabled", False):
        if not master_cfg.get("force_channels") and not master_cfg.get("force_sub"):
            return None

    channels = master_cfg.get("fsub_channels", [])
    if not channels and master_cfg.get("force_channels"):
        channels = master_cfg.get("force_channels", [])
    if not channels and master_cfg.get("force_sub"):
        channels = [master_cfg.get("force_sub")]

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

        if not is_sub and mode == "request" and db is not None:
            try:
                from plugins.clone import mongo_db
                if mongo_db is not None:
                    req_doc = mongo_db.join_requests.find_one({"chat_id": chat_id, "user_id": user_id})
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
    # 1. Channel join buttons
    for item in missing:
        btn_title = f"Join {item['title']} ↗️" if len(item['title']) <= 25 else f"Join Channel {item['idx']} ↗️"
        buttons.append([InlineKeyboardButton(btn_title, url=item["link"])])

    # 2. Custom fake buttons if set
    fsub_btns = master_cfg.get("fsub_buttons", [])
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
        buttons.append([InlineKeyboardButton("🔄 TRY AGAIN 🔄", url=f"https://t.me/{me.username}?start={original_payload}")])
    else:
        buttons.append([InlineKeyboardButton("🔄 TRY AGAIN 🔄", callback_data=f"master_verify:{original_payload}")])

    return InlineKeyboardMarkup(buttons)


async def send_master_fsub_prompt(client, message, payload):
    markup = await check_master_fsub(client, message.from_user.id, payload)
    if not markup:
        return False
    master_cfg = await get_master_config(client)
    custom_text = master_cfg.get("fsub_text")
    if custom_text:
        text = custom_text.replace("{user_mention}", message.from_user.mention).replace("{mention}", message.from_user.mention)
    else:
        text = "👉 <b>PLEASE JOIN MY UPDATES CHANNEL AND THEN CLICK ON TRY AGAIN BUTTON</b> 👇"

    fsub_pic = master_cfg.get("fsub_pic")
    has_spoiler = bool(master_cfg.get("fsub_pic_spoiler", False))
    invert_cap = bool(master_cfg.get("fsub_pic_invert", False))

    if fsub_pic:
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

    await message.reply_text(text, reply_markup=markup, disable_web_page_preview=True)
    return True


@Client.on_message(filters.command("start") & filters.incoming)
async def start(client, message):
    me = client.me or (await client.get_me())
    if me and me.username and me.username.lower() != BOT_USERNAME.lower():
        return
    try:
        from plugins.master_settings import cancel_user_listeners
        cancel_user_listeners(client, message.chat.id, message.from_user.id)
    except Exception:
        pass
    username = client.me.username
    if not await db.is_user_exist(message.from_user.id):
        await db.add_user(message.from_user.id, message.from_user.first_name)
        await client.send_message(LOG_CHANNEL, script.LOG_TEXT.format(message.from_user.id, message.from_user.mention))
    if len(message.command) != 2:
        buttons = [
            [InlineKeyboardButton('⚙️ SETTINGS', callback_data='master_settings'), InlineKeyboardButton('🤖 MY CLONE BOT', callback_data='my_clones')],
            [InlineKeyboardButton('💝 sᴜʙsᴄʀɪʙᴇ ᴍʏ ʏᴏᴜᴛᴜʙᴇ ᴄʜᴀɴɴᴇʟ', url='https://www.youtube.com/@tech_as_0')],
            [InlineKeyboardButton('🔍 sᴜᴘᴘᴏʀᴛ ɢʀᴏᴜᴘ', url=tg_link(SUPPORT_GROUP, 'ash_movie_j')), InlineKeyboardButton('🤖 ᴜᴘᴅᴀᴛᴇ ᴄʜᴀɴɴᴇʟ', url=tg_link(UPDATE_CHANNEL, 'MoviesGroupG3'))],
            [InlineKeyboardButton('💁‍♀️ ʜᴇʟᴘ', callback_data='help'), InlineKeyboardButton('😊 ᴀʙᴏᴜᴛ', callback_data='about')]
        ]
        reply_markup = InlineKeyboardMarkup(buttons)
        me = client.me
        u_info = await get_user(message.from_user.id)
        start_photo = (u_info.get("start_pic") if u_info else None) or random.choice(PICS)
        try:
            await message.reply_photo(
                photo=start_photo,
                caption=script.START_TXT.format(message.from_user.mention, me.mention),
                reply_markup=reply_markup
            )
        except Exception:
            await message.reply_photo(
                photo=random.choice(PICS),
                caption=script.START_TXT.format(message.from_user.mention, me.mention),
                reply_markup=reply_markup
            )
        return

# Don't Remove Credit Tg - @movies_1780
# Subscribe YouTube Channel For Amazing Bot https://www.youtube.com/@tech_as_0
# Ask Doubt on telegram @movies_1780
    
    data = message.command[1]
    if data.lower() == "clone":
        from plugins.master_settings import send_manage_clones
        return await send_manage_clones(client, message)
    if data.lower() == "settings":
        from plugins.master_settings import send_settings_menu
        return await send_settings_menu(client, message)
    if data.startswith("csettings_") or data.startswith("cset_") or data.startswith("clone_manage_"):
        try:
            bid = int(data.split("_")[-1])
        except Exception:
            bid = None
        from plugins.master_settings import send_clone_settings_menu
        return await send_clone_settings_menu(client, message, bid)

    # 1. Custom batch routing
    if data.startswith("batch_"):
        from link_modules import custom_batch
        return await custom_batch.batch_start(client, message)

    # 2. Channel batch routing
    if data.startswith("cbatch_"):
        from link_modules import channel_batch
        return await channel_batch.batch_start_deliver(client, message)

    # 3. Special link routing
    if data.startswith("special_"):
        from link_modules import special_link
        return await special_link.open_special(client, message)

    # 4. Single message / file link routing
    if data.startswith("msg_") or data.startswith("msM_"):
        from link_modules import single_link
        return await single_link.open_single(client, message)

    # 5. Check if base64 encoded payload
    try:
        pad = (4 - len(data) % 4) % 4
        raw_dec = base64.urlsafe_b64decode(data + "=" * pad).decode("utf-8", errors="ignore")
        if raw_dec.startswith("batch_"):
            message.command[1] = raw_dec
            from link_modules import custom_batch
            return await custom_batch.batch_start(client, message)
        if raw_dec.startswith("cbatch_"):
            message.command[1] = raw_dec
            from link_modules import channel_batch
            return await channel_batch.batch_start_deliver(client, message)
        if raw_dec.startswith("special_"):
            message.command[1] = raw_dec
            from link_modules import special_link
            return await special_link.open_special(client, message)
        if raw_dec.startswith("msg_") or raw_dec.startswith("msM_"):
            from link_modules import single_link
            return await single_link.open_single(client, message)
        if raw_dec.startswith("file_") or raw_dec.startswith("filep_"):
            data = raw_dec
    except Exception:
        pass

    # 6. Check database tables directly by token
    try:
        from clone_plugins.database import mongo_db
        if mongo_db is not None:
            clean_tok = data.split("_", 1)[1] if "_" in data else data
            if mongo_db.share_links.find_one({"token": data}) or mongo_db.share_links.find_one({"token": clean_tok}):
                from link_modules import single_link
                return await single_link.open_single(client, message)
            if mongo_db.custom_batch_links.find_one({"token": data}) or mongo_db.custom_batch_links.find_one({"token": clean_tok}):
                message.command[1] = f"batch_{clean_tok}"
                from link_modules import custom_batch
                return await custom_batch.batch_start(client, message)
            if mongo_db.channel_batch_links.find_one({"token": data}) or mongo_db.channel_batch_links.find_one({"token": clean_tok}):
                message.command[1] = f"cbatch_{clean_tok}"
                from link_modules import channel_batch
                return await channel_batch.batch_start_deliver(client, message)
            if mongo_db.special_links.find_one({"token": data}) or mongo_db.special_links.find_one({"token": clean_tok}):
                message.command[1] = f"special_{clean_tok}"
                from link_modules import special_link
                return await special_link.open_special(client, message)
    except Exception:
        pass
    if data.startswith("verify_") or data.startswith("verify-"):
        master_cfg = await get_master_config(client)
        time_mins = 480
        for s in (1, 2, 3):
            v_key = f"verify_{s}" if s > 1 else "verify_1"
            v_cfg = master_cfg.get(v_key, {})
            if v_cfg.get("is_on"):
                time_mins = int(v_cfg.get("time_minutes", 480))
                break

        if data.startswith("verify_"):
            token = data.split("_", 1)[1]
            orig_payload, slot_used = consume_verify_token(token, message.from_user.id, client.me.id)
            if orig_payload is not None:
                v_key = f"verify_{slot_used}" if slot_used > 1 else "verify_1"
                v_cfg = master_cfg.get(v_key, {})
                time_mins = int(v_cfg.get("time", v_cfg.get("time_minutes", 1440)))
                set_user_verified(message.from_user.id, client.me.id, duration_minutes=time_mins, slot=slot_used)
                dur_str = format_time_minutes(time_mins)
                
                # Send log to verify_log_channel if configured
                log_ch = master_cfg.get("verify_log_channel")
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

                text = (
                    f"✅ <b>Hey {message.from_user.mention}, you are successfully verified!</b>\n\n"
                    f"Now you have unlimited access for all files for <b>{dur_str}</b>."
                )
                if orig_payload:
                    markup = InlineKeyboardMarkup([[InlineKeyboardButton("📥 GET YOUR FILE", url=f"https://telegram.me/{username}?start={orig_payload}")]])
                    await message.reply_text(text=text, protect_content=True, reply_markup=markup)
                    message.command = ["/start", orig_payload]
                    return await start(client, message)
                return await message.reply_text(text=text, protect_content=True)
            else:
                return await message.reply_text("<b>Invalid link or Expired link !</b>", protect_content=True)

        if data.split("-", 1)[0] == "verify":
            userid = data.split("-", 2)[1]
            token = data.split("-", 3)[2]
            if str(message.from_user.id) != str(userid):
                return await message.reply_text(text="<b>Invalid link or Expired link !</b>", protect_content=True)
            is_valid = await check_token(client, userid, token)
            if is_valid == True:
                dur_str = format_time_minutes(time_mins)
                await message.reply_text(
                    text=f"<b>Hey {message.from_user.mention}, you are successfully verified!\nNow you have unlimited access for all files for {dur_str}.</b>",
                    protect_content=True
                )
                await verify_user(client, userid, token)
                set_user_verified(message.from_user.id, client.me.id, duration_minutes=time_mins, slot=1)
                return
            else:
                return await message.reply_text(text="<b>Invalid link or Expired link !</b>", protect_content=True)

    if await send_master_fsub_prompt(client, message, data):
        return

    v_text, verify_markup = await check_master_verification(client, message.from_user.id, data)
    if verify_markup:
        return await message.reply_text(v_text or "<b>You are not verified !\nKindly verify to continue !</b>", protect_content=True, reply_markup=verify_markup, disable_web_page_preview=True)

    master_cfg = await get_master_config(client)

    if data.split("-", 1)[0] == "BATCH":
        sts = await message.reply("**🔺 ᴘʟᴇᴀsᴇ ᴡᴀɪᴛ**")
        file_id = data.split("-", 1)[1]
        msgs = BATCH_FILES.get(file_id)
        if not msgs:
            decode_file_id = base64.urlsafe_b64decode(file_id + "=" * (-len(file_id) % 4)).decode("ascii")
            msg = await client.get_messages(LOG_CHANNEL, int(decode_file_id))
            media = getattr(msg, msg.media.value)
            file_id = media.file_id
            file = await client.download_media(file_id)
            try: 
                with open(file) as file_data:
                    msgs=json.loads(file_data.read())
            except:
                await sts.edit("FAILED")
                return await client.send_message(LOG_CHANNEL, "UNABLE TO OPEN FILE.")
            os.remove(file)
            BATCH_FILES[file_id] = msgs
            
        filesarr = []
        for msg in msgs:
            channel_id = int(msg.get("channel_id"))
            msgid = msg.get("msg_id")
            info = await client.get_messages(channel_id, int(msgid))
            if info.media:
                file_type = info.media
                file = getattr(info, file_type.value)
                f_caption = getattr(info, 'caption', '')
                if f_caption:
                    f_caption = f"@movies_1780 {f_caption.html}"
                old_title = getattr(file, "file_name", "")
                title = formate_file_name(old_title)
                size=get_size(int(file.file_size))
                if BATCH_FILE_CAPTION:
                    try:
                        f_caption=BATCH_FILE_CAPTION.format(file_name= '' if title is None else title, file_size='' if size is None else size, file_caption='' if f_caption is None else f_caption)
                    except:
                        f_caption=f_caption
                if f_caption is None:
                    f_caption = f"@movies_1780 {title}"
                if STREAM_MODE == True:
                    if info.video or info.document:
                        log_msg = info
                        fileName = {quote_plus(get_name(log_msg))}
                        stream = f"{URL}watch/{str(log_msg.id)}/{quote_plus(get_name(log_msg))}?hash={get_hash(log_msg)}"
                        download = f"{URL}{str(log_msg.id)}/{quote_plus(get_name(log_msg))}?hash={get_hash(log_msg)}"
                        button = [[
                            InlineKeyboardButton("• ᴅᴏᴡɴʟᴏᴀᴅ •", url=download),
                            InlineKeyboardButton('• ᴡᴀᴛᴄʜ •', url=stream)
                        ],[
                            InlineKeyboardButton("• ᴡᴀᴛᴄʜ ɪɴ ᴡᴇʙ ᴀᴘᴘ •", web_app=WebAppInfo(url=stream))
                        ]]
                        reply_markup=InlineKeyboardMarkup(button)
                else:
                    reply_markup = None
                try:
                    msg = await info.copy(chat_id=message.from_user.id, caption=f_caption, protect_content=False, reply_markup=reply_markup)
                except FloodWait as e:
                    await asyncio.sleep(e.value)
                    msg = await info.copy(chat_id=message.from_user.id, caption=f_caption, protect_content=False, reply_markup=reply_markup)
                except:
                    continue
            else:
                try:
                    msg = await info.copy(chat_id=message.from_user.id, protect_content=False)
                except FloodWait as e:
                    await asyncio.sleep(e.value)
                    msg = await info.copy(chat_id=message.from_user.id, protect_content=False)
                except:
                    continue
            filesarr.append(msg)
            await asyncio.sleep(1) 
        await sts.delete()
        
        ad_enabled = master_cfg.get("auto_delete_enabled", AUTO_DELETE_MODE)
        ad_sec = int(master_cfg.get("auto_delete_time", (int(master_cfg.get("auto_delete_minutes", AUTO_DELETE)) * 60)))
        if ad_enabled:
            time_str = format_auto_delete_time(ad_sec)
            k = await client.send_message(chat_id = message.from_user.id, text=f"<b><u>❗️❗️❗️IMPORTANT❗️️❗️❗️</u></b>\n\nThis Movie File/Video will be deleted in <b><u>{time_str}</u> 🫥 <i></b>(Due to Copyright Issues)</i>.\n\n<b><i>Please forward this File/Video to your Saved Messages and Start Download there</b>")
            await asyncio.sleep(ad_sec)
            for x in filesarr:
                try:
                    await x.delete()
                except:
                    pass
            await k.edit_text("<b>Your All Files/Videos is successfully deleted!!!</b>")
        return

    try:
        pre, decode_file_id = ((base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))).decode("ascii")).split("_", 1)
    except Exception:
        if "_" in data:
            pre, decode_file_id = data.split("_", 1)
        else:
            return await message.reply_text("<b>Invalid or expired link!</b>")

    try:
        user_info = await get_user(message.from_user.id)
        msg = await client.get_messages(LOG_CHANNEL, int(decode_file_id))
        user_protect = bool(user_info.get("protect_content", False)) if user_info else bool(master_cfg.get("protect_content", False))
        if msg.media:
            media = getattr(msg, msg.media.value)
            title = formate_file_name(getattr(media, "file_name", None) or "Media")
            size = get_size(getattr(media, "file_size", 0))
            raw_caption = getattr(msg, "caption", "") or ""
            
            cust_cap = user_info.get("custom_caption") if user_info else master_cfg.get("custom_caption")
            invert_cap = bool(user_info.get("invert_caption", False)) if user_info else bool(master_cfg.get("invert_caption", False))
            spoiler_anim = bool(user_info.get("spoiler_animation", False)) if user_info else bool(master_cfg.get("spoiler_animation", False))
            caption_tmpl = cust_cap or CUSTOM_FILE_CAPTION or f"@movies_1780 <code>{title}</code>"
            f_caption = format_caption(caption_tmpl, media=media, source_msg=msg, default_caption=f"@movies_1780 <code>{title}</code>")

            button = []
            if STREAM_MODE == True:
                if msg.video or msg.document:
                    log_msg = msg
                    fileName = {quote_plus(get_name(log_msg))}
                    stream = f"{URL}watch/{str(log_msg.id)}/{quote_plus(get_name(log_msg))}?hash={get_hash(log_msg)}"
                    download = f"{URL}{str(log_msg.id)}/{quote_plus(get_name(log_msg))}?hash={get_hash(log_msg)}"
                    button.append([
                        InlineKeyboardButton("• ᴅᴏᴡɴʟᴏᴀᴅ •", url=download),
                        InlineKeyboardButton('• ᴡᴀᴛᴄʜ •', url=stream)
                    ])
                    button.append([
                        InlineKeyboardButton("• ᴡᴀᴛᴄʜ ɪɴ ᴡᴇʙ ᴀᴘᴘ •", web_app=WebAppInfo(url=stream))
                    ])
            
            # Custom buttons
            c_btns = (user_info.get("custom_buttons") if user_info and user_info.get("custom_buttons") else master_cfg.get("custom_buttons", []))
            for b in c_btns:
                if isinstance(b, dict) and b.get("text") and b.get("url"):
                    button.append([InlineKeyboardButton(b["text"], url=b["url"])])

            reply_markup = InlineKeyboardMarkup(button) if button else None
            del_msg = None
            attempts = []
            base_kw = {
                "chat_id": message.from_user.id,
                "caption": f_caption,
                "parse_mode": enums.ParseMode.HTML,
                "reply_markup": reply_markup,
                "protect_content": user_protect,
            }

            kw1 = dict(base_kw)
            if invert_cap:
                kw1["invert_media"] = True
            if spoiler_anim:
                kw1["has_spoiler"] = True
            attempts.append(kw1)

            if invert_cap or spoiler_anim:
                kw2 = dict(base_kw)
                if invert_cap:
                    kw2["show_caption_above_media"] = True
                if spoiler_anim:
                    kw2["has_spoiler"] = True
                attempts.append(kw2)

            if spoiler_anim:
                attempts.append({**base_kw, "has_spoiler": True})

            attempts.append(base_kw)
            fb_no_pm = dict(base_kw)
            fb_no_pm.pop("parse_mode", None)
            attempts.append(fb_no_pm)

            for attempt_kw in attempts:
                try:
                    del_msg = await msg.copy(**attempt_kw)
                    if del_msg:
                        break
                except Exception:
                    continue
        else:
            del_msg = await msg.copy(chat_id=message.from_user.id, protect_content=user_protect)
        
        ad_enabled = master_cfg.get("auto_delete_enabled", AUTO_DELETE_MODE)
        ad_sec = int(master_cfg.get("auto_delete_time", (int(master_cfg.get("auto_delete_minutes", AUTO_DELETE)) * 60)))
        if ad_enabled:
            time_str = format_auto_delete_time(ad_sec)
            k = await client.send_message(chat_id = message.from_user.id, text=f"<b><u>❗️❗️❗️IMPORTANT❗️️❗️❗️</u></b>\n\nThis Movie File/Video will be deleted in <b><u>{time_str}</u> 🫥 <i></b>(Due to Copyright Issues)</i>.\n\n<b><i>Please forward this File/Video to your Saved Messages and Start Download there</b>")
            await asyncio.sleep(ad_sec)
            try:
                await del_msg.delete()
            except:
                pass
            try:
                await k.edit_text("<b>Your File/Video is successfully deleted!!!</b>")
            except:
                pass
        return
    except Exception as e:
        logger.error(e)
        
# Don't Remove Credit Tg - @movies_1780
# Subscribe YouTube Channel For Amazing Bot https://www.youtube.com/@tech_as_0
# Ask Doubt on telegram @movies_1780

@Client.on_message(filters.command("help") & filters.private)
async def help_command_handler(client, message):
    me = client.me or (await client.get_me())
    if me and me.username and BOT_USERNAME and me.username.lower() != BOT_USERNAME.lower():
        return
    buttons = [[
        InlineKeyboardButton('Hᴏᴍᴇ', callback_data='start'),
        InlineKeyboardButton('🔒 Cʟᴏsᴇ', callback_data='close_data')
    ]]
    try:
        await message.reply_photo(
            photo=random.choice(PICS),
            caption=script.HELP_TXT,
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=enums.ParseMode.HTML
        )
    except Exception:
        await message.reply_text(
            text=script.HELP_TXT,
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=enums.ParseMode.HTML
        )


@Client.on_message(filters.command("settings") & filters.private)
async def settings_cmd_handler(client, message):
    me = client.me or (await client.get_me())
    if me and me.username and BOT_USERNAME and me.username.lower() != BOT_USERNAME.lower():
        return
    from plugins.master_settings import send_settings_menu
    return await send_settings_menu(client, message)


@Client.on_message(filters.command("shortener") & filters.private)
async def shortener_cmd_handler(client, message):
    me = client.me or (await client.get_me())
    if me and me.username and BOT_USERNAME and me.username.lower() != BOT_USERNAME.lower():
        return
    user_id = message.from_user.id
    user = await get_user(user_id)
    if not (user.get("base_site") and user.get("shortener_api")):
        return await message.reply(
            "<b>Link Shortener</b>\n\n"
            "To shorten your links using your preferred provider, make sure to connect it with me first.\n\n"
            "Use /settings to connect your shortener provider."
        )
    ans = await client.ask(message.chat.id, "Send your Link which you want to shorten", timeout=120)
    link = (ans.text or "").strip()
    if not link or link.startswith("/"):
        return await message.reply("❌ Invalid link or cancelled.")
    from clone_plugins.users_api import get_short_link
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


@Client.on_message(filters.command('api') & filters.private)
async def shortener_api_handler(client, m: Message):
    me = client.me or (await client.get_me())
    if me and me.username and BOT_USERNAME and me.username.lower() != BOT_USERNAME.lower():
        return
    user_id = m.from_user.id
    user = await get_user(user_id)
    cmd = m.command

    if len(cmd) == 1:
        s = script.SHORTENER_API_MESSAGE.format(base_site=user["base_site"], shortener_api=user["shortener_api"])
        return await m.reply(s)

    elif len(cmd) == 2:    
        api = cmd[1].strip()
        await update_user_info(user_id, {"shortener_api": api})
        await m.reply("<b>Shortener API updated successfully to</b> " + api)


@Client.on_message(filters.command("base_site") & filters.private)
async def base_site_handler(client, m: Message):
    me = client.me or (await client.get_me())
    if me and me.username and BOT_USERNAME and me.username.lower() != BOT_USERNAME.lower():
        return
    user_id = m.from_user.id
    user = await get_user(user_id)
    cmd = m.command
    text = f"`/base_site (base_site)`\n\n<b>Current base site: None\n\n EX:</b> `/base_site shortnerdomain.com`\n\nIf You Want To Remove Base Site Then Copy This And Send To Bot - `/base_site None`"
    if len(cmd) == 1:
        return await m.reply(text=text, disable_web_page_preview=True)
    elif len(cmd) == 2:
        base_site = cmd[1].strip()
        if base_site == None:
            await update_user_info(user_id, {"base_site": base_site})
            return await m.reply("<b>Base Site updated successfully</b>")
            
        if not domain(base_site):
            return await m.reply(text=text, disable_web_page_preview=True)
        await update_user_info(user_id, {"base_site": base_site})
        await m.reply("<b>Base Site updated successfully</b>")

# Don't Remove Credit Tg - @movies_1780
# Subscribe YouTube Channel For Amazing Bot https://www.youtube.com/@tech_as_0
# Ask Doubt on telegram @movies_1780

async def safe_edit_menu(query: CallbackQuery, text: str, reply_markup=None):
    try:
        await query.answer()
    except Exception:
        pass
    msg = query.message
    if not msg:
        return
    try:
        if getattr(msg, "photo", None) or getattr(msg, "media", None):
            await msg.edit_caption(caption=text, reply_markup=reply_markup, parse_mode=enums.ParseMode.HTML)
        else:
            await msg.edit_text(text=text, reply_markup=reply_markup, parse_mode=enums.ParseMode.HTML)
    except Exception:
        try:
            await msg.delete()
        except Exception:
            pass
        await msg.reply_text(text=text, reply_markup=reply_markup, parse_mode=enums.ParseMode.HTML)


@Client.on_callback_query()
async def cb_handler(client: Client, query: CallbackQuery):
    me = client.me or (await client.get_me())
    if me and me.username and BOT_USERNAME and me.username.lower() != BOT_USERNAME.lower():
        return
    try:
        from plugins.master_settings import cancel_user_listeners
        cancel_user_listeners(client, query.message.chat.id if query.message else query.from_user.id, query.from_user.id)
    except Exception:
        pass
    data = query.data or ""
    if data == "close_data":
        try:
            await query.answer()
            await query.message.delete()
        except Exception:
            pass
        return

    elif (
        data in ("settings", "master_settings", "settings_back", "my_clone", "my_clones", "clone_my_bots", "create_clone_prompt", "clone_limit", "add_clone_prompt", "clone", "google_backup", "google_connect", "link_shortener", "delete_shortener", "add_shortener", "custom_caption", "custom_thumbnail", "custom_button", "protect_menu", "start_photo_menu")
        or data.startswith((
            "master_", "manage_clone:", "cm:", "cad:", "cmdelete:", "protect_", "protect_menu", "caption_", "button_",
            "start_pic_", "link_shortener", "delete_shortener", "log_channel", "database_channel",
            "m_", "cset_", "cset_fsub", "custom_", "settings_back"
        ))
    ):
        from plugins.master_settings import callbacks as master_cb
        return await master_cb(client, query)

    elif data in ("m_buy_prem", "c_buy_prem", "c_prem_upi_view"):
        master_cfg = await get_master_config(client)
        from settings_modules.premium_plan import handle_user_buy_premium_view
        return await handle_user_buy_premium_view(client, query, rec=master_cfg, show_upi=(data == "c_prem_upi_view"))

    elif data == "c_prem_user_back":
        if query.message.photo:
            try:
                await query.message.delete()
            except Exception:
                pass
            buttons = [
                [InlineKeyboardButton("⚙️ SETTINGS", callback_data="master_settings"), InlineKeyboardButton("🤖 MY CLONE BOT", callback_data="my_clones")],
                [InlineKeyboardButton("💝 sᴜʙsᴄʀɪʙᴇ ᴍʏ ʏᴏᴜᴛᴜʙᴇ ᴄʜᴀɴɴᴇʟ", url="https://www.youtube.com/@tech_as_0")],
                [InlineKeyboardButton("ℹ️ ʜᴇʟᴘ", callback_data="help"), InlineKeyboardButton("😊 ᴀʙᴏᴜᴛ", callback_data="about")]
            ]
            me = (await client.get_me()).mention
            return await client.send_message(
                chat_id=query.from_user.id,
                text=script.START_TXT.format(query.from_user.mention, me),
                reply_markup=InlineKeyboardMarkup(buttons),
                disable_web_page_preview=True
            )
        else:
            return await callbacks(client, type("Q", (), {"data": "start", "from_user": query.from_user, "message": query.message, "answer": query.answer})())

    elif data == "about":
        buttons = [[
            InlineKeyboardButton("Hᴏᴍᴇ", callback_data="start"),
            InlineKeyboardButton("🔒 Cʟᴏsᴇ", callback_data="close_data")
        ]]
        me2 = (await client.get_me()).mention
        await safe_edit_menu(
            query,
            text=script.ABOUT_TXT.format(me2),
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    elif data == "start":
        buttons = [
            [InlineKeyboardButton("⚙️ SETTINGS", callback_data="master_settings"), InlineKeyboardButton("🤖 MY CLONE BOT", callback_data="my_clones")],
            [InlineKeyboardButton("💝 sᴜʙsᴄʀɪʙᴇ ᴍʏ ʏᴏᴜᴛᴜʙᴇ ᴄʜᴀɴɴᴇʟ", url="https://www.youtube.com/@tech_as_0")],
            [InlineKeyboardButton("🔍 sᴜᴘᴘᴏʀᴛ ɢʀᴏᴜᴘ", url=tg_link(SUPPORT_GROUP, "ash_movie_j")), InlineKeyboardButton("🤖 ᴜᴘᴅᴀᴛᴇ ᴄʜᴀɴɴᴇʟ", url=tg_link(UPDATE_CHANNEL, "MoviesGroupG3"))],
            [InlineKeyboardButton("💁‍♀️ ʜᴇʟᴘ", callback_data="help"), InlineKeyboardButton("😊 ᴀʙᴏᴜᴛ", callback_data="about")]
        ]
        me2 = (await client.get_me()).mention
        await safe_edit_menu(
            query,
            text=script.START_TXT.format(query.from_user.mention, me2),
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    elif data == "clone":
        buttons = [[
            InlineKeyboardButton("Hᴏᴍᴇ", callback_data="start"),
            InlineKeyboardButton("🔒 Cʟᴏsᴇ", callback_data="close_data")
        ]]
        await safe_edit_menu(
            query,
            text=script.CLONE_TXT.format(query.from_user.mention),
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    elif data == "help":
        buttons = [[
            InlineKeyboardButton("Hᴏᴍᴇ", callback_data="start"),
            InlineKeyboardButton("🔒 Cʟᴏsᴇ", callback_data="close_data")
        ]]
        await safe_edit_menu(
            query,
            text=script.HELP_TXT,
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    else:
        try:
            await query.answer()
        except Exception:
            pass
