# 🆓 FREE USAGE LIMIT SETTINGS MODULE
import asyncio
from pyrogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
)
from clone_plugins.sessions import start_user_session, is_user_session_active, clear_user_session

async def handle_free_limit_callbacks(client, query, data, user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn):
    if data == "master_free_limit_menu" or data == "cset_free_limit_menu":
        f_limit = r.get("free_limit", {})
        count = f_limit.get("count", 0)
        num = f_limit.get("num", 0)
        unit = f_limit.get("unit", "day")
        is_on = bool(f_limit.get("enabled", False))
        if is_on and count > 0:
            status_desc = f"📊 <b>CURRENT FREE USAGE LIMIT:</b>\n* <b>FILES ALLOWED:</b> {count} FILES\n* <b>RESET PERIOD:</b> EVERY {num} {unit.upper()}(S)"
        else:
            status_desc = "⚠️ <b>FREE USAGE LIMIT:</b> 🚫 <b>DISABLED\n(UNLIMITED ACCESS)</b>"
            
        text = (
            "🆓 <b>FREE USAGE LIMIT:</b>\n\n"
            "<b>FREE USAGE LIMIT ALLOWS YOU TO CONTROL HOW MANY FILES A USER CAN ACCESS FOR FREE THROUGH YOUR SHARE LINK. YOU CAN SET ANY CUSTOM LIMIT (E.G., DAYS, WEEKS, MONTHS, OR YEARS).</b>\n\n"
            "⚠️ <b>NOTE:</b>\n"
            "1. <b>IF NO LIMIT IS SET, THE FREE LIMIT FEATURE IS COMPLETELY DISABLED, AND USERS CAN ACCESS UNLIMITED FILES WITHOUT ANY RESTRICTIONS.</b>\n"
            "2. <b>THIS FREE LIMIT FEATURE WILL ONLY WORK WHEN PREMIUM FEATURE OR TOKEN VERIFICATION FEATURE IS ENABLED.</b>\n\n"
            "💡 <b>EXAMPLE:</b>\n"
            "<b>IF YOU SET A LIMIT OF 5 FILES EVERY 1 MONTH, THEN A USER OPENING YOUR LINK CAN ONLY GET 5 FILES FOR FREE IN THAT MONTH. ONCE THE LIMIT IS REACHED, THEY MUST WAIT UNTIL THE MONTH RESETS TO GET MORE.</b>\n\n"
            f"{status_desc}"
        )
        return await edit_or_reply_fn(
            query,
            text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("SET FREE USAGE LIMIT", callback_data="m_set_free_limit")],
                [InlineKeyboardButton("DELETE FREE USAGE LIMIT", callback_data="m_del_free_limit")],
                [InlineKeyboardButton("🪧 BACK", callback_data="settings")]
            ])
        )

    if data == "m_del_free_limit" or data == "cset_del_free_limit":
        save_fn(free_limit={"enabled": False, "count": 0, "num": 0, "unit": "day"})
        await query.answer("Free limit deleted!")
        return await handle_free_limit_callbacks(client, query, "master_free_limit_menu", user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn)

    if data == "m_set_free_limit" or data == "cset_set_free_limit":
        cancel_listeners_fn(client, user_id, user_id)
        sess_token = start_user_session(user_id, "m_free_limit")
        await query.answer()
        await query.message.reply(
            "🆓 <b>SET FREE USAGE LIMIT:</b>\n\n"
            "<b>Step 1/2: How many files can a free user access? (Send a number, e.g. <code>5</code>):</b>\n\n"
            "<i>Send /cancel to abort.</i>"
        )
        async def _limit_worker():
            try:
                ans = await client.listen(chat_id=user_id, timeout=120)
            except Exception:
                await client.send_message(user_id, "❌ <b>Timeout. Process cancelled.</b>")
                clear_user_session(user_id)
                return
            if not is_user_session_active(user_id, sess_token):
                return
            txt = (ans.text or "").strip()
            if txt == "/cancel":
                await client.send_message(user_id, "❌ <b>Cancelled.</b>")
                clear_user_session(user_id)
                return
            if not txt.isdigit() or int(txt) <= 0:
                await client.send_message(user_id, "❌ <b>Invalid number. Must be a positive integer.</b>")
                clear_user_session(user_id)
                return
            count = int(txt)
            
            unit_kb = ReplyKeyboardMarkup([
                [KeyboardButton("1 Day"), KeyboardButton("7 Days")],
                [KeyboardButton("1 Month"), KeyboardButton("1 Year")]
            ], resize_keyboard=True, one_time_keyboard=True)
            
            await client.send_message(
                user_id,
                f"🆓 <b>Step 2/2: Choose reset interval for {count} files:</b>",
                reply_markup=unit_kb
            )
            try:
                ans2 = await client.listen(chat_id=user_id, timeout=120)
            except Exception:
                await client.send_message(user_id, "❌ <b>Timeout. Process cancelled.</b>", reply_markup=ReplyKeyboardRemove())
                clear_user_session(user_id)
                return
            if not is_user_session_active(user_id, sess_token):
                return
            txt2 = (ans2.text or "").strip().lower()
            if txt2 == "/cancel":
                await client.send_message(user_id, "❌ <b>Cancelled.</b>", reply_markup=ReplyKeyboardRemove())
                clear_user_session(user_id)
                return
            
            num = 1
            unit = "day"
            if "month" in txt2:
                unit = "month"
                num = 1
            elif "year" in txt2:
                unit = "year"
                num = 1
            elif "7" in txt2 or "week" in txt2:
                unit = "day"
                num = 7
            else:
                unit = "day"
                num = 1
                
            save_fn(free_limit={"enabled": True, "count": count, "num": num, "unit": unit})
            clear_user_session(user_id)
            await client.send_message(
                user_id,
                f"✅ <b>FREE USAGE LIMIT SET TO {count} FILES EVERY {num} {unit.upper()}(S)!</b>",
                reply_markup=ReplyKeyboardRemove()
            )
            await client.send_message(
                user_id,
                "<b>Settings Updated ✅</b>",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🪧 BACK TO SETTINGS", callback_data="settings")]])
            )
        asyncio.create_task(_limit_worker())
        return
