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
    create_verify_token, consume_verify_token, format_time_minutes
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
        return None
    if is_user_premium(user_id, master_cfg):
        return None

    active_slot = None
    for s in (1, 2, 3):
        v_key = f"verify_{s}" if s > 1 else "verify_1"
        v_cfg = master_cfg.get(v_key, {})
        if v_cfg.get("is_on"):
            active_slot = v_cfg
            break

    if not active_slot:
        if VERIFY_MODE and master_cfg.get("base_site") and master_cfg.get("shortener_api"):
            active_slot = {
                "site": master_cfg.get("base_site"),
                "api": master_cfg.get("shortener_api"),
                "tutorial": VERIFY_TUTORIAL,
                "time_minutes": 480
            }
        elif VERIFY_MODE:
            if not await check_verification(client, user_id):
                btn = [[
                    InlineKeyboardButton("Verify", url=await get_token(client, user_id, f"https://telegram.me/{client.me.username}?start="))
                ],[
                    InlineKeyboardButton("How To Open Link & Verify", url=VERIFY_TUTORIAL)
                ]]
                if master_cfg.get("premium_is_on"):
                    btn.append([InlineKeyboardButton("💳 Buy Premium Plan", callback_data="m_buy_prem")])
                return InlineKeyboardMarkup(btn)
            return None
        else:
            return None

    if check_user_verified(user_id, client.me.id):
        return None

    site = active_slot.get("site") or master_cfg.get("base_site")
    api = active_slot.get("api") or master_cfg.get("shortener_api")
    tutorial = active_slot.get("tutorial") or VERIFY_TUTORIAL

    if not site or not api:
        return None

    token = create_verify_token(user_id, client.me.id, original_payload)
    raw_url = f"https://telegram.me/{client.me.username}?start=verify_{token}"
    short_url = await get_short_link({"base_site": site, "shortener_api": api}, raw_url)

    btn = [[InlineKeyboardButton("🔗 Click Here To Verify", url=short_url)]]
    if tutorial:
        btn.append([InlineKeyboardButton("🎬 How To Open Link & Verify", url=tutorial)])
    if master_cfg.get("premium_is_on"):
        btn.append([InlineKeyboardButton("💳 Buy Premium Plan", callback_data="m_buy_prem")])
    return InlineKeyboardMarkup(btn)


async def check_master_fsub(client, user_id, original_payload):
    master_cfg = await get_master_config(client)
    channels = master_cfg.get("force_channels", [])
    if not channels:
        return None
    missing = []
    for ch in channels:
        try:
            member = await client.get_chat_member(ch, user_id)
            if member.status in (enums.ChatMemberStatus.LEFT, enums.ChatMemberStatus.BANNED):
                missing.append(ch)
        except Exception:
            missing.append(ch)
    if not missing:
        return None
    buttons = []
    for ch in missing:
        try:
            chat = await client.get_chat(ch)
            link = chat.invite_link or f"https://t.me/{chat.username}"
            title = chat.title or str(ch)
            buttons.append([InlineKeyboardButton(f"📢 Join {title[:20]}", url=link)])
        except Exception:
            pass
    buttons.append([InlineKeyboardButton("🔄 Try Again", url=f"https://t.me/{client.me.username}?start={original_payload}")])
    return InlineKeyboardMarkup(buttons)


@Client.on_message(filters.command("start") & filters.incoming)
async def start(client, message):
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

    # 1. Custom batch routing
    if data.startswith("batch_"):
        from clone_plugins import custom_batch
        return await custom_batch.batch_start(client, message)

    # 2. Channel batch routing
    if data.startswith("cbatch_"):
        from clone_plugins import channel_batch
        return await channel_batch.batch_start_deliver(client, message)

    # 3. Special link routing
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
            orig_payload = await consume_verify_token(token, message.from_user.id, client.me.id)
            if orig_payload is not None:
                await set_user_verified(message.from_user.id, client.me.id, duration_minutes=time_mins)
                dur_str = format_time_minutes(time_mins)
                text = f"<b>Hey {message.from_user.mention}, You are successfully verified !\nNow you have unlimited access for all files for {dur_str}.</b>"
                markup = None
                if orig_payload:
                    markup = InlineKeyboardMarkup([[InlineKeyboardButton("📥 GET YOUR FILE", url=f"https://telegram.me/{username}?start={orig_payload}")]])
                return await message.reply_text(text=text, protect_content=True, reply_markup=markup)
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
                    text=f"<b>Hey {message.from_user.mention}, You are successfully verified !\nNow you have unlimited access for all files for {dur_str}.</b>",
                    protect_content=True
                )
                await verify_user(client, userid, token)
                await set_user_verified(message.from_user.id, client.me.id, duration_minutes=time_mins)
                return
            else:
                return await message.reply_text(text="<b>Invalid link or Expired link !</b>", protect_content=True)

    fsub_markup = await check_master_fsub(client, message.from_user.id, data)
    if fsub_markup:
        return await message.reply_text("<b>🔐 Please join the required channel(s) first to access files.</b>", reply_markup=fsub_markup)

    verify_markup = await check_master_verification(client, message.from_user.id, data)
    if verify_markup:
        return await message.reply_text("<b>You are not verified !\nKindly verify to continue !</b>", protect_content=True, reply_markup=verify_markup)

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
        ad_mins = int(master_cfg.get("auto_delete_minutes", AUTO_DELETE))
        if ad_enabled:
            k = await client.send_message(chat_id = message.from_user.id, text=f"<b><u>❗️❗️❗️IMPORTANT❗️️❗️❗️</u></b>\n\nThis Movie File/Video will be deleted in <b><u>{ad_mins} minutes</u> 🫥 <i></b>(Due to Copyright Issues)</i>.\n\n<b><i>Please forward this File/Video to your Saved Messages and Start Download there</b>")
            await asyncio.sleep(ad_mins * 60)
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
            try:
                del_msg = await msg.copy(chat_id=message.from_user.id, caption=f_caption, parse_mode=enums.ParseMode.HTML, reply_markup=reply_markup, protect_content=user_protect)
            except Exception:
                del_msg = await msg.copy(chat_id=message.from_user.id, caption=f_caption, reply_markup=reply_markup, protect_content=user_protect)
        else:
            del_msg = await msg.copy(chat_id=message.from_user.id, protect_content=user_protect)
        
        ad_enabled = master_cfg.get("auto_delete_enabled", AUTO_DELETE_MODE)
        ad_mins = int(master_cfg.get("auto_delete_minutes", AUTO_DELETE))
        if ad_enabled:
            k = await client.send_message(chat_id = message.from_user.id, text=f"<b><u>❗️❗️❗️IMPORTANT❗️️❗️❗️</u></b>\n\nThis Movie File/Video will be deleted in <b><u>{ad_mins} minutes</u> 🫥 <i></b>(Due to Copyright Issues)</i>.\n\n<b><i>Please forward this File/Video to your Saved Messages and Start Download there</b>")
            await asyncio.sleep(ad_mins * 60)
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
    from plugins.master_settings import send_settings_menu
    return await send_settings_menu(client, message)


@Client.on_message(filters.command("shortener") & filters.private)
async def shortener_cmd_handler(client, message):
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

# Don't Remove Credit Tg - @movies_1780
# Subscribe YouTube Channel For Amazing Bot https://www.youtube.com/@tech_as_0
# Ask Doubt on telegram @movies_1780

@Client.on_message(filters.command("base_site") & filters.private)
async def base_site_handler(client, m: Message):
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

    elif data in ("settings", "master_settings", "settings_back", "my_clone", "my_clones", "add_clone_prompt", "clone", "google_backup", "google_connect", "link_shortener", "delete_shortener", "add_shortener", "custom_caption", "custom_button", "protect_menu", "start_photo_menu") or data.startswith(("master_", "manage_clone:", "cm:", "cmdelete:", "protect_", "caption_", "button_", "start_pic_", "link_shortener", "delete_shortener", "log_channel", "database_channel")):
        from plugins.master_settings import callbacks as master_cb
        return await master_cb(client, query)

    elif data == "m_buy_prem":
        try:
            await query.answer()
        except Exception:
            pass
        master_cfg = await get_master_config(client)
        p_text = master_cfg.get("premium_plan_text") or "<b>Please contact the bot admin to purchase a premium plan.</b>"
        p_photo = master_cfg.get("premium_plan_photo")
        p_upi = master_cfg.get("premium_upi_id")
        extra = ""
        if p_upi:
            extra = f"\n\n💳 <b>Pay via UPI:</b> <code>{p_upi}</code>"
        full_text = f"💳 <b>PREMIUM PLAN DETAILS:</b>\n\n{p_text}{extra}"
        if p_photo:
            try:
                return await query.message.reply_photo(photo=p_photo, caption=full_text)
            except Exception:
                pass
        return await query.message.reply(full_text)

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
