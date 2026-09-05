"""
Button Debouncer / Anti-Spam Module
Prevents duplicate panels and race conditions when users click buttons multiple times rapidly.
"""
import time
import logging

logger = logging.getLogger(__name__)

_USER_LAST_CLICK = {}

def should_throttle_button(user_id: int, callback_data: str = "", msg_id: int = 0, cooldown: float = 0.45) -> bool:
    """
    Returns True if the button click from this user should be throttled (ignored).
    Cooldown defaults to 0.45s which absorbs fast multi-taps.
    """
    if not user_id:
        return False
    now = time.time()
    uid = int(user_id)
    last_click = _USER_LAST_CLICK.get(uid, 0.0)
    if (now - last_click) < cooldown:
        return True
    _USER_LAST_CLICK[uid] = now

    if len(_USER_LAST_CLICK) > 5000:
        cutoff = now - 30.0
        for k in list(_USER_LAST_CLICK.keys()):
            if _USER_LAST_CLICK[k] < cutoff:
                del _USER_LAST_CLICK[k]

    return False

async def debounce_callback(query, cooldown: float = 0.45) -> bool:
    """
    Convenience helper: checks if the callback is throttled.
    If throttled, automatically answers the query (to hide the loading spinner)
    and returns True.
    """
    try:
        uid = getattr(query, "from_user", None) and query.from_user.id
        msg_id = getattr(query, "message", None) and query.message.id
        data = getattr(query, "data", "") or ""
        if should_throttle_button(uid, callback_data=data, msg_id=msg_id, cooldown=cooldown):
            try:
                await query.answer()
            except Exception:
                pass
            return True
    except Exception:
        pass
    return False
