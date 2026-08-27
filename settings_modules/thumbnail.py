# 🖼️ CUSTOM THUMBNAIL SETTINGS MODULE
import os
import asyncio
from pyrogram import enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from clone_plugins.sessions import start_user_session, is_user_session_active, clear_user_session

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

    back_cb = f"settings_back:{target_bid}" if target_bid else "settings_back"
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
        save_fn(custom_thumbnail=None, custom_thumb_path=None)
        r["custom_thumbnail"] = None
        r["custom_thumb_path"] = None
        clean_id = f"thumb_{user_id}_{target_bid or 'master'}"
        p = os.path.join(_thumbs_dir(), f"{clean_id}.jpg")
        if os.path.exists(p):
            try:
                os.remove(p)
            except Exception:
                pass
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
                photo_id = ans.photo.file_id
                p_prefix = f"thumb_{user_id}_{target_bid or 'master'}"
                local_p = await save_thumbnail_media(client, ans, user_id, prefix=p_prefix)

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
