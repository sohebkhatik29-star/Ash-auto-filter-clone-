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
            mins_left = max(0, 4 - (elapsed // 60))
            secs_left = max(0, 59 - (elapsed % 60))
            inactivity_info = f"{mins_left} Mins {secs_left} Secs Remaining"
        else:
            inactivity_info = "5 Minutes (Resets on every user activity)"

        text = (
            "⚡ <b>BOT STATUS (ACTIVE / DEACTIVATE):</b>\n\n"
            "<blockquote>CONTROL AND MONITOR YOUR CLONE BOT STATUS.</blockquote>\n\n"
            "<b>AVAILABLE MODES:</b>\n\n"
            "<b>- ENABLE: BOT IS FULLY ACTIVE AND DELIVERS FILES/MESSAGES TO ALL USERS.</b>\n\n"
            "<b>- DISABLE: BOT IS DEACTIVATED AND WILL NOT SERVE USERS UNTIL REACTIVATED.</b>\n\n"
            "<b>AUTOMATIC INACTIVITY POLICY:</b>\n"
            "<b>• IF NO USER STARTS OR USES THIS BOT FOR 5 CONSECUTIVE MINUTES, IT IS AUTOMATICALLY DEACTIVATED BY THE SYSTEM.</b>\n"
            "<b>• STARTING OR USING THE BOT AT ANY TIME RESETS THE 5-MINUTE TIMER.</b>\n\n"
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
        INACTIVITY_SECONDS = 5 * 60  # 5 Minutes for testing
        await asyncio.sleep(15)  # Initial wait on startup
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
                            logging.info(f"Auto-deactivated clone @{bot_username} (ID: {bid}) after 5 minutes of inactivity.")

                            deact_notice = (
                                f"⚠️ <b>Your clone {bot_name} (@{bot_username}) was automatically deactivated by our system due to being inactive for the last 5 minutes.</b>\n\n"
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

            # Check every 30 seconds
            await asyncio.sleep(30)

    asyncio.create_task(_inactivity_checker_loop())
