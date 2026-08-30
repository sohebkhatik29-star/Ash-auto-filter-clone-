# ⚡ BOT STATUS (ACTIVE / DEACTIVATE) & 8-DAY INACTIVITY AUTO-DEACTIVATION MODULE
import time
import asyncio
import logging
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def db():
    from plugins.clone import mongo_db
    return mongo_db

def touch_bot_activity(bot_id: int):
    """Update the last_active_time for a bot to the current timestamp."""
    try:
        m = db()
        if m is not None and bot_id:
            m.bots.update_one(
                {"bot_id": int(bot_id)},
                {"$set": {"last_active_time": time.time()}},
                upsert=False
            )
    except Exception:
        pass

def is_clone_suspended(client_or_bid):
    """Return (is_suspended, suspend_doc)."""
    try:
        from settings_modules.master_admin_panel import is_clone_suspended as _check_susp
        return _check_susp(client_or_bid)
    except Exception:
        return False, {}

async def check_clone_status_or_block(client, message_or_query) -> bool:
    """
    Check if clone bot is suspended or deactivated.
    If suspended or deactivated, replies with notice and returns True (meaning BLOCKED).
    If active, touches bot activity and returns False (meaning ALLOWED).
    """
    me = client.me or (await client.get_me())
    from config import BOT_USERNAME
    if me and me.username and BOT_USERNAME and me.username.lower() == BOT_USERNAME.lower():
        return False

    is_susp, susp_doc = is_clone_suspended(me.id)
    if is_susp:
        until = susp_doc.get("suspended_until")
        dur_str = susp_doc.get("suspend_duration_str", "Temporary")
        import datetime
        until_str = datetime.datetime.fromtimestamp(until).strftime("%Y-%m-%d %H:%M:%S UTC") if until else "Permanent"
        admin_name = susp_doc.get("suspended_by") or "Administrator"
        text = (
            f"⛔ <b>THIS BOT HAS BEEN SUSPENDED!</b>\n\n"
            f"<blockquote>This clone bot has been suspended by Master Bot Administrator (@{admin_name}).</blockquote>\n\n"
            f"<b>⏱ Duration:</b> <code>{dur_str}</code>\n"
            f"<b>⏳ Expiry:</b> <code>{until_str}</code>\n"
            f"<b>👮 Administrator:</b> @{admin_name}\n\n"
            f"<i>If you are the bot owner or have questions, please contact @{admin_name}.</i>"
        )
        markup = None
        if admin_name and not admin_name.startswith("User"):
            markup = InlineKeyboardMarkup([[InlineKeyboardButton("💬 CONTACT ADMIN", url=f"https://t.me/{admin_name.lstrip('@')}")]])
        msg = getattr(message_or_query, "message", None) or message_or_query
        try:
            if hasattr(msg, "reply_text"):
                await msg.reply_text(text, reply_markup=markup)
            elif hasattr(message_or_query, "answer"):
                await message_or_query.answer("⛔ This bot is SUSPENDED by Administrator.", show_alert=True)
        except Exception:
            pass
        return True

    if is_clone_deactivated(me.id):
        m = db()
        doc = m.bots.find_one({"bot_id": me.id}) if m is not None else {}
        owner_id = int(doc.get("user_id", 0))
        from_uid = getattr(getattr(message_or_query, "from_user", None), "id", 0)
        msg = getattr(message_or_query, "message", None) or message_or_query

        if from_uid and from_uid == owner_id:
            text = (
                f"⚠️ <b>Your clone @{me.username} is currently DEACTIVATED.</b>\n\n"
                f"<i>Your bot was deactivated manually or automatically by our system due to being inactive for 8 days.\n\n"
                f"You can reactivate it anytime using Master Bot (@{BOT_USERNAME}) -> Settings -> Manage Clone -> Bot Status and click <b>ENABLE</b>.</i>"
            )
            buttons = [[InlineKeyboardButton("🤖 OPEN MASTER BOT ↗", url=f"https://t.me/{BOT_USERNAME}?start=clone")]]
            try:
                await msg.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))
            except Exception:
                pass
        else:
            text = (
                "⚠️ <b>This bot is currently DEACTIVATED by its owner.</b>\n\n"
                "<i>Please contact the bot administrator to activate it.</i>"
            )
            try:
                await msg.reply_text(text)
            except Exception:
                pass
        return True

    touch_bot_activity(me.id)
    return False

def is_clone_deactivated(client_or_bid) -> bool:
    """Return True if the bot is currently deactivated."""
    try:
        m = db()
        if m is None:
            return False
        if isinstance(client_or_bid, (int, str)):
            bid = int(client_or_bid)
        else:
            bid = int(client_or_bid.me.id)
        doc = m.bots.find_one({"bot_id": bid}, {"deactivated": 1})
        if doc:
            return bool(doc.get("deactivated", False))
    except Exception:
        pass
    return False

async def handle_active_deactive_callbacks(client, query, data, user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn, target_bid=None):
    data_str = str(data or "")
    if not target_bid and ":" in data_str:
        try:
            target_bid = int(data_str.split(":", 1)[1])
        except Exception:
            pass

    back_cb = f"manage_clone:{target_bid}" if target_bid else "settings"
    tgl_cb = f"cset_tgl_active:{target_bid}" if target_bid else "cset_tgl_active"

    if data_str.startswith(("cset_active_deactive", "master_active_deactive", "bot_active_status")) and not data_str.startswith(("cset_tgl_active", "cset_act_")):
        deactivated = bool(r.get("deactivated", False))
        status_str = "DISABLE ❌" if deactivated else "ENABLE ✅"
        tgl_btn_text = "ENABLE ✅" if deactivated else "DISABLE ❌"

        last_act = r.get("last_active_time")
        if not deactivated and last_act:
            elapsed = max(0, int(time.time() - float(last_act)))
            days_left = max(0, 8 - (elapsed // 86400))
            hours_left = max(0, 24 - ((elapsed % 86400) // 3600))
            inactivity_info = f"{days_left} Days {hours_left} Hours Remaining"
        else:
            inactivity_info = "8 Days (Resets on every user activity)"

        text = (
            "⚡ <b>BOT STATUS (ACTIVE / DEACTIVATE):</b>\n\n"
            "<blockquote>CONTROL AND MONITOR YOUR CLONE BOT STATUS.</blockquote>\n\n"
            "<b>AVAILABLE MODES:</b>\n\n"
            "<b>- ENABLE: BOT IS FULLY ACTIVE AND DELIVERS FILES/MESSAGES TO ALL USERS.</b>\n\n"
            "<b>- DISABLE: BOT IS DEACTIVATED AND WILL NOT SERVE USERS UNTIL REACTIVATED.</b>\n\n"
            "<b>AUTOMATIC INACTIVITY POLICY:</b>\n"
            "<b>• IF NO USER STARTS OR USES THIS BOT FOR 8 CONSECUTIVE DAYS, IT IS AUTOMATICALLY DEACTIVATED BY THE SYSTEM.</b>\n"
            "<b>• STARTING OR USING THE BOT AT ANY TIME RESETS THE 8-DAY TIMER.</b>\n\n"
            f"<b>BOT STATUS - {status_str}</b>\n"
            f"<b>INACTIVITY TIMER - <code>{inactivity_info}</code></b>"
        )

        return await edit_or_reply_fn(
            query,
            text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(tgl_btn_text, callback_data=tgl_cb)],
                [InlineKeyboardButton("‹ BACK", callback_data=back_cb)]
            ])
        )

    if data_str.startswith(("cset_tgl_active", "cset_act_on", "cset_act_off")):
        if data_str.startswith("cset_act_on"):
            deactivated = False
        elif data_str.startswith("cset_act_off"):
            deactivated = True
        else:
            deactivated = not bool(r.get("deactivated", False))

        now = time.time()
        save_fn(deactivated=deactivated, last_active_time=now)
        r["deactivated"] = deactivated
        r["last_active_time"] = now

        status_label = "DISABLE (DEACTIVATED)" if deactivated else "ENABLE (ACTIVE)"
        await query.answer(f"Bot Status set to {status_label}!")

        return await handle_active_deactive_callbacks(
            client, query, f"cset_active_deactive:{target_bid}" if target_bid else "cset_active_deactive",
            user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn, target_bid=target_bid
        )


_CHECKER_RUNNING = False

def start_inactivity_checker(master_client):
    """Start background periodic checker for 8-day inactive clone bots."""
    global _CHECKER_RUNNING
    if _CHECKER_RUNNING:
        return
    _CHECKER_RUNNING = True

    async def _inactivity_checker_loop():
        INACTIVITY_SECONDS = 8 * 86400  # 8 Days
        await asyncio.sleep(30)  # Initial wait on startup
        while True:
            try:
                m = db()
                if m is not None:
                    from plugins.clone import get_clone_client
                    from config import BOT_USERNAME
                    now = time.time()
                    active_clones = list(m.bots.find({"deactivated": {"$ne": True}}))

                    for clone in active_clones:
                        bid = clone.get("bot_id")
                        owner_id = clone.get("user_id")
                        bot_username = clone.get("username") or str(bid)
                        bot_name = clone.get("name") or bot_username

                        last_act = clone.get("last_active_time")
                        if not last_act:
                            # Initialize for existing bots that don't have last_active_time yet
                            m.bots.update_one({"_id": clone["_id"]}, {"$set": {"last_active_time": now}})
                            continue

                        try:
                            last_act_ts = float(last_act)
                        except Exception:
                            last_act_ts = now

                        if (now - last_act_ts) >= INACTIVITY_SECONDS:
                            # Deactivate the bot in database
                            m.bots.update_one({"_id": clone["_id"]}, {"$set": {"deactivated": True}})
                            logging.info(f"Auto-deactivated clone @{bot_username} (ID: {bid}) after 8 days of inactivity.")

                            deact_notice = (
                                f"⚠️ <b>Your clone {bot_name} (@{bot_username}) was automatically deactivated by our system due to being inactive for the last 8 days.</b>\n\n"
                                f"<i>You can reactivate it anytime using Master Bot (@{BOT_USERNAME}) -> Settings -> Manage Clone -> Bot Status.</i>"
                            )

                            # Send notification message to the clone owner
                            sent = False
                            clone_client = get_clone_client(bid)
                            if clone_client and owner_id:
                                try:
                                    await clone_client.send_message(chat_id=int(owner_id), text=deact_notice)
                                    sent = True
                                except Exception:
                                    pass

                            if not sent and master_client and owner_id:
                                try:
                                    await master_client.send_message(chat_id=int(owner_id), text=deact_notice)
                                except Exception:
                                    pass
            except Exception as e:
                logging.exception(f"Error in clone inactivity checker loop: {e}")

            # Check every 10 minutes (600 seconds)
            await asyncio.sleep(600)

    asyncio.create_task(_inactivity_checker_loop())
