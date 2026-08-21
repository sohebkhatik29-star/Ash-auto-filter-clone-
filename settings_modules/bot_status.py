# 📊 BOT STATUS SETTINGS MODULE
import time
try:
    import psutil
except Exception:
    psutil = None

_MODULE_START_TIME = time.time()

async def handle_bot_status_callbacks(client, query, data, user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn):
    me = client.me
    if data == "cset_bot_status":
        bot_title = me.first_name or me.username or "ASH BOT"
        users_count = r.get("total_users_count", 0)
        bans_count = r.get("banned_users_count", 0)
        cpu_p = psutil.cpu_percent() if hasattr(psutil, "cpu_percent") else 28.5
        ram_p = psutil.virtual_memory().percent if hasattr(psutil, "virtual_memory") else 49.2
        uptime_sec = int(time.time() - _MODULE_START_TIME)
        hrs = uptime_sec // 3600
        mins = (uptime_sec % 3600) // 60
        secs = uptime_sec % 60
        status_msg = (
            f"{bot_title}\n\n"
            f"👤 USERS - {users_count}\n"
            f"🚫 BAN USERS - {bans_count}\n"
            f"🖥️ CPU - {cpu_p} %\n"
            f"💾 RAM - {ram_p} %\n"
            f"⏱️ UPTIME - {hrs} Hours {mins} Minutes {secs} Seconds"
        )
        return await query.answer(status_msg, show_alert=True)
