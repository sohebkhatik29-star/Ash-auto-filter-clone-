# 🆓 FREE USAGE LIMIT SETTINGS MODULE
import re
import time
import asyncio
from pyrogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
)
from clone_plugins.sessions import start_user_session, is_user_session_active, clear_user_session

def parse_free_limit_duration(text: str):
    """
    Parses strings like:
    '1s', '30s' -> seconds
    '1', '1m', '10m', '1min', '1minute' -> minutes
    '1h', '2h', '12h', '1hour' -> hours
    '1d', '7d', '1day' -> days
    '1w', '2w', '1week' -> weeks
    '1month', '1mhont', '1moth', '1mon', '1mo' -> months (30 days)
    '1year', '1yar', '1yr', '1y' -> years (365 days)
    Returns: (duration_seconds, human_display_string, raw_num, raw_unit) or (None, None, None, None)
    """
    txt = (text or "").strip().lower()
    if not txt:
        return None, None, None, None
    
    m = re.match(r"^(\d+)\s*([a-z]*)$", txt)
    if not m:
        return None, None, None, None
    
    num_str, unit_str = m.groups()
    try:
        num = int(num_str)
    except Exception:
        return None, None, None, None
    if num <= 0:
        return None, None, None, None
    
    unit_str = unit_str.strip()
    
    if not unit_str or unit_str in ("m", "min", "mins", "minute", "minutes"):
        seconds = num * 60
        display = f"{num} Minute(s)" if num != 1 else "1 Minute"
        return seconds, display, num, "minute"
    
    if unit_str in ("s", "sec", "secs", "second", "seconds"):
        seconds = num
        display = f"{num} Second(s)" if num != 1 else "1 Second"
        return seconds, display, num, "second"
    
    if unit_str in ("h", "hr", "hrs", "hour", "hours"):
        seconds = num * 3600
        display = f"{num} Hour(s)" if num != 1 else "1 Hour"
        return seconds, display, num, "hour"
    
    if unit_str in ("d", "day", "days"):
        seconds = num * 86400
        display = f"{num} Day(s)" if num != 1 else "1 Day(s)"
        return seconds, display, num, "day"
    
    if unit_str in ("w", "wk", "wks", "week", "weeks"):
        seconds = num * 7 * 86400
        display = f"{num} Week(s)" if num != 1 else "1 Week(s)"
        return seconds, display, num, "week"
    
    if unit_str in ("month", "months", "mhont", "mhonts", "moth", "moths", "mon", "mons", "mo"):
        seconds = num * 30 * 86400
        display = f"{num} Month(s)" if num != 1 else "1 Month(s)"
        return seconds, display, num, "month"
    
    if unit_str in ("year", "years", "yar", "yars", "yr", "yrs", "y"):
        seconds = num * 365 * 86400
        display = f"{num} Year(s)" if num != 1 else "1 Year(s)"
        return seconds, display, num, "year"
    
    return None, None, None, None


async def handle_free_limit_callbacks(client, query, data, user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn, target_bid=None):
    if ":" in data:
        try:
            target_bid = int(data.split(":")[1])
        except Exception:
            pass

    is_clone = bool(target_bid or str(data).startswith("cset_"))
    back_cb = f"manage_clone:{target_bid}" if target_bid else ("cset:home" if str(data).startswith("cset_") else "settings")
    prefix = f":{target_bid}" if target_bid else ""

    set_cb = f"cset_set_free_limit{prefix}" if str(data).startswith("cset_") else f"m_set_free_limit{prefix}"
    del_cb = f"cset_del_free_limit{prefix}" if str(data).startswith("cset_") else f"m_del_free_limit{prefix}"
    menu_cb = f"cset_free_limit_menu{prefix}" if str(data).startswith("cset_") else f"master_free_limit_menu{prefix}"

    if data in ("master_free_limit_menu", "cset_free_limit_menu") or data.startswith(("master_free_limit_menu:", "cset_free_limit_menu:")):
        f_limit = r.get("free_limit", {})
        count = int(f_limit.get("count", 0))
        is_on = bool(f_limit.get("enabled", False))
        window_display = f_limit.get("display") or f_limit.get("window_text") or (f"EVERY {f_limit.get('num', 1)} {f_limit.get('unit', 'DAY').upper()}(S)" if f_limit.get("num") else "1 DAY(S)")
        if not str(window_display).upper().startswith("EVERY"):
            reset_str = f"EVERY {window_display.upper()}"
        else:
            reset_str = window_display.upper()

        if is_on and count > 0:
            status_desc = f"📊 <b>CURRENT FREE USAGE LIMIT:</b>\n* <b>FILES ALLOWED:</b> {count} FILES\n* <b>RESET PERIOD:</b> {reset_str}"
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
                [InlineKeyboardButton("SET FREE USAGE LIMIT", callback_data=set_cb)],
                [InlineKeyboardButton("DELETE FREE USAGE LIMIT", callback_data=del_cb)],
                [InlineKeyboardButton("‹ BACK", callback_data=back_cb)]
            ])
        )

    if data in ("m_del_free_limit", "cset_del_free_limit") or data.startswith(("m_del_free_limit:", "cset_del_free_limit:", "master_del_free_limit:")):
        save_fn(free_limit={"enabled": False, "count": 0, "duration_seconds": 0, "display": "None", "window_text": "None", "num": 0, "unit": "day"})
        try:
            await query.answer("Free limit deleted!", show_alert=True)
        except Exception:
            pass
        return await handle_free_limit_callbacks(client, query, menu_cb, user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn, target_bid=target_bid)

    if data in ("m_set_free_limit", "cset_set_free_limit") or data.startswith(("m_set_free_limit:", "cset_set_free_limit:", "master_set_free_limit:")):
        cancel_listeners_fn(client, user_id, user_id)
        sess_token = start_user_session(user_id, f"free_limit_{target_bid or 'main'}")
        try:
            await query.answer()
        except Exception:
            pass
        await client.send_message(
            user_id,
            "🆓 <b>SET FREE USAGE LIMIT:</b>\n\n"
            "<b>Step 1/2: Send how many free uses/files you want to allow (e.g., <code>2</code>, <code>5</code>, <code>1500</code>):</b>\n\n"
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
            if txt.lower() == "/cancel":
                await client.send_message(user_id, "❌ <b>Cancelled.</b>")
                clear_user_session(user_id)
                return
            if not txt.isdigit() or int(txt) <= 0:
                await client.send_message(user_id, "❌ <b>Invalid number. Must be a positive integer (e.g. 2, 5, 1500).</b>")
                clear_user_session(user_id)
                return
            count = int(txt)
            
            await client.send_message(
                user_id,
                f"🆓 <b>Step 2/2: Send the reset time duration for {count} files:</b>\n\n"
                "<b>Examples:</b>\n"
                "• <code>1s</code> - 1 second\n"
                "• <code>1m</code> or <code>1</code> - 1 minute\n"
                "• <code>1h</code> - 1 hour\n"
                "• <code>1d</code> - 1 day\n"
                "• <code>1month</code> (or <code>1mhont</code>) - 1 month\n"
                "• <code>1year</code> (or <code>1yar</code>) - 1 year\n\n"
                "<i>Send /cancel to abort.</i>"
            )
            try:
                ans2 = await client.listen(chat_id=user_id, timeout=120)
            except Exception:
                await client.send_message(user_id, "❌ <b>Timeout. Process cancelled.</b>")
                clear_user_session(user_id)
                return
            if not is_user_session_active(user_id, sess_token):
                return
            txt2 = (ans2.text or "").strip()
            if txt2.lower() == "/cancel":
                await client.send_message(user_id, "❌ <b>Cancelled.</b>")
                clear_user_session(user_id)
                return
            
            duration_sec, display_str, num, unit = parse_free_limit_duration(txt2)
            if not duration_sec:
                await client.send_message(
                    user_id,
                    "❌ <b>Invalid time duration.</b>\n\nPlease use formats like <code>1s</code>, <code>1m</code> (or <code>1</code>), <code>1h</code>, <code>1d</code>, <code>1month</code>, <code>1year</code>."
                )
                clear_user_session(user_id)
                return

            window_text = f"Every {display_str}"
            save_fn(free_limit={
                "enabled": True,
                "count": count,
                "duration_seconds": duration_sec,
                "display": display_str,
                "window_text": window_text,
                "num": num,
                "unit": unit
            })
            clear_user_session(user_id)
            await client.send_message(
                user_id,
                f"✅ <b>FREE USAGE LIMIT SET TO {count} FILES EVERY {display_str.upper()}!</b>",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK TO FREE USAGE LIMIT", callback_data=menu_cb)]])
            )
        asyncio.create_task(_limit_worker())
        return
