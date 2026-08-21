# 📝 START MESSAGE SETTINGS MODULE
import asyncio
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from clone_plugins.sessions import start_user_session, is_user_session_active, clear_user_session

async def handle_start_message_callbacks(client, query, data, user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn):
    if data == "cset_start_msg_menu":
        text = (
            "📝 <b>START MESSAGE:</b>\n\n"
            "<b>START MESSAGE: WHEN USER GIVE START COMMAND OR START THE BOT THEN BOT REPLY START MESSAGE. IN START MESSAGE BOT OWNER CAN SET START MESSAGE TEXT, PICTURE AND BUTTON.</b>"
        )
        return await edit_or_reply_fn(
            query,
            text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("START TEXT", callback_data="cset_start_text")],
                [InlineKeyboardButton("START PICTURE", callback_data="cset_start_pic")],
                [InlineKeyboardButton("START BUTTON", callback_data="custom_button")],
                [InlineKeyboardButton("🪧 BACK", callback_data="clone_my_clone_info")]
            ])
        )

    if data == "cset_start_text":
        st_txt = r.get("start_text") or "Default start text"
        text = (
            "📝 <b>START TEXT:</b>\n\n"
            "<b>AVAILABLE FILLINGS:</b>\n"
            "{mention} - USER - NAME MENTION\n"
            "{bot_mention} - BOT - NAME MENTION\n\n"
            f"<b>TEXT -</b> <code>{st_txt}</code>"
        )
        return await edit_or_reply_fn(
            query,
            text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("SET TEXT", callback_data="cset_set_start_text"), InlineKeyboardButton("DEFAULT TEXT", callback_data="cset_def_start_text")],
                [InlineKeyboardButton("🪧 BACK", callback_data="cset_start_msg_menu")]
            ])
        )

    if data == "cset_set_start_text":
        cancel_listeners_fn(client, user_id, user_id)
        sess_token = start_user_session(user_id, "set_start_text")
        await query.answer()
        await edit_or_reply_fn(
            query,
            "<b>SEND ME A START TEXT.</b>\n\n<b>AVAILABLE FILLINGS:</b>\n{mention} - USER - NAME MENTION\n{bot_mention} - BOT - NAME MENTION\n\n/cancel - CANCEL THIS PROCESS.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🪧 BACK", callback_data="cset_start_text")]])
        )
        async def _stxt_worker():
            try:
                ans = await client.listen(chat_id=user_id, timeout=120)
            except Exception:
                await client.send_message(user_id, "❌ <b>Timeout. Process cancelled.</b>")
                clear_user_session(user_id)
                return
            if not is_user_session_active(user_id, sess_token):
                return
            t_val = (ans.text or "").strip()
            clear_user_session(user_id)
            if t_val == "/cancel":
                return await client.send_message(chat_id=user_id, text="❌ <b>Cancelled.</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🪧 BACK", callback_data="cset_start_text")]]) )
            save_fn(start_text=t_val)
            return await client.send_message(
                chat_id=user_id,
                text=f"<b>SUCCESSFULLY SET START TEXT -</b>\n\n{t_val}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🪧 BACK", callback_data="cset_start_text")]])
            )
        asyncio.create_task(_stxt_worker())
        return

    if data == "cset_def_start_text":
        save_fn(start_text=None)
        await query.answer("Reset to default start text!")
        return await edit_or_reply_fn(
            query,
            "<b>SUCCESSFULLY SET TO DEFAULT START TEXT.</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🪧 BACK", callback_data="cset_start_text")]])
        )

    if data == "cset_start_pic":
        pic = r.get("start_pic")
        spoiler = bool(r.get("start_pic_spoiler", False))
        spoiler_txt = "✅" if spoiler else "❌"
        has_pic_txt = "ALREADY ADDED PICTURE..." if pic else "YOU DIDN'T ADDED ANY PICTURE..."
        text = (
            "🖼️ <b>START PICTURE:</b>\n\n"
            f"<b>{has_pic_txt}</b>\n\n"
            f"<b>SPOILER EFFECT - {spoiler_txt}</b>"
        )
        return await edit_or_reply_fn(
            query,
            text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("SET PICTURE", callback_data="cset_set_start_pic")],
                [InlineKeyboardButton("DELETE PICTURE", callback_data="cset_del_start_pic")],
                [InlineKeyboardButton(f"SPOILER - {spoiler_txt}", callback_data="cset_tgl_start_spoiler")],
                [InlineKeyboardButton("🪧 BACK", callback_data="cset_start_msg_menu")]
            ])
        )

    if data == "cset_set_start_pic":
        cancel_listeners_fn(client, user_id, user_id)
        sess_token = start_user_session(user_id, "set_start_pic")
        await query.answer()
        await edit_or_reply_fn(
            query,
            "<b>SEND ME A PICTURE.</b>\n\n/cancel - CANCEL THIS PROCESS.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🪧 BACK", callback_data="cset_start_pic")]])
        )
        async def _spic_worker():
            try:
                ans = await client.listen(chat_id=user_id, timeout=120)
            except Exception:
                await client.send_message(user_id, "❌ <b>Timeout. Process cancelled.</b>")
                clear_user_session(user_id)
                return
            if not is_user_session_active(user_id, sess_token):
                return
            if not ans or ans.text == "/cancel" or not ans.photo:
                clear_user_session(user_id)
                return await client.send_message(chat_id=user_id, text="❌ <b>Cancelled or not a photo.</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🪧 BACK", callback_data="cset_start_pic")]]) )
            photo_id = ans.photo.file_id
            clear_user_session(user_id)
            save_fn(start_pic=photo_id)
            return await client.send_message(
                chat_id=user_id,
                text="<b>SUCCESSFULLY PICTURE SET ✅</b>",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🪧 BACK", callback_data="cset_start_pic")]])
            )
        asyncio.create_task(_spic_worker())
        return

    if data == "cset_del_start_pic":
        save_fn(start_pic=None)
        await query.answer("Start picture deleted!")
        return await edit_or_reply_fn(
            query,
            "<b>SUCCESSFULLY DELETED START PICTURE ✅</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🪧 BACK", callback_data="cset_start_pic")]])
        )

    if data == "cset_tgl_start_spoiler":
        spoiler = not bool(r.get("start_pic_spoiler", False))
        save_fn(start_pic_spoiler=spoiler)
        return await handle_start_message_callbacks(client, query, "cset_start_pic", user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn)
