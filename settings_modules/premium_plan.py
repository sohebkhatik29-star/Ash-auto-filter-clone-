# 💸 PREMIUM PLAN SETTINGS MODULE
import os
import re
import time
import asyncio
from pyrogram import enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from clone_plugins.sessions import start_user_session, is_user_session_active, clear_user_session

def get_contact_info(rec: dict):
    """Return (clean_username, full_url, display_str)."""
    contact = rec.get("premium_screenshot_contact") or rec.get("owner_username") or "movies_1780"
    contact = str(contact).strip()
    if contact.startswith("http://") or contact.startswith("https://"):
        url = contact
        display = contact
        username = contact.rstrip("/").split("/")[-1].lstrip("@")
    else:
        username = contact.lstrip("@")
        url = f"https://t.me/{username}"
        display = f"@{username}"
    return username, url, display

def render_premium_plan_payload(rec: dict, user_mention: str = "User", show_upi: bool = False):
    """
    Generate (text, photo_id, reply_markup, has_spoiler, invert_caption)
    matching the exact VJ File Store style shown in user's video.
    """
    _, contact_url, display_contact = get_contact_info(rec)
    photo_id = rec.get("premium_plan_photo") or rec.get("premium_qr_pic")
    has_spoiler = bool(rec.get("premium_spoiler", False))
    invert_caption = bool(rec.get("premium_invert_cap", False))

    if show_upi:
        upi_id = rec.get("premium_upi_id") or "sonukhatik7193@oksbi"
        text = (
            "<b>PAYMENT METHOD: UPI ⚡</b>\n\n"
            "<b>YOU CAN PURCHASE PREMIUM THROUGH UPI, NET BANKING.</b>\n\n"
            f"💳 <b>UPI ID -</b> <code>{upi_id}</code>\n\n"
            "❗ <b>MUST SEND SCREENSHOT AFTER PAYMENT.</b>\n\n"
            "‼️ <b>AFTER SENDING SCREENSHOT PLEASE GIVE US SOMETIME TO ADD YOU IN PREMIUM LIST.</b>"
        )
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("• SEND PAYMENT SCREENSHOT •", url=contact_url)],
            [InlineKeyboardButton("‹ BACK", callback_data="c_buy_prem")]
        ])
    else:
        custom_txt = rec.get("premium_plan_text")
        if custom_txt:
            text = custom_txt.replace("{user_mention}", user_mention).replace("{user}", user_mention)
        else:
            text = (
                "⚡ <b>Buy Movies and Series Premium Now ⚡</b>\n\n"
                "<b>More Premium Plans</b>\n"
                "• 60 Rs - 1 month\n"
                "• 120 Rs - 3 Month\n"
                "• 240 Rs - 6 Months + 15 Days Free\n"
                "• 480 Rs - 1 Year + 1 Month\n"
                "• 1500 Rs - Lifetime\n\n"
                "⚠️ <b>Send Ss After Payment</b> ⚠️\n"
                f"<b>Contact :-</b> {display_contact}"
            )
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("💳 UPI", callback_data="c_prem_upi_view")],
            [InlineKeyboardButton("• SEND PAYMENT SCREENSHOT •", url=contact_url)],
            [InlineKeyboardButton("‹ BACK", callback_data="c_prem_user_back")]
        ])

    return text, photo_id, markup, has_spoiler, invert_caption

async def handle_user_buy_premium_view(client, query_or_msg, rec: dict = None, show_upi: bool = False):
    """Display user-facing Premium Plan or UPI details with QR photo and one-tap copy UPI ID."""
    if not rec:
        try:
            from clone_plugins.commands import bot_record
            rec = bot_record(client)
        except Exception:
            rec = {}

    # Merge with master_settings if any key is missing in clone doc
    try:
        from plugins.clone import mongo_db
        if mongo_db is not None:
            m_rec = mongo_db.master_settings.find_one({"type": "master_config"}) or mongo_db.master_settings.find_one({}) or {}
            if m_rec:
                merged = dict(m_rec)
                if rec:
                    for k, v in rec.items():
                        if v is not None and v != "":
                            merged[k] = v
                rec = merged
    except Exception:
        pass

    is_query = hasattr(query_or_msg, "message") and hasattr(query_or_msg, "answer")
    user = query_or_msg.from_user if is_query else getattr(query_or_msg, "from_user", None)
    user_mention = getattr(user, "mention", "User") if user else "User"
    user_id = user.id if user else 0

    if is_query:
        try:
            await query_or_msg.answer()
        except Exception:
            pass

    text, photo_id, markup, has_spoiler, invert_caption = render_premium_plan_payload(
        rec, user_mention=user_mention, show_upi=show_upi
    )

    # Resolve photo object (local file path or file_id)
    photo_target = rec.get("premium_qr_path") or rec.get("premium_plan_photo_path")
    if not photo_target or not (isinstance(photo_target, str) and os.path.exists(photo_target)):
        photo_target = photo_id

    if photo_target:
        try:
            from settings_modules.thumbnail import get_cached_thumb_path
            cached = await get_cached_thumb_path(client, photo_target)
            if cached and os.path.exists(cached):
                photo_target = cached
        except Exception:
            pass

    msg = query_or_msg.message if is_query else query_or_msg
    if not msg:
        return

    chat_id = msg.chat.id if hasattr(msg, "chat") and msg.chat else user_id

    # 1. If existing message already has photo, edit caption in place
    if is_query and msg and getattr(msg, "photo", None):
        try:
            return await msg.edit_caption(
                caption=text,
                reply_markup=markup,
                parse_mode=enums.ParseMode.HTML
            )
        except Exception:
            pass

    # 2. If photo is configured and old message is text or needs new photo
    if photo_target:
        if is_query and msg:
            try:
                await msg.delete()
            except Exception:
                pass
        try:
            return await client.send_photo(
                chat_id=chat_id,
                photo=photo_target,
                caption=text,
                reply_markup=markup,
                parse_mode=enums.ParseMode.HTML,
                has_spoiler=has_spoiler
            )
        except Exception:
            try:
                return await client.send_photo(
                    chat_id=chat_id,
                    photo=photo_target,
                    caption=text,
                    reply_markup=markup,
                    parse_mode=enums.ParseMode.HTML
                )
            except Exception:
                pass

    # 3. Fallback: If no photo or photo sending failed, edit or send text message
    if is_query and msg and not getattr(msg, "photo", None):
        try:
            return await msg.edit_text(
                text=text,
                reply_markup=markup,
                parse_mode=enums.ParseMode.HTML,
                disable_web_page_preview=True
            )
        except Exception:
            pass

    return await client.send_message(
        chat_id=chat_id,
        text=text,
        reply_markup=markup,
        parse_mode=enums.ParseMode.HTML,
        disable_web_page_preview=True
    )

# ----------------- ADMIN SETTINGS HANDLER ----------------- #

async def handle_premium_callbacks(client, query, data, user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn, target_bid=None):
    data_str = str(data or "")
    if not target_bid and ":" in data_str:
        try:
            target_bid = int(data_str.split(":", 1)[1])
        except Exception:
            pass

    def cb(name: str) -> str:
        return f"{name}:{target_bid}" if target_bid else name

    back_main = f"manage_clone:{target_bid}" if target_bid else "settings_back"

    async def clean_show(text, reply_markup=None):
        try:
            if query.message:
                return await query.message.edit_text(text, reply_markup=reply_markup, parse_mode=enums.ParseMode.HTML, disable_web_page_preview=True)
            else:
                return await client.send_message(user_id, text, reply_markup=reply_markup, parse_mode=enums.ParseMode.HTML, disable_web_page_preview=True)
        except Exception:
            return await client.send_message(user_id, text, reply_markup=reply_markup, parse_mode=enums.ParseMode.HTML, disable_web_page_preview=True)

    # 1. Main Premium Plan Menu
    if (
        data_str in ("master_premium_plan", "cset_premium_plan")
        or data_str.startswith(("master_premium_plan:", "cset_premium_plan:"))
    ):
        cancel_listeners_fn(user_id)
        prem_on = bool(r.get("premium_is_on", False) or r.get("premium_enabled", False))
        tgl_label = "🔓 PREMIUM IS ON ✅" if prem_on else "🔒 PREMIUM IS OFF ❌"

        text = (
            "💳 <b>PREMIUM PLAN:</b>\n\n"
            "❝ <b>PREMIUM PLAN: A PAID SUBSCRIPTION THAT GIVES USERS AD-FREE ACCESS, "
            "FASTER DOWNLOADS, AND EXCLUSIVE ENTRY TO RESTRICTED FILES OR GROUPS.</b> ❞"
        )
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("📝 PREMIUM PLAN MESSAGE", callback_data=cb("cset_prem_msg_menu"))],
            [InlineKeyboardButton("➕ ADD PREMIUM USER", callback_data=cb("cset_prem_add_user"))],
            [InlineKeyboardButton("➖ REMOVE PREMIUM USER", callback_data=cb("cset_prem_rem_user"))],
            [InlineKeyboardButton("👥 PREMIUM USERS LIST", callback_data=cb("cset_prem_list_users"))],
            [InlineKeyboardButton(tgl_label, callback_data=cb("cset_prem_tgl"))],
            [InlineKeyboardButton("‹ BACK", callback_data=back_main)]
        ])
        return await clean_show(text, markup)

    # 2. Toggle Premium ON / OFF
    if data_str.startswith("cset_prem_tgl"):
        cur_s = bool(r.get("premium_is_on", False) or r.get("premium_enabled", False))
        new_s = not cur_s
        save_fn(premium_is_on=new_s, premium_enabled=new_s)
        r["premium_is_on"] = new_s
        r["premium_enabled"] = new_s
        try:
            await query.answer(f"Premium is now {'ON ✅' if new_s else 'OFF ❌'}!")
        except Exception:
            pass
        return await handle_premium_callbacks(client, query, cb("master_premium_plan"), user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn, target_bid)

    # 3. Premium Plan Message Submenu
    if data_str.startswith("cset_prem_msg_menu"):
        cancel_listeners_fn(user_id)
        text = (
            "📝 <b>PREMIUM PLAN MESSAGE:</b>\n\n"
            "❝ <b>PREMIUM PLAN MESSAGE: WHEN USER CLICK ON BUY PREMIUM PLAN BUTTON THEN BOT REPLY PREMIUM PLAN MESSAGE. "
            "IN PREMIUM PLAN MESSAGE BOT OWNER CAN SET PREMIUM PLAN MESSAGE TEXT, PICTURE AND BUTTON.</b> ❞"
        )
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("PREMIUM PLAN TEXT", callback_data=cb("cset_prem_text_menu"))],
            [InlineKeyboardButton("PREMIUM PLAN QR PICTURE", callback_data=cb("cset_prem_pic_menu"))],
            [InlineKeyboardButton("PREMIUM PLAN UPI", callback_data=cb("cset_prem_upi_menu"))],
            [InlineKeyboardButton("SEND SCREENSHOT CONTACT", callback_data=cb("cset_prem_contact_menu"))],
            [InlineKeyboardButton("‹ BACK", callback_data=cb("master_premium_plan"))]
        ])
        return await clean_show(text, markup)

    # 4. Premium Plan Text Submenu
    if data_str.startswith("cset_prem_text_menu"):
        cancel_listeners_fn(user_id)
        p_text = r.get("premium_plan_text") or "{user_mention}\nBuy Movies and Series Premium Now ⚡"
        text = (
            "💳 <b>PREMIUM PLAN TEXT:</b>\n\n"
            f"<b>TEXT -</b> {p_text}\n\n"
            "<b>AVAILABLE FILLINGS:</b>\n\n"
            "<b>{user_mention}</b> : <b>USER - NAME</b>\n\n"
            "<b>YOU CAN USE <u>HTML STYLE FORMATTING</u> IN TEXT</b>"
        )
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("SET PREMIUM TEXT", callback_data=cb("cset_prem_set_txt"))],
            [InlineKeyboardButton("REMOVE PREMIUM TEXT", callback_data=cb("cset_prem_rem_txt"))],
            [InlineKeyboardButton("‹ BACK", callback_data=cb("cset_prem_msg_menu"))]
        ])
        return await clean_show(text, markup)

    # 4.1 Set Premium Text
    if data_str.startswith("cset_prem_set_txt"):
        cancel_listeners_fn(user_id)
        sess_token = start_user_session(user_id, f"prem_txt_{target_bid or 'master'}")
        try:
            await query.answer()
        except Exception:
            pass

        prompt_markup = InlineKeyboardMarkup([[InlineKeyboardButton("‹ CANCEL", callback_data=cb("cset_prem_text_menu"))]])
        prompt_msg = await clean_show(
            "<b>SEND ME A PREMIUM TEXT.</b>\n\n"
            "<b>AVAILABLE FILLINGS:</b>\n\n"
            "<b>{user_mention}</b> : <b>USER - NAME</b>\n\n"
            "<b>YOU CAN USE <u>HTML STYLE FORMATTING</u> IN TEXT</b>\n\n"
            "<code>/cancel</code> - <b>CANCEL THIS PROCESS.</b>",
            prompt_markup
        )

        async def _txt_worker():
            try:
                ans = await client.listen(chat_id=user_id, timeout=300)
            except Exception:
                clear_user_session(user_id)
                return
            if not is_user_session_active(user_id, sess_token):
                return

            t = (ans.text or ans.caption or "").strip()
            if t.lower() == "/cancel":
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
                return await handle_premium_callbacks(client, query, cb("cset_prem_text_menu"), user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn, target_bid)

            save_fn(premium_plan_text=t)
            r["premium_plan_text"] = t
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

            back_markup = InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data=cb("cset_prem_text_menu"))]])
            return await client.send_message(
                chat_id=user_id,
                text=f"<b>SUCCESSFULLY SET PREMIUM TEXT -</b>\n\n{t}",
                reply_markup=back_markup,
                parse_mode=enums.ParseMode.HTML
            )

        asyncio.create_task(_txt_worker())
        return

    # 4.2 Remove Premium Text
    if data_str.startswith("cset_prem_rem_txt"):
        save_fn(premium_plan_text=None)
        r["premium_plan_text"] = None
        try:
            await query.answer("Premium text removed successfully!")
        except Exception:
            pass
        return await handle_premium_callbacks(client, query, cb("cset_prem_text_menu"), user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn, target_bid)

    # 5. Premium Plan Picture Submenu
    if data_str.startswith("cset_prem_pic_menu"):
        cancel_listeners_fn(user_id)
        has_pic = bool(r.get("premium_plan_photo") or r.get("premium_qr_pic"))
        pic_status = "<b>ALREADY ADDED PICTURE...</b>" if has_pic else "<b>YOU DIDN'T ADD ANY PICTURE...</b>"
        is_spoiler = bool(r.get("premium_spoiler", False))
        is_invert = bool(r.get("premium_invert_cap", False))
        spoiler_txt = "✅" if is_spoiler else "❌"
        invert_txt = "✅" if is_invert else "❌"

        text = (
            "❝ <b>INVERT CAPTION : IF ON THEN CAPTION SHOW ABOVE PREMIUM MESSAGE PICTURE, "
            "IF OFF THEN CAPTION SHOWN BELOW PREMIUM MESSAGE PICTURE AS NORMAL.\n\n"
            "SPOILER ANIMATION : IF ON THEN PREMIUM MESSAGE PICTURE GET SPOILER ANIMATION, "
            "IF OFF THEN NO SPOILER ANIMATION.</b> ❞\n\n"
            f"{pic_status}\n\n"
            f"<b>SPOILER -</b> {spoiler_txt}\n"
            f"<b>INVERT CAPTION -</b> {invert_txt}"
        )
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("SET PREMIUM PIC", callback_data=cb("cset_prem_set_pic"))],
            [InlineKeyboardButton("DELETE PREMIUM PIC", callback_data=cb("cset_prem_del_pic"))],
            [InlineKeyboardButton("VIEW PREMIUM PIC", callback_data=cb("cset_prem_view_pic"))],
            [InlineKeyboardButton(f"SPOILER - {spoiler_txt}", callback_data=cb("cset_prem_tgl_spoiler"))],
            [InlineKeyboardButton(f"INVERT CAPTION - {invert_txt}", callback_data=cb("cset_prem_tgl_invert"))],
            [InlineKeyboardButton("‹ BACK", callback_data=cb("cset_prem_msg_menu"))]
        ])
        return await clean_show(text, markup)

    # 5.1 Set Picture
    if data_str.startswith("cset_prem_set_pic"):
        cancel_listeners_fn(user_id)
        sess_token = start_user_session(user_id, f"prem_pic_{target_bid or 'master'}")
        try:
            await query.answer()
        except Exception:
            pass

        prompt_markup = InlineKeyboardMarkup([[InlineKeyboardButton("‹ CANCEL", callback_data=cb("cset_prem_pic_menu"))]])
        prompt_msg = await clean_show(
            "<b>SEND ME A PICTURE.</b>\n\n"
            "<code>/cancel</code> - <b>CANCEL THIS PROCESS.</b>",
            prompt_markup
        )

        async def _pic_worker():
            try:
                ans = await client.listen(chat_id=user_id, timeout=300)
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
                return await handle_premium_callbacks(client, query, cb("cset_prem_pic_menu"), user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn, target_bid)

            if ans.photo:
                photo_id = ans.photo.file_id
                from settings_modules.thumbnail import save_thumbnail_media
                local_path = await save_thumbnail_media(client, ans, user_id, prefix=f"prem_qr_{target_bid or 'master'}")
                upd = {
                    "premium_plan_photo": photo_id,
                    "premium_qr_pic": photo_id
                }
                if local_path:
                    upd["premium_qr_path"] = local_path
                    upd["premium_plan_photo_path"] = local_path
                save_fn(**upd)
                r.update(upd)
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

                back_markup = InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data=cb("cset_prem_pic_menu"))]])
                photo_to_send = local_path or photo_id
                return await client.send_photo(
                    chat_id=user_id,
                    photo=photo_to_send,
                    caption="<b>SUCCESSFULLY PICTURE SET</b> ✅",
                    reply_markup=back_markup,
                    parse_mode=enums.ParseMode.HTML
                )
            else:
                try:
                    await ans.reply("⚠️ <b>Please send a valid photo picture.</b>")
                except Exception:
                    pass
                clear_user_session(user_id)
                return await handle_premium_callbacks(client, query, cb("cset_prem_pic_menu"), user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn, target_bid)

        asyncio.create_task(_pic_worker())
        return

    # 5.2 Delete Picture
    if data_str.startswith("cset_prem_del_pic"):
        save_fn(premium_plan_photo=None, premium_qr_pic=None, premium_qr_path=None, premium_plan_photo_path=None)
        r["premium_plan_photo"] = None
        r["premium_qr_pic"] = None
        r["premium_qr_path"] = None
        r["premium_plan_photo_path"] = None
        try:
            await query.answer("Picture deleted successfully!")
        except Exception:
            pass
        return await handle_premium_callbacks(client, query, cb("cset_prem_pic_menu"), user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn, target_bid)

    # 5.3 View Picture
    if data_str.startswith("cset_prem_view_pic"):
        photo_id = r.get("premium_plan_photo") or r.get("premium_qr_pic")
        if photo_id:
            try:
                back_markup = InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data=cb("cset_prem_pic_menu"))]])
                await client.send_photo(
                    chat_id=user_id,
                    photo=photo_id,
                    caption="🖼️ <b>YOUR CURRENT PREMIUM QR/PICTURE</b>",
                    reply_markup=back_markup,
                    parse_mode=enums.ParseMode.HTML
                )
                if query.message:
                    try:
                        await query.message.delete()
                    except Exception:
                        pass
                return
            except Exception:
                pass
        try:
            await query.answer("You haven't set any premium photo yet!", show_alert=True)
        except Exception:
            pass
        return await handle_premium_callbacks(client, query, cb("cset_prem_pic_menu"), user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn, target_bid)

    # 5.4 Toggle Spoiler & Invert Caption
    if data_str.startswith("cset_prem_tgl_spoiler"):
        new_sp = not bool(r.get("premium_spoiler", False))
        save_fn(premium_spoiler=new_sp)
        r["premium_spoiler"] = new_sp
        try:
            await query.answer(f"Spoiler: {'ON ✅' if new_sp else 'OFF ❌'}")
        except Exception:
            pass
        return await handle_premium_callbacks(client, query, cb("cset_prem_pic_menu"), user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn, target_bid)

    if data_str.startswith("cset_prem_tgl_invert"):
        new_inv = not bool(r.get("premium_invert_cap", False))
        save_fn(premium_invert_cap=new_inv)
        r["premium_invert_cap"] = new_inv
        try:
            await query.answer(f"Invert caption: {'ON ✅' if new_inv else 'OFF ❌'}")
        except Exception:
            pass
        return await handle_premium_callbacks(client, query, cb("cset_prem_pic_menu"), user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn, target_bid)

    # 6. Premium Plan UPI Submenu
    if data_str.startswith("cset_prem_upi_menu"):
        cancel_listeners_fn(user_id)
        upi_id = r.get("premium_upi_id") or "sonukhatik7193@oksbi"
        text = (
            "💳 <b>PREMIUM PLAN UPI:</b>\n\n"
            f"<b>UPI ID -</b> <code>{upi_id}</code>\n\n"
            "❝ <b>SET YOUR UPI ID (e.g. <code>sonukhatik7193@oksbi</code>). "
            "THIS UPI ID WILL BE DISPLAYED TO USERS IN THE UPI PAYMENT SCREEN WITH A ONE-TAP COPY OPTION.</b> ❞"
        )
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("SET UPI ID", callback_data=cb("cset_prem_set_upi"))],
            [InlineKeyboardButton("REMOVE UPI ID", callback_data=cb("cset_prem_rem_upi"))],
            [InlineKeyboardButton("‹ BACK", callback_data=cb("cset_prem_msg_menu"))]
        ])
        return await clean_show(text, markup)

    # 6.1 Set UPI ID
    if data_str.startswith("cset_prem_set_upi"):
        cancel_listeners_fn(user_id)
        sess_token = start_user_session(user_id, f"prem_upi_{target_bid or 'master'}")
        try:
            await query.answer()
        except Exception:
            pass

        prompt_markup = InlineKeyboardMarkup([[InlineKeyboardButton("‹ CANCEL", callback_data=cb("cset_prem_upi_menu"))]])
        prompt_msg = await clean_show(
            "<b>SEND ME YOUR UPI ID (e.g. <code>sonukhatik7193@oksbi</code>).</b>\n\n"
            "<code>/cancel</code> - <b>CANCEL THIS PROCESS.</b>",
            prompt_markup
        )

        async def _upi_worker():
            try:
                ans = await client.listen(chat_id=user_id, timeout=300)
            except Exception:
                clear_user_session(user_id)
                return
            if not is_user_session_active(user_id, sess_token):
                return

            t = (ans.text or ans.caption or "").strip()
            if t.lower() == "/cancel":
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
                return await handle_premium_callbacks(client, query, cb("cset_prem_upi_menu"), user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn, target_bid)

            save_fn(premium_upi_id=t)
            r["premium_upi_id"] = t
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

            back_markup = InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data=cb("cset_prem_upi_menu"))]])
            return await client.send_message(
                chat_id=user_id,
                text=f"<b>SUCCESSFULLY SET UPI ID -</b> <code>{t}</code> ✅",
                reply_markup=back_markup,
                parse_mode=enums.ParseMode.HTML
            )

        asyncio.create_task(_upi_worker())
        return

    # 6.2 Remove UPI ID
    if data_str.startswith("cset_prem_rem_upi"):
        save_fn(premium_upi_id=None)
        r["premium_upi_id"] = None
        try:
            await query.answer("UPI ID removed successfully!")
        except Exception:
            pass
        return await handle_premium_callbacks(client, query, cb("cset_prem_upi_menu"), user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn, target_bid)

    # 7. Send Screenshot Contact Submenu
    if data_str.startswith("cset_prem_contact_menu"):
        cancel_listeners_fn(user_id)
        _, _, display_c = get_contact_info(r)
        text = (
            "📨 <b>SEND SCREENSHOT CONTACT:</b>\n\n"
            f"<b>CONTACT -</b> <code>{display_c}</code>\n\n"
            "❝ <b>SET YOUR TELEGRAM USERNAME OR LINK (e.g. <code>@movies_1780</code> or <code>https://t.me/movies_1780</code>). "
            "WHEN USERS CLICK ON '* SEND PAYMENT SCREENSHOT *', IT WILL DIRECTLY OPEN THIS TELEGRAM ACCOUNT.</b> ❞"
        )
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("SET CONTACT USERNAME", callback_data=cb("cset_prem_set_contact"))],
            [InlineKeyboardButton("REMOVE CONTACT", callback_data=cb("cset_prem_rem_contact"))],
            [InlineKeyboardButton("‹ BACK", callback_data=cb("cset_prem_msg_menu"))]
        ])
        return await clean_show(text, markup)

    # 7.1 Set Contact Username / URL
    if data_str.startswith("cset_prem_set_contact"):
        cancel_listeners_fn(user_id)
        sess_token = start_user_session(user_id, f"prem_contact_{target_bid or 'master'}")
        try:
            await query.answer()
        except Exception:
            pass

        prompt_markup = InlineKeyboardMarkup([[InlineKeyboardButton("‹ CANCEL", callback_data=cb("cset_prem_contact_menu"))]])
        prompt_msg = await clean_show(
            "<b>SEND ME YOUR TELEGRAM USERNAME OR LINK (e.g. <code>@movies_1780</code>).</b>\n\n"
            "<code>/cancel</code> - <b>CANCEL THIS PROCESS.</b>",
            prompt_markup
        )

        async def _contact_worker():
            try:
                ans = await client.listen(chat_id=user_id, timeout=300)
            except Exception:
                clear_user_session(user_id)
                return
            if not is_user_session_active(user_id, sess_token):
                return

            t = (ans.text or ans.caption or "").strip()
            if t.lower() == "/cancel":
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
                return await handle_premium_callbacks(client, query, cb("cset_prem_contact_menu"), user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn, target_bid)

            clean_c = t.lstrip("@").strip()
            save_fn(premium_screenshot_contact=clean_c)
            r["premium_screenshot_contact"] = clean_c
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

            back_markup = InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data=cb("cset_prem_contact_menu"))]])
            return await client.send_message(
                chat_id=user_id,
                text=f"<b>SUCCESSFULLY SET CONTACT -</b> <code>@{clean_c}</code> ✅",
                reply_markup=back_markup,
                parse_mode=enums.ParseMode.HTML
            )

        asyncio.create_task(_contact_worker())
        return

    # 7.2 Remove Contact
    if data_str.startswith("cset_prem_rem_contact"):
        save_fn(premium_screenshot_contact=None)
        r["premium_screenshot_contact"] = None
        try:
            await query.answer("Contact reset to default!")
        except Exception:
            pass
        return await handle_premium_callbacks(client, query, cb("cset_prem_contact_menu"), user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn, target_bid)

    # 8. Add Premium User
    if data_str.startswith("cset_prem_add_user"):
        cancel_listeners_fn(user_id)
        sess_token = start_user_session(user_id, f"prem_add_{target_bid or 'master'}")
        try:
            await query.answer()
        except Exception:
            pass

        prompt_markup = InlineKeyboardMarkup([[InlineKeyboardButton("‹ CANCEL", callback_data=cb("master_premium_plan"))]])
        prompt_msg = await clean_show(
            "➕ <b>ADD PREMIUM USER:</b>\n\n"
            "<b>SEND USER ID AND DURATION IN DAYS (e.g. <code>123456789 30</code>):</b>\n\n"
            "<code>/cancel</code> - <b>CANCEL THIS PROCESS.</b>",
            prompt_markup
        )

        async def _add_u_worker():
            try:
                ans = await client.listen(chat_id=user_id, timeout=300)
            except Exception:
                clear_user_session(user_id)
                return
            if not is_user_session_active(user_id, sess_token):
                return

            t = (ans.text or ans.caption or "").strip()
            if t.lower() == "/cancel":
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
                return await handle_premium_callbacks(client, query, cb("master_premium_plan"), user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn, target_bid)

            parts = t.split()
            if len(parts) >= 1 and parts[0].isdigit():
                target_uid = int(parts[0])
                days = int(parts[1]) if len(parts) >= 2 and parts[1].isdigit() else 30
                now = int(time.time())
                exp_ts = now + (days * 86400)

                users_list = list(r.get("premium_users", []))
                users_list = [u for u in users_list if int(u.get("user_id", 0)) != target_uid]
                users_list.append({"user_id": target_uid, "expires_at": exp_ts, "added_at": now})

                save_fn(premium_users=users_list, premium_is_on=True, premium_enabled=True)
                r["premium_users"] = users_list
                r["premium_is_on"] = True
                r["premium_enabled"] = True
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

                back_markup = InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data=cb("master_premium_plan"))]])
                return await client.send_message(
                    chat_id=user_id,
                    text=f"✅ <b>User <code>{target_uid}</code> has been added to Premium for {days} days!</b>",
                    reply_markup=back_markup,
                    parse_mode=enums.ParseMode.HTML
                )
            else:
                try:
                    await ans.reply("⚠️ <b>Please send a valid format: <code>USER_ID DAYS</code></b>")
                except Exception:
                    pass
                clear_user_session(user_id)
                return await handle_premium_callbacks(client, query, cb("master_premium_plan"), user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn, target_bid)

        asyncio.create_task(_add_u_worker())
        return

    # 9. Remove Premium User
    if data_str.startswith("cset_prem_rem_user"):
        cancel_listeners_fn(user_id)
        sess_token = start_user_session(user_id, f"prem_rem_{target_bid or 'master'}")
        try:
            await query.answer()
        except Exception:
            pass

        prompt_markup = InlineKeyboardMarkup([[InlineKeyboardButton("‹ CANCEL", callback_data=cb("master_premium_plan"))]])
        prompt_msg = await clean_show(
            "➖ <b>REMOVE PREMIUM USER:</b>\n\n"
            "<b>SEND USER ID TO REMOVE FROM PREMIUM:</b>\n\n"
            "<code>/cancel</code> - <b>CANCEL THIS PROCESS.</b>",
            prompt_markup
        )

        async def _rem_u_worker():
            try:
                ans = await client.listen(chat_id=user_id, timeout=300)
            except Exception:
                clear_user_session(user_id)
                return
            if not is_user_session_active(user_id, sess_token):
                return

            t = (ans.text or ans.caption or "").strip()
            if t.lower() == "/cancel":
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
                return await handle_premium_callbacks(client, query, cb("master_premium_plan"), user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn, target_bid)

            if t.isdigit():
                target_uid = int(t)
                users_list = list(r.get("premium_users", []))
                users_list = [u for u in users_list if int(u.get("user_id", 0)) != target_uid]

                save_fn(premium_users=users_list)
                r["premium_users"] = users_list
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

                back_markup = InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data=cb("master_premium_plan"))]])
                return await client.send_message(
                    chat_id=user_id,
                    text=f"✅ <b>User <code>{target_uid}</code> removed from Premium!</b>",
                    reply_markup=back_markup,
                    parse_mode=enums.ParseMode.HTML
                )
            else:
                try:
                    await ans.reply("⚠️ <b>Please send a valid numeric USER ID.</b>")
                except Exception:
                    pass
                clear_user_session(user_id)
                return await handle_premium_callbacks(client, query, cb("master_premium_plan"), user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn, target_bid)

        asyncio.create_task(_rem_u_worker())
        return

    # 10. List Premium Users
    if data_str.startswith("cset_prem_list_users"):
        cancel_listeners_fn(user_id)
        users_list = list(r.get("premium_users", []))
        now = int(time.time())
        active_users = [u for u in users_list if int(u.get("expires_at", 0)) > now]

        if not active_users:
            text = (
                "👥 <b>PREMIUM USERS LIST:</b>\n\n"
                "<i>No active premium users found.</i>"
            )
        else:
            lines = ["👥 <b>PREMIUM USERS LIST:</b>\n", f"<b>Total Active Users:</b> <b>{len(active_users)}</b>\n"]
            for idx, u in enumerate(active_users, 1):
                uid = u.get("user_id")
                exp = int(u.get("expires_at", 0))
                days_left = max(0, (exp - now) // 86400)
                lines.append(f"{idx}. <code>{uid}</code> — <b>{days_left} Days Left</b>")
            text = "\n".join(lines)

        markup = InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data=cb("master_premium_plan"))]])
        return await clean_show(text, markup)
