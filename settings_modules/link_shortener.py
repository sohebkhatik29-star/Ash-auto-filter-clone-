# 🖇️ LINK SHORTENER SETTINGS MODULE
import asyncio
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from clone_plugins.sessions import start_user_session, is_user_session_active, clear_user_session

def shortener_settings_markup(site: str, api: str, is_enabled: bool, back_cb="settings", bid=None):
    cb_set = f"m_set_main_shortener:{bid}" if bid else "m_set_main_shortener"
    cb_del = f"m_del_main_shortener:{bid}" if bid else "m_del_main_shortener"
    cb_tgl = f"m_tgl_shortlink:{bid}" if bid else "m_tgl_shortlink"
    
    rows = [
        [InlineKeyboardButton("SET SHORTLINK", callback_data=cb_set)],
        [InlineKeyboardButton("DELETE SHORTLINK", callback_data=cb_del)],
    ]
    
    has_credentials = bool(site and site != "Not Set" and api and api != "Not Set")
    if has_credentials:
        tgl_btn_text = "OFF SHORTLINK" if is_enabled else "ON SHORTLINK"
        rows.append([InlineKeyboardButton(tgl_btn_text, callback_data=cb_tgl)])
        
    rows.append([InlineKeyboardButton("‹ BACK", callback_data=back_cb)])
    return InlineKeyboardMarkup(rows)

def render_shortener_text(site: str, api: str, is_enabled: bool) -> str:
    status_txt = "ON ✅" if is_enabled else "OFF ❌"
    site_txt = site if site and site != "Not Set" else "Not Set"
    api_txt = api if api and api != "Not Set" else "Not Set"
    
    return (
        "🖇️ <b>LINK SHORTNER:</b>\n\n"
        "<blockquote>LINK SHORTENER: A TOOL THAT CONVERTS FILE LINKS INTO MONETIZED URLS, ALLOWING BOT OWNERS TO EARN MONEY WHENEVER A USER CLICKS.</blockquote>\n\n"
        f"<b>SHORTLINK - {status_txt}</b>\n\n"
        f"<b>URL -</b> <code>{site_txt}</code>\n"
        f"<b>API -</b> <code>{api_txt}</code>"
    )

async def handle_shortener_callbacks(client, query, data, user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn, target_bid=None):
    data_str = str(data or "")
    if not target_bid and ":" in data_str:
        last_part = data_str.split(":")[-1]
        if last_part.isdigit() and len(last_part) >= 6:
            target_bid = int(last_part)

    back_cb = f"manage_clone:{target_bid}" if target_bid else "settings_back"
    menu_cb = f"link_shortener:{target_bid}" if target_bid else "link_shortener"

    site = r.get("shortener_site") or r.get("base_site") or "Not Set"
    api = r.get("shortener_api") or "Not Set"
    has_creds = bool(site and site != "Not Set" and api and api != "Not Set")
    is_enabled = bool(r.get("shortener_enabled", True)) if has_creds else False

    # Main Link Shortener Menu
    if (
        data_str in ("link_shortener", "cset_shortener")
        or data_str.startswith(("link_shortener:", "cset_shortener:"))
    ):
        text = render_shortener_text(site, api, is_enabled)
        return await edit_or_reply_fn(
            query,
            text,
            reply_markup=shortener_settings_markup(site, api, is_enabled, back_cb=back_cb, bid=target_bid)
        )

    # Toggle Shortlink ON / OFF
    if (
        data_str in ("m_tgl_shortlink", "tgl_shortlink")
        or data_str.startswith(("m_tgl_shortlink:", "tgl_shortlink:"))
    ):
        if not has_creds:
            if query:
                await query.answer("❌ Please set shortlink URL & API first!", show_alert=True)
            return
        new_state = not is_enabled
        save_fn(shortener_enabled=new_state)
        r["shortener_enabled"] = new_state
        if query:
            await query.answer(f"Shortlink turned {'ON' if new_state else 'OFF'}!")
        text = render_shortener_text(site, api, new_state)
        return await edit_or_reply_fn(
            query,
            text,
            reply_markup=shortener_settings_markup(site, api, new_state, back_cb=back_cb, bid=target_bid)
        )

    # Delete Shortlink
    if (
        data_str in ("m_del_main_shortener", "delete_shortener", "delete_shortlink")
        or data_str.startswith(("m_del_main_shortener:", "delete_shortener:", "delete_shortlink:"))
    ):
        save_fn(shortener_site=None, shortener_api=None, base_site=None, shortener_enabled=False)
        r["shortener_site"] = None
        r["shortener_api"] = None
        r["base_site"] = None
        r["shortener_enabled"] = False
        if query:
            await query.answer("Shortener deleted!")
        text = render_shortener_text("Not Set", "Not Set", False)
        return await edit_or_reply_fn(
            query,
            text,
            reply_markup=shortener_settings_markup("Not Set", "Not Set", False, back_cb=back_cb, bid=target_bid)
        )

    # Set Shortlink
    if (
        data_str in ("m_set_main_shortener", "add_shortener", "set_shortlink")
        or data_str.startswith(("m_set_main_shortener:", "add_shortener:", "set_shortlink:"))
    ):
        cancel_listeners_fn(client, user_id, user_id)
        sess_token = start_user_session(user_id, "m_main_short")
        if query:
            try:
                await query.answer()
            except Exception:
                pass
        
        prompt1 = await client.send_message(
            chat_id=user_id,
            text=(
                "<b>SEND ME A SHORTLINK URL OR DOMAIN...</b>\n\n"
                "<b>FORMAT :</b>\n\n"
                "https://vjlink.online - ❌\n\n"
                "<code>vjlink.online</code> - ✅\n\n"
                "/cancel - <b>CANCEL THIS PROCESS.</b>"
            )
        )

        async def _m_short_worker():
            try:
                ans = await client.listen(chat_id=user_id, timeout=120)
            except Exception:
                try:
                    await prompt1.delete()
                except Exception:
                    pass
                clear_user_session(user_id)
                await client.send_message(
                    chat_id=user_id,
                    text="❌ <b>Timeout. Process cancelled.</b>",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("‹ BACK", callback_data=menu_cb)]
                    ])
                )
                return

            if not is_user_session_active(user_id, sess_token):
                return

            st = (ans.text or "").strip()
            if st == "/cancel":
                try:
                    await prompt1.delete()
                    await ans.delete()
                except Exception:
                    pass
                clear_user_session(user_id)
                await client.send_message(
                    chat_id=user_id,
                    text="❌ <b>Process cancelled.</b>",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("‹ BACK", callback_data=menu_cb)]
                    ])
                )
                return

            st = st.replace("http://", "").replace("https://", "").strip("/")
            try:
                await prompt1.delete()
                await ans.delete()
            except Exception:
                pass

            prompt2 = await client.send_message(
                chat_id=user_id,
                text="<b>SEND ME SHORTLINK API...</b>\n\n/cancel - <b>CANCEL THIS PROCESS.</b>"
            )

            try:
                ans2 = await client.listen(chat_id=user_id, timeout=120)
            except Exception:
                try:
                    await prompt2.delete()
                except Exception:
                    pass
                clear_user_session(user_id)
                await client.send_message(
                    chat_id=user_id,
                    text="❌ <b>Timeout. Process cancelled.</b>",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("‹ BACK", callback_data=menu_cb)]
                    ])
                )
                return

            if not is_user_session_active(user_id, sess_token):
                return

            ap = (ans2.text or "").strip()
            if ap == "/cancel":
                try:
                    await prompt2.delete()
                    await ans2.delete()
                except Exception:
                    pass
                clear_user_session(user_id)
                await client.send_message(
                    chat_id=user_id,
                    text="❌ <b>Process cancelled.</b>",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("‹ BACK", callback_data=menu_cb)]
                    ])
                )
                return

            try:
                await prompt2.delete()
                await ans2.delete()
            except Exception:
                pass

            save_fn(shortener_site=st, shortener_api=ap, base_site=st, shortener_enabled=True)
            r["shortener_site"] = st
            r["shortener_api"] = ap
            r["base_site"] = st
            r["shortener_enabled"] = True
            clear_user_session(user_id)

            await client.send_message(
                chat_id=user_id,
                text="<b>SUCCESSFULLY SET SHORTLINK</b> ✅",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("‹ BACK", callback_data=menu_cb)]
                ])
            )

        asyncio.create_task(_m_short_worker())
        return

