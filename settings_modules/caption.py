# 🍿 CUSTOM CAPTION SETTINGS MODULE
import asyncio
from pyrogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardRemove
)
from clone_plugins.sessions import start_user_session, is_user_session_active, clear_user_session

def caption_settings_markup(invert_on: bool, spoiler_on: bool, back_cb="settings", bid=None):
    invert_btn_text = "INVERT CAPTION - ✅" if invert_on else "INVERT CAPTION - ❌"
    spoiler_btn_text = "SPOILER ANIMATION - ✅" if spoiler_on else "SPOILER ANIMATION - ❌"
    
    cb_set = f"m_set_caption:{bid}" if bid else "m_set_caption"
    cb_del = f"m_del_caption:{bid}" if bid else "m_del_caption"
    cb_inv = f"m_tgl_cap_invert:{bid}" if bid else "m_tgl_cap_invert"
    cb_spoil = f"m_tgl_cap_spoiler:{bid}" if bid else "m_tgl_cap_spoiler"
    
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("SET CAPTION", callback_data=cb_set)],
        [InlineKeyboardButton("DEFAULT CAPTION", callback_data=cb_del)],
        [InlineKeyboardButton(invert_btn_text, callback_data=cb_inv)],
        [InlineKeyboardButton(spoiler_btn_text, callback_data=cb_spoil)],
        [InlineKeyboardButton("‹ BACK", callback_data=back_cb)]
    ])

def render_caption_text(cap: str, invert_on: bool, spoiler_on: bool) -> str:
    invert_status = "ON ✅" if invert_on else "OFF ❌"
    spoiler_status = "ON ✅" if spoiler_on else "OFF ❌"
    cap_display = cap if cap else "None"
    
    return (
        "<b>AVAILABLE FILLING:-</b>\n\n"
        "<code>{file_name}</code> - <b>FILE NAME FOR MEDIA MESSAGE</b>\n"
        "<code>{file_size}</code> - <b>FILE SIZE FOR MEDIA MESSAGE</b>\n"
        "<code>{originalcaption}</code> - <b>ORIGINAL CAPTION FOR MEDIA MESSAGE</b>\n\n"
        "<b>CAPTION :-</b>\n\n"
        f"<code>{cap_display}</code>\n\n"
        f"<b>INVERT CAPTION - {invert_status}</b>\n\n"
        f"<b>SPOILER ANIMATION - {spoiler_status}</b>\n\n"
        "<b>NOTE:</b>\n"
        "<b>INVERT CAPTION :</b> IF ON THEN CAPTION SHOW ABOVE VIDEO FILE, IF OFF THEN CAPTION SHOW BELOW VIDEO FILE AS NORMAL.\n\n"
        "<b>SPOILER ANIMATION:</b> IF ON THEN VIDEO FILE THUMBNAIL GET SPOILER ANIMATION, IF OFF THEN NO SPOILER ANIMATION.\n\n"
        "<b>NOTE:</b> <i>SPOILER AND INVERT CAPTION SUPPORT ONLY IN VIDEO FILE NOT IN OTHER MEDIA</i>"
    )

async def handle_caption_callbacks(client, query, data, user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn, target_bid=None):
    data_str = str(data or "")
    if not target_bid and ":" in data_str:
        last_part = data_str.split(":")[-1]
        if last_part.isdigit() and len(last_part) >= 6:
            target_bid = int(last_part)

    back_cb = f"manage_clone:{target_bid}" if target_bid else "settings_back"
    main_cb = f"custom_caption:{target_bid}" if target_bid else "custom_caption"

    # Helper to cleanly show/edit text
    async def clean_show(txt, markup):
        msg = getattr(query, "message", None) or query
        if msg and (getattr(msg, "photo", None) or getattr(msg, "media", None)):
            try:
                await msg.delete()
            except Exception:
                pass
            return await client.send_message(chat_id=user_id, text=txt, reply_markup=markup)
        return await edit_or_reply_fn(query, txt, reply_markup=markup)

    # 1. Main Caption Menu
    if data_str == "custom_caption" or data_str.startswith("custom_caption:") or data_str == "cset_caption" or data_str.startswith("cset_caption:"):
        try:
            await query.answer()
        except Exception:
            pass
        cap = r.get("custom_caption") or ""
        invert_on = bool(r.get("invert_caption", False))
        spoiler_on = bool(r.get("spoiler_animation", False))
        text = render_caption_text(cap, invert_on, spoiler_on)
        return await clean_show(text, caption_settings_markup(invert_on, spoiler_on, back_cb, target_bid))

    # 2. Toggle Invert Caption
    if data_str.startswith(("m_tgl_cap_invert", "cset_tgl_cap_invert", "caption_invert")):
        cur_invert = bool(r.get("invert_caption", False))
        new_invert = not cur_invert
        save_fn(invert_caption=new_invert)
        r["invert_caption"] = new_invert
        try:
            await query.answer(f"Invert Caption set to {'ON' if new_invert else 'OFF'}")
        except Exception:
            pass
        cap = r.get("custom_caption") or ""
        spoiler_on = bool(r.get("spoiler_animation", False))
        text = render_caption_text(cap, new_invert, spoiler_on)
        return await clean_show(text, caption_settings_markup(new_invert, spoiler_on, back_cb, target_bid))

    # 3. Toggle Spoiler Animation
    if data_str.startswith(("m_tgl_cap_spoiler", "cset_tgl_cap_spoiler", "caption_spoiler")):
        cur_spoiler = bool(r.get("spoiler_animation", False))
        new_spoiler = not cur_spoiler
        save_fn(spoiler_animation=new_spoiler)
        r["spoiler_animation"] = new_spoiler
        try:
            await query.answer(f"Spoiler Animation set to {'ON' if new_spoiler else 'OFF'}")
        except Exception:
            pass
        cap = r.get("custom_caption") or ""
        invert_on = bool(r.get("invert_caption", False))
        text = render_caption_text(cap, invert_on, new_spoiler)
        return await clean_show(text, caption_settings_markup(invert_on, new_spoiler, back_cb, target_bid))

    # 4. Reset to Default Caption
    if data_str.startswith(("m_del_caption", "cset_del_caption", "caption_delete")):
        save_fn(custom_caption=None)
        r["custom_caption"] = None
        try:
            await query.answer("Caption reset to default!")
        except Exception:
            pass
        invert_on = bool(r.get("invert_caption", False))
        spoiler_on = bool(r.get("spoiler_animation", False))
        text = render_caption_text("", invert_on, spoiler_on)
        return await clean_show(text, caption_settings_markup(invert_on, spoiler_on, back_cb, target_bid))

    # 5. Set Custom Caption Wizard
    if data_str.startswith(("m_set_caption", "cset_set_caption", "caption_edit")):
        cancel_listeners_fn(client, user_id, user_id)
        sess_token = start_user_session(user_id, "m_caption")
        try:
            await query.answer()
        except Exception:
            pass
        prompt_text = (
            "<b>SEND ME A FILE CAPTION.</b>\n\n"
            "<b>AVAILABLE FILLING:-</b>\n\n"
            "<code>{file_name}</code> - <b>FILE NAME FOR MEDIA MESSAGE</b>\n"
            "<code>{file_size}</code> - <b>FILE SIZE FOR MEDIA MESSAGE</b>\n"
            "<code>{originalcaption}</code> - <b>ORIGINAL CAPTION FOR MEDIA MESSAGE</b>\n\n"
            "/cancel - <b>CANCEL THIS PROCESS.</b>"
        )
        prompt_markup = InlineKeyboardMarkup([[InlineKeyboardButton("‹ CANCEL", callback_data=main_cb)]])
        prompt_msg = await clean_show(prompt_text, prompt_markup)
        
        async def _cap_worker():
            try:
                ans = await client.listen(chat_id=user_id, timeout=120)
            except Exception:
                clear_user_session(user_id)
                cap = r.get("custom_caption") or ""
                inv = bool(r.get("invert_caption", False))
                sp = bool(r.get("spoiler_animation", False))
                await clean_show(render_caption_text(cap, inv, sp), caption_settings_markup(inv, sp, back_cb, target_bid))
                return
            if not is_user_session_active(user_id, sess_token):
                return
            try:
                await ans.delete()
            except Exception:
                pass
            t = (ans.text or ans.caption or "").strip()
            if t == "/cancel":
                clear_user_session(user_id)
                cap = r.get("custom_caption") or ""
                inv = bool(r.get("invert_caption", False))
                sp = bool(r.get("spoiler_animation", False))
                await clean_show(render_caption_text(cap, inv, sp), caption_settings_markup(inv, sp, back_cb, target_bid))
                return
            save_fn(custom_caption=t)
            r["custom_caption"] = t
            clear_user_session(user_id)
            inv = bool(r.get("invert_caption", False))
            sp = bool(r.get("spoiler_animation", False))
            updated_text = render_caption_text(t, inv, sp)
            await clean_show(updated_text, caption_settings_markup(inv, sp, back_cb, target_bid))
        asyncio.create_task(_cap_worker())
        return
