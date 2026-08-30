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
    Deliver video or document with custom thumbnail applied.
    Uses Telegram Bot API HTTP directly first (instant server-side thumbnail attachment),
    then falls back to Pyrogram send_video / send_document.
    """
    thumb_path = await get_cached_thumb_path(client, thumb_val) if thumb_val else None
    
    # 1. Resolve Bot Token
    bot_token = None
    if getattr(client, "bot_token", None):
        bot_token = client.bot_token
    elif getattr(client, "token", None):
        bot_token = client.token
    elif getattr(client, "_token", None):
        bot_token = client._token
    elif getattr(client, "name", None) and ":" in str(client.name):
        bot_token = str(client.name)

    if not bot_token and mongo_db is not None:
        try:
            b_id = getattr(client, "me", None) and client.me.id
            if b_id:
                rec = mongo_db.bots.find_one({"bot_id": int(b_id)})
                if rec:
                    bot_token = rec.get("token") or rec.get("bot_token")
            if not bot_token and getattr(client, "me", None) and client.me.username:
                rec_u = mongo_db.bots.find_one({"username": client.me.username})
                if rec_u:
                    bot_token = rec_u.get("token") or rec_u.get("bot_token")
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

    # 3. Resolve direct Telegram photo file_id vs local thumbnail path
    direct_photo_id = None
    cands = thumb_val if isinstance(thumb_val, (list, tuple, set)) else [thumb_val]
    for c in cands:
        if isinstance(c, str) and c and "/" not in c and "\\" not in c:
            direct_photo_id = c
            break

    # 4. Deliver via Bot API HTTP (Instant Server-Side Thumbnail Attachment)
    if bot_token and (thumb_path or direct_photo_id):
        # A. Try sendVideo
        v_fields = {
            "chat_id": str(chat_id),
            "video": str(file_id),
            "supports_streaming": "true",
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

        v_files = None
        if thumb_path and os.path.exists(thumb_path) and os.path.getsize(thumb_path) > 0:
            v_fields["thumbnail"] = "attach://thumb"
            v_files = {"thumb": thumb_path}
        elif direct_photo_id:
            v_fields["thumbnail"] = str(direct_photo_id)

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
        }
        if caption:
            d_fields["caption"] = caption
            d_fields["parse_mode"] = "HTML"
        if markup_json:
            d_fields["reply_markup"] = markup_json
        if protect_content:
            d_fields["protect_content"] = "true"

        d_files = None
        if thumb_path and os.path.exists(thumb_path) and os.path.getsize(thumb_path) > 0:
            d_fields["thumbnail"] = "attach://thumb"
            d_files = {"thumb": thumb_path}
        elif direct_photo_id:
            d_fields["thumbnail"] = str(direct_photo_id)

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

    # 5. Fallback to Pyrogram client methods
    delivered = None
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
            if pyrogram.__version__.startswith("2"):
                kw["thumbnail"] = thumb_path
            else:
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
            if "thumbnail" in kw:
                kw.pop("thumbnail", None)
            try:
                delivered = await client.send_video(**kw)
            except Exception:
                pass

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
            if pyrogram.__version__.startswith("2"):
                kw_d["thumbnail"] = thumb_path
            else:
                kw_d["thumb"] = thumb_path
                
        if file_name:
            kw_d["file_name"] = file_name
        try:
            delivered = await client.send_document(**kw_d)
        except Exception:
            if "thumb" in kw_d:
                kw_d.pop("thumb", None)
            if "thumbnail" in kw_d:
                kw_d.pop("thumbnail", None)
            try:
                delivered = await client.send_document(**kw_d)
            except Exception:
                pass

    return delivered

