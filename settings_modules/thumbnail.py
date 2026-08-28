# 🖼️ CUSTOM THUMBNAIL SETTINGS MODULE
import os
import json
import uuid
import mimetypes
import urllib.request
import urllib.parse
import asyncio
from pyrogram import enums, filters
from pyrogram.handlers import MessageHandler, CallbackQueryHandler
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from clone_plugins.sessions import start_user_session, is_user_session_active, clear_user_session
from plugins.clone import mongo_db

def _thumbs_dir() -> str:
    """Absolute cache directory for thumbnails."""
    base = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(__file__)), "cache", "thumbs"))
    os.makedirs(base, exist_ok=True)
    return base

def optimize_image(image_path: str, max_dim: int = 320):
    """Resize image to max 320x320 and save as optimized JPEG under 200KB. Always returns absolute path."""
    if not image_path:
        return image_path
    image_path = os.path.abspath(image_path)
    if not os.path.exists(image_path):
        return image_path
    try:
        from PIL import Image
        with Image.open(image_path) as img:
            img = img.convert("RGB")
            img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS if hasattr(Image, "Resampling") else Image.ANTIALIAS)
            img.save(image_path, "JPEG", quality=85, optimize=True)
    except Exception:
        pass
    return image_path

def _post_multipart_sync(url: str, fields: dict, files: dict = None):
    boundary = uuid.uuid4().hex
    body = bytearray()
    for name, value in fields.items():
        if value is None:
            continue
        body.extend(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode('utf-8'))
    if files:
        for name, filepath in files.items():
            if not filepath or not os.path.exists(filepath):
                continue
            try:
                with open(filepath, 'rb') as f:
                    file_bytes = f.read()
                mime = mimetypes.guess_type(filepath)[0] or 'image/jpeg'
                body.extend(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; filename="{name}.jpg"\r\nContent-Type: {mime}\r\n\r\n'.encode('utf-8'))
                body.extend(file_bytes)
                body.extend(b'\r\n')
            except Exception:
                pass
    body.extend(f'--{boundary}--\r\n'.encode('utf-8'))
    req = urllib.request.Request(
        url,
        data=bytes(body),
        headers={'Content-Type': f'multipart/form-data; boundary={boundary}'}
    )
    with urllib.request.urlopen(req, timeout=35) as resp:
        res_data = resp.read().decode('utf-8')
        return json.loads(res_data)

async def post_bot_api(token: str, method: str, fields: dict, files: dict = None):
    if not token:
        return None
    url = f"https://api.telegram.org/bot{token}/{method}"
    loop = asyncio.get_event_loop()
    try:
        return await loop.run_in_executor(None, lambda: _post_multipart_sync(url, fields, files))
    except Exception:
        return None

async def save_thumbnail_media(client, message_or_photo, user_id, prefix="thumb"):
    """Download photo from incoming Message/Photo and optimize for Telegram thumbnail."""
    clean_id = f"{prefix}_{user_id}"
    dest_path = os.path.join(_thumbs_dir(), f"{clean_id}.jpg")
    try:
        if os.path.exists(dest_path):
            try:
                os.remove(dest_path)
            except Exception:
                pass
        downloaded = await client.download_media(message_or_photo, file_name=dest_path)
        if downloaded and os.path.exists(downloaded):
            return optimize_image(downloaded)
    except Exception:
        pass
    return None

async def get_cached_thumb_path(client, thumb_val):
    """Return an absolute local file path ready for send_video / send_document thumb parameter."""
    if not thumb_val:
        return None
    # 1. Already a local file path
    if isinstance(thumb_val, str) and os.path.exists(thumb_val) and os.path.getsize(thumb_val) > 0:
        return optimize_image(os.path.abspath(thumb_val))

    clean_id = "".join(c for c in str(thumb_val)[-24:] if c.isalnum()) or "thumb"
    path = os.path.join(_thumbs_dir(), f"{clean_id}.jpg")
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return optimize_image(path)

    # 2. Download via current client (file_id of the photo)
    try:
        downloaded = await client.download_media(thumb_val, file_name=path)
        if downloaded and os.path.exists(downloaded) and os.path.getsize(downloaded) > 0:
            return optimize_image(downloaded)
    except Exception:
        pass

    # 3. Fallback to StreamBot if available
    try:
        from AshCore.bot import StreamBot
        downloaded = await StreamBot.download_media(thumb_val, file_name=path)
        if downloaded and os.path.exists(downloaded) and os.path.getsize(downloaded) > 0:
            return optimize_image(downloaded)
    except Exception:
        pass

    return None

async def deliver_media_with_custom_thumb(
    client,
    chat_id: int,
    file_id: str,
    media_type: str = "video",
    thumb_val = None,
    caption: str = None,
    reply_markup = None,
    protect_content: bool = False,
    invert_caption: bool = False,
    has_spoiler: bool = False,
    duration: int = None,
    width: int = None,
    height: int = None,
    file_name: str = None,
):
    """
    Deliver video or document with custom cover/thumbnail applied.
    Uses Telegram Bot API HTTP directly first (which server-side attaches thumbnail to file_id),
    then falls back to Pyrogram send_video / send_document.
    """
    thumb_path = await get_cached_thumb_path(client, thumb_val) if thumb_val else None
    
    # 1. Resolve Bot Token
    bot_token = None
    if getattr(client, "bot_token", None):
        bot_token = client.bot_token
    elif getattr(client, "_token", None):
        bot_token = client._token
    if not bot_token:
        try:
            b_id = getattr(client, "me", None) and client.me.id
            if b_id and mongo_db is not None:
                rec = mongo_db.bots.find_one({"bot_id": int(b_id)})
                if rec:
                    bot_token = rec.get("token") or rec.get("bot_token")
        except Exception:
            pass
    if not bot_token:
        try:
            from config import BOT_TOKEN
            bot_token = BOT_TOKEN
        except Exception:
            pass

    # 2. Build Reply Markup JSON
    markup_json = None
    if reply_markup:
        if isinstance(reply_markup, str):
            markup_json = reply_markup
        elif hasattr(reply_markup, "inline_keyboard"):
            try:
                kb_list = []
                for row in reply_markup.inline_keyboard:
                    r = []
                    for btn in row:
                        b = {"text": btn.text}
                        if getattr(btn, "url", None):
                            b["url"] = btn.url
                        elif getattr(btn, "callback_data", None):
                            b["callback_data"] = btn.callback_data
                        r.append(b)
                    kb_list.append(r)
                markup_json = json.dumps({"inline_keyboard": kb_list})
            except Exception:
                pass
        elif isinstance(reply_markup, dict):
            markup_json = json.dumps(reply_markup)

    # 3. Deliver via Bot API HTTP if thumb exists
    if bot_token and thumb_path and os.path.exists(thumb_path) and os.path.getsize(thumb_path) > 0:
        # A. Try sendVideo
        v_fields = {
            "chat_id": str(chat_id),
            "video": str(file_id),
            "supports_streaming": "true",
            "thumbnail": "attach://thumb",
            "cover": "attach://cover",
        }
        if caption:
            v_fields["caption"] = caption
            v_fields["parse_mode"] = "HTML"
        if markup_json:
            v_fields["reply_markup"] = markup_json
        if protect_content:
            v_fields["protect_content"] = "true"
        if invert_caption:
            v_fields["show_caption_above_media"] = "true"
        if has_spoiler:
            v_fields["has_spoiler"] = "true"
        if duration:
            v_fields["duration"] = str(duration)
        if width:
            v_fields["width"] = str(width)
        if height:
            v_fields["height"] = str(height)

        v_files = {
            "thumb": thumb_path,
            "cover": thumb_path,
        }
        try:
            res = await post_bot_api(bot_token, "sendVideo", v_fields, v_files)
            if isinstance(res, dict) and res.get("ok") and "result" in res:
                mid = res["result"]["message_id"]
                try:
                    return await client.get_messages(chat_id, mid)
                except Exception:
                    pass
        except Exception:
            pass

        # B. Try sendDocument
        d_fields = {
            "chat_id": str(chat_id),
            "document": str(file_id),
            "thumbnail": "attach://thumb",
        }
        if caption:
            d_fields["caption"] = caption
            d_fields["parse_mode"] = "HTML"
        if markup_json:
            d_fields["reply_markup"] = markup_json
        if protect_content:
            d_fields["protect_content"] = "true"
        d_files = {"thumb": thumb_path}
        try:
            res_d = await post_bot_api(bot_token, "sendDocument", d_fields, d_files)
            if isinstance(res_d, dict) and res_d.get("ok") and "result" in res_d:
                mid = res_d["result"]["message_id"]
                try:
                    return await client.get_messages(chat_id, mid)
                except Exception:
                    pass
        except Exception:
            pass

    # 4. Fallback to Pyrogram client methods
    delivered = None
    # Video attempt
    if media_type == "video" or not media_type or media_type == "document":
        kw = {
            "chat_id": chat_id,
            "video": file_id,
            "supports_streaming": True,
            "protect_content": protect_content,
            "reply_markup": reply_markup,
        }
        if caption:
            kw["caption"] = caption
            kw["parse_mode"] = enums.ParseMode.HTML
        if thumb_path and os.path.exists(thumb_path):
            kw["thumb"] = thumb_path
        if duration:
            kw["duration"] = duration
        if width:
            kw["width"] = width
        if height:
            kw["height"] = height
        if file_name:
            kw["file_name"] = file_name
        if invert_caption:
            kw["show_caption_above_media"] = True
        if has_spoiler:
            kw["has_spoiler"] = True
        try:
            delivered = await client.send_video(**kw)
        except Exception:
            if "thumb" in kw:
                kw.pop("thumb", None)
                try:
                    delivered = await client.send_video(**kw)
                except Exception:
                    pass

    # Document attempt
    if not delivered and (media_type == "document" or not media_type):
        kw_d = {
            "chat_id": chat_id,
            "document": file_id,
            "protect_content": protect_content,
            "reply_markup": reply_markup,
        }
        if caption:
            kw_d["caption"] = caption
            kw_d["parse_mode"] = enums.ParseMode.HTML
        if thumb_path and os.path.exists(thumb_path):
            kw_d["thumb"] = thumb_path
        if file_name:
            kw_d["file_name"] = file_name
        try:
            delivered = await client.send_document(**kw_d)
        except Exception:
            if "thumb" in kw_d:
                kw_d.pop("thumb", None)
                try:
                    delivered = await client.send_document(**kw_d)
                except Exception:
                    pass

    return delivered

async def save_permanent_thumbnail(client, user_id, message_or_photo):
    """Save permanent thumbnail in DB and local cache for client/user."""
    bot_id = client.me.id if getattr(client, "me", None) else "master"
    prefix = f"thumb_{user_id}_{bot_id}"
    local_path = await save_thumbnail_media(client, message_or_photo, user_id, prefix=prefix)
    
    photo_id = None
    if hasattr(message_or_photo, "photo") and message_or_photo.photo:
        photo_id = message_or_photo.photo.file_id
    elif hasattr(message_or_photo, "file_id"):
        photo_id = message_or_photo.file_id

    if mongo_db is not None:
        try:
            # Update clone bot doc if this is a clone bot
            if getattr(client, "me", None) and client.me.id:
                mongo_db.bots.update_one(
                    {"bot_id": client.me.id},
                    {"$set": {"custom_thumbnail": photo_id, "custom_thumb_path": local_path}},
                    upsert=False
                )
            # Also update user doc and master settings doc
            mongo_db.users.update_one(
                {"id": int(user_id)},
                {"$set": {"custom_thumbnail": photo_id, "custom_thumb_path": local_path}},
                upsert=True
            )
            from config import ADMINS
            if int(user_id) in [int(x) for x in ADMINS if str(x).strip().lstrip("-").isdigit()]:
                mongo_db.master_settings.update_one(
                    {"type": "master_config"},
                    {"$set": {"custom_thumbnail": photo_id, "custom_thumb_path": local_path}},
                    upsert=True
                )
        except Exception:
            pass

    return photo_id, local_path

async def delete_permanent_thumbnail(client, user_id):
    """Delete permanent thumbnail from DB and local cache."""
    bot_id = client.me.id if getattr(client, "me", None) else "master"
    clean_id = f"thumb_{user_id}_{bot_id}"
    p = os.path.join(_thumbs_dir(), f"{clean_id}.jpg")
    if os.path.exists(p):
        try:
            os.remove(p)
        except Exception:
            pass

    if mongo_db is not None:
        try:
            if getattr(client, "me", None) and client.me.id:
                mongo_db.bots.update_one(
                    {"bot_id": client.me.id},
                    {"$set": {"custom_thumbnail": None, "custom_thumb_path": None}}
                )
            mongo_db.users.update_one(
                {"id": int(user_id)},
                {"$set": {"custom_thumbnail": None, "custom_thumb_path": None}}
            )
            from config import ADMINS
            if int(user_id) in [int(x) for x in ADMINS if str(x).strip().lstrip("-").isdigit()]:
                mongo_db.master_settings.update_one(
                    {"type": "master_config"},
                    {"$set": {"custom_thumbnail": None, "custom_thumb_path": None}}
                )
        except Exception:
            pass

def thumbnail_menu_text(has_thumb: bool) -> str:
    status = "<b>ALREADY ADDED PICTURE...</b>" if has_thumb else "<b>YOU DIDN'T ADD ANY PICTURE...</b>"
    return (
        "🖼️ <b>CUSTOM THUMBNAIL:</b>\n\n"
        "❝ <b>CUSTOM THUMBNAIL: IT IS A COVER THUMBNAIL FOR VIDEO FILE WHICH BOT SEND TO USER, "
        "THE THUMB YOU SET IS APPLIED ON ALL OLD OR NEW FILE. AND IT SUPPORT ONLY IN VIDEO FILE NOT IN DOCUMENT FILE.</b> ❞\n\n"
        f"{status}"
    )

def thumbnail_markup(back_cb="settings_back", bid=None):
    cb_set = f"m_set_thumb:{bid}" if bid else "m_set_thumb"
    cb_del = f"m_del_thumb:{bid}" if bid else "m_del_thumb"
    cb_view = f"m_view_thumb:{bid}" if bid else "m_view_thumb"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("SET THUMBNAIL", callback_data=cb_set)],
        [InlineKeyboardButton("DELETE THUMBNAIL", callback_data=cb_del)],
        [InlineKeyboardButton("VIEW THUMBNAIL", callback_data=cb_view)],
        [InlineKeyboardButton("‹ BACK", callback_data=back_cb)]
    ])

async def handle_thumbnail_callbacks(client, query, data, user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn, target_bid=None):
    data_str = str(data or "")
    if not target_bid and ":" in data_str:
        try:
            target_bid = int(data_str.split(":", 1)[1])
        except Exception:
            pass

    back_cb = f"manage_clone:{target_bid}" if target_bid else "settings_back"
    main_cb = f"custom_thumbnail:{target_bid}" if target_bid else "custom_thumbnail"

    async def clean_show(text, reply_markup=None):
        try:
            if query.message:
                return await query.message.edit_text(text, reply_markup=reply_markup, parse_mode=enums.ParseMode.HTML)
            else:
                return await client.send_message(user_id, text, reply_markup=reply_markup, parse_mode=enums.ParseMode.HTML)
        except Exception:
            return await client.send_message(user_id, text, reply_markup=reply_markup, parse_mode=enums.ParseMode.HTML)

    # 1. Main Custom Thumbnail menu
    if data_str in ("custom_thumbnail", "master_custom_thumbnail", "cset_thumbnail") or data_str.startswith(("custom_thumbnail:", "cset_thumbnail:")):
        cancel_listeners_fn(user_id)
        has_thumb = bool(r.get("custom_thumbnail") or r.get("custom_thumb_path"))
        return await clean_show(thumbnail_menu_text(has_thumb), thumbnail_markup(back_cb, target_bid))

    # 2. View Thumbnail
    if data_str in ("m_view_thumb", "cset_view_thumb") or data_str.startswith(("m_view_thumb:", "cset_view_thumb:")):
        cancel_listeners_fn(user_id)
        cur_thumb = r.get("custom_thumbnail")
        cur_path = r.get("custom_thumb_path")
        
        back_markup = InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data=main_cb)]])
        
        # Try sending photo by file_id or local path
        sent = False
        if cur_thumb:
            try:
                await client.send_photo(chat_id=user_id, photo=cur_thumb, caption="🖼️ <b>YOUR CURRENT CUSTOM THUMBNAIL</b>", reply_markup=back_markup)
                sent = True
            except Exception:
                sent = False
        
        if not sent and cur_path and os.path.exists(cur_path):
            try:
                await client.send_photo(chat_id=user_id, photo=cur_path, caption="🖼️ <b>YOUR CURRENT CUSTOM THUMBNAIL</b>", reply_markup=back_markup)
                sent = True
            except Exception:
                sent = False

        if sent:
            try:
                await query.message.delete()
            except Exception:
                pass
            return

        try:
            await query.answer("You haven't set any custom thumbnail yet!", show_alert=True)
        except Exception:
            pass
        return await clean_show(thumbnail_menu_text(False), thumbnail_markup(back_cb, target_bid))

    # 3. Delete Thumbnail
    if data_str in ("m_del_thumb", "cset_del_thumb") or data_str.startswith(("m_del_thumb:", "cset_del_thumb:")):
        await delete_permanent_thumbnail(client, user_id)
        save_fn(custom_thumbnail=None, custom_thumb_path=None)
        r["custom_thumbnail"] = None
        r["custom_thumb_path"] = None
        try:
            await query.answer("Thumbnail deleted successfully!")
        except Exception:
            pass
        return await clean_show(thumbnail_menu_text(False), thumbnail_markup(back_cb, target_bid))

    # 4. Set Thumbnail Prompt
    if data_str in ("m_set_thumb", "cset_set_thumb") or data_str.startswith(("m_set_thumb:", "cset_set_thumb:")):
        cancel_listeners_fn(user_id)
        sess_token = start_user_session(user_id, f"set_thumb_{target_bid or 'master'}")

        try:
            await query.answer()
        except Exception:
            pass
        prompt_markup = InlineKeyboardMarkup([[InlineKeyboardButton("‹ CANCEL", callback_data=main_cb)]])
        prompt_msg = await clean_show(
            "<b>SEND ME A PICTURE.</b>\n\n"
            "<code>/cancel</code> - <b>CANCEL THIS PROCESS.</b>",
            prompt_markup
        )

        async def _thumb_worker():
            try:
                ans = await client.listen(chat_id=user_id, timeout=300)
            except asyncio.TimeoutError:
                if is_user_session_active(user_id, sess_token):
                    clear_user_session(user_id)
                    cur_t = r.get("custom_thumbnail") or r.get("custom_thumb_path")
                    await clean_show(thumbnail_menu_text(bool(cur_t)), thumbnail_markup(back_cb, target_bid))
                return
            except Exception:
                clear_user_session(user_id)
                return

            if not is_user_session_active(user_id, sess_token):
                return

            txt = (ans.text or ans.caption or "").strip()
            if txt.lower() == "/cancel":
                try:
                    await ans.delete()
                except Exception:
                    pass
                if prompt_msg:
                    try:
                        await prompt_msg.delete()
                    except Exception:
                        pass
                clear_user_session(user_id)
                cur_t = r.get("custom_thumbnail") or r.get("custom_thumb_path")
                await clean_show(thumbnail_menu_text(bool(cur_t)), thumbnail_markup(back_cb, target_bid))
                return

            if ans.photo:
                photo_id, local_p = await save_permanent_thumbnail(client, user_id, ans)
                save_fn(custom_thumbnail=photo_id, custom_thumb_path=local_p)
                r["custom_thumbnail"] = photo_id
                r["custom_thumb_path"] = local_p
                clear_user_session(user_id)

                if prompt_msg:
                    try:
                        await prompt_msg.delete()
                    except Exception:
                        pass
                try:
                    await ans.delete()
                except Exception:
                    pass

                back_markup = InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data=main_cb)]])
                return await client.send_photo(
                    chat_id=user_id,
                    photo=photo_id,
                    caption="<b>SUCCESSFULLY PICTURE SET</b> ✅",
                    reply_markup=back_markup,
                    parse_mode=enums.ParseMode.HTML
                )
            else:
                try:
                    await ans.reply("⚠️ <b>Please send a valid photo/picture.</b>")
                except Exception:
                    pass
                clear_user_session(user_id)
                cur_t = r.get("custom_thumbnail") or r.get("custom_thumb_path")
                await clean_show(thumbnail_menu_text(bool(cur_t)), thumbnail_markup(back_cb, target_bid))

        asyncio.create_task(_thumb_worker())
        return


# ========================================================================= #
# DIRECT PHOTO THUMBNAIL HANDLER (Video Cover Seva Style) & COMMANDS        #
# ========================================================================= #

async def handle_direct_photo_thumbnail(client, message):
    """When a user sends a photo directly in private chat, save as custom thumbnail."""
    if not message.from_user:
        return
    user_id = message.from_user.id

    # 1. Do NOT capture if user has an active prompt session (e.g. caption, QR, token verify, fsub, etc.)
    try:
        from clone_plugins.sessions import _USER_SESSIONS
        if int(user_id) in _USER_SESSIONS:
            return
    except Exception:
        pass

    # 2. Do NOT capture if client is listening for input from this user
    for attr in ("_listeners", "listeners"):
        try:
            d = getattr(client, attr, None)
            if isinstance(d, dict) and (user_id in d or message.chat.id in d):
                return
        except Exception:
            pass

    # 3. Do NOT capture if in getlink pending session or batch session
    try:
        from link_modules.single_link import is_single_link_pending
        if is_single_link_pending(client.me.id, user_id):
            return
    except Exception:
        pass
    try:
        from link_modules.channel_batch import is_channel_batch_active
        if is_channel_batch_active(client.me.id, user_id):
            return
    except Exception:
        pass
    try:
        from link_modules.special_link import is_special_link_active
        if is_special_link_active(client.me.id, user_id):
            return
    except Exception:
        pass

    # Save photo directly as user / bot permanent custom thumbnail
    photo_id, local_p = await save_permanent_thumbnail(client, user_id, message)
    
    markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🖼️ VIEW THUMBNAIL", callback_data="cset_view_thumb"),
            InlineKeyboardButton("🗑️ DELETE THUMBNAIL", callback_data="cset_del_thumb")
        ]
    ])

    await message.reply(
        "✅ <b>Thumbnail Updated!</b>\n\n"
        "<b>Now send any video to apply this cover.</b>",
        reply_markup=markup,
        parse_mode=enums.ParseMode.HTML
    )


async def thumb_commands_handler(client, message):
    """Handle /setthumb, /delthumb, /viewthumb commands in private chat."""
    if not message.from_user:
        return
    user_id = message.from_user.id
    cmd = (message.command[0] if message.command else "").lower()

    if cmd in ("setthumb", "set_thumb", "thumb"):
        replied = message.reply_to_message
        if replied and replied.photo:
            photo_id, local_p = await save_permanent_thumbnail(client, user_id, replied)
            markup = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("🖼️ VIEW THUMBNAIL", callback_data="cset_view_thumb"),
                    InlineKeyboardButton("🗑️ DELETE THUMBNAIL", callback_data="cset_del_thumb")
                ]
            ])
            return await message.reply(
                "✅ <b>Thumbnail Updated!</b>\n\n"
                "<b>Now send any video to apply this cover.</b>",
                reply_markup=markup,
                parse_mode=enums.ParseMode.HTML
            )
        else:
            sess_token = start_user_session(user_id, "cmd_set_thumb")
            prompt_msg = await message.reply(
                "🖼️ <b>Send me a picture to set as your custom thumbnail.</b>\n\n"
                "<code>/cancel</code> - <b>CANCEL THIS PROCESS.</b>",
                parse_mode=enums.ParseMode.HTML
            )
            try:
                ans = await client.listen(chat_id=user_id, timeout=120)
                if not is_user_session_active(user_id, sess_token):
                    return
                clear_user_session(user_id)
                txt = (ans.text or ans.caption or "").strip()
                if txt.lower() == "/cancel":
                    try: await ans.delete()
                    except Exception: pass
                    try: await prompt_msg.delete()
                    except Exception: pass
                    return await message.reply("❌ Cancelled.")
                if ans.photo:
                    photo_id, local_p = await save_permanent_thumbnail(client, user_id, ans)
                    markup = InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton("🖼️ VIEW THUMBNAIL", callback_data="cset_view_thumb"),
                            InlineKeyboardButton("🗑️ DELETE THUMBNAIL", callback_data="cset_del_thumb")
                        ]
                    ])
                    return await message.reply(
                        "✅ <b>Thumbnail Updated!</b>\n\n"
                        "<b>Now send any video to apply this cover.</b>",
                        reply_markup=markup,
                        parse_mode=enums.ParseMode.HTML
                    )
                else:
                    return await message.reply("⚠️ <b>Please send a valid photo picture.</b>")
            except Exception:
                clear_user_session(user_id)
                return

    if cmd in ("delthumb", "del_thumb", "removethumb"):
        await delete_permanent_thumbnail(client, user_id)
        return await message.reply("🗑️ <b>Custom Thumbnail Deleted Successfully!</b>", parse_mode=enums.ParseMode.HTML)

    if cmd in ("viewthumb", "view_thumb", "showthumb"):
        bot_id = client.me.id if getattr(client, "me", None) else "master"
        clean_id = f"thumb_{user_id}_{bot_id}"
        p = os.path.join(_thumbs_dir(), f"{clean_id}.jpg")
        
        doc = mongo_db.users.find_one({"id": int(user_id)}) if mongo_db is not None else None
        photo_id = doc.get("custom_thumbnail") if doc else None
        
        sent = False
        markup = InlineKeyboardMarkup([[InlineKeyboardButton("🗑️ DELETE THUMBNAIL", callback_data="cset_del_thumb")]])
        if photo_id:
            try:
                await message.reply_photo(photo=photo_id, caption="🖼️ <b>Your Current Custom Thumbnail</b>", reply_markup=markup)
                sent = True
            except Exception:
                sent = False
        if not sent and os.path.exists(p):
            try:
                await message.reply_photo(photo=p, caption="🖼️ <b>Your Current Custom Thumbnail</b>", reply_markup=markup)
                sent = True
            except Exception:
                sent = False
        if not sent:
            return await message.reply("⚠️ <b>You haven't set any custom thumbnail yet!</b>")
