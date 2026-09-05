# ASH FILE STORE & CLONE MANAGER - AUTHORIZATION & ACCESS CONTROL
import logging
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import ADMINS, BOT_USERNAME, PUBLIC_FILE_STORE

logger = logging.getLogger(__name__)

UNAUTHORIZED_MESSAGE_TEXT = (
    "⚠️ <b>You are not my Master!</b>\n\n"
    "❝ <b>Only the Clone Owner, Clone Admins, and Master Admins are authorized to use commands and generate links in this bot.</b> ❞\n\n"
    "💡 <i>You can create your own personal clone bot to use all link generation and storage features!</i>"
)

def get_db():
    try:
        from plugins.clone import mongo_db
        return mongo_db
    except Exception:
        return None

def is_master_admin(uid) -> bool:
    """Check if user is Master Bot Owner or Master Bot Admin."""
    try:
        uid_int = int(uid)
        for a in ADMINS:
            if str(a).strip().lstrip("-").isdigit() and int(a) == uid_int:
                return True
        db = get_db()
        if db is not None:
            if db.master_admins.find_one({"user_id": uid_int}):
                return True
    except Exception:
        pass
    return False

def get_clone_record(client) -> dict:
    """Retrieve clone bot configuration record from database."""
    db = get_db()
    if db is None:
        return {}
    try:
        b_id = getattr(client, "me", None) and getattr(client.me, "id", None)
        if b_id:
            rec = db.bots.find_one({"$or": [{"bot_id": int(b_id)}, {"bot_id": str(b_id)}]})
            if rec:
                return rec
        token_val = getattr(client, "bot_token", None) or getattr(client, "_token", "")
        if token_val:
            rec = db.bots.find_one({"$or": [{"token": token_val}, {"bot_token": token_val}]})
            if rec:
                return rec
        if getattr(client, "me", None) and getattr(client.me, "username", None):
            rec = db.bots.find_one({"$or": [{"username": client.me.username}, {"username": client.me.username.lower()}]})
            if rec:
                return rec
    except Exception:
        pass
    return {}

def is_clone_bot(client) -> bool:
    """Determine if the current client is a Clone Bot or the Master Bot."""
    try:
        if not getattr(client, "me", None):
            return False
        if BOT_USERNAME and getattr(client.me, "username", None):
            if client.me.username.lower() != BOT_USERNAME.lower():
                return True
        rec = get_clone_record(client)
        if rec and rec.get("bot_id"):
            return True
    except Exception:
        pass
    return False

def is_clone_owner(client, uid) -> bool:
    """Check if user is the creator / owner of this clone bot."""
    try:
        uid_int = int(uid)
        rec = get_clone_record(client)
        if rec and int(rec.get("user_id", 0)) == uid_int:
            return True
    except Exception:
        pass
    return False

def is_clone_admin(client, uid) -> bool:
    """Check if user is added as an admin or moderator in this clone bot."""
    try:
        uid_int = int(uid)
        rec = get_clone_record(client)
        if not rec:
            return False
        # Check admins list / dict
        adms = rec.get("admins", [])
        if isinstance(adms, dict):
            adms = list(adms.values())
        for a in adms:
            if isinstance(a, dict):
                if int(a.get("user_id", 0)) == uid_int:
                    return True
            elif str(a).isdigit() and int(a) == uid_int:
                return True
        # Check moderators list
        mods = rec.get("moderators", [])
        if isinstance(mods, list):
            for m in mods:
                if str(m).isdigit() and int(m) == uid_int:
                    return True
    except Exception:
        pass
    return False

def is_clone_authorized(client, uid) -> bool:
    """
    Complete Authorization Check:
    - Master Bot: Master Admin / Master Owner are always authorized. If PUBLIC_FILE_STORE is True, users can generate links.
    - Clone Bot: ONLY Master Owner, Master Admins, Clone Owner, and Clone Admins are authorized!
    """
    try:
        uid_int = int(uid)
    except Exception:
        return False

    # 1. Master Owner & Master Admins have global authority on all bots
    if is_master_admin(uid_int):
        return True

    # 2. Check if this client is a Clone Bot
    if is_clone_bot(client):
        # On Clone Bots: ONLY Clone Owner and Clone Admins are allowed!
        if is_clone_owner(client, uid_int):
            return True
        if is_clone_admin(client, uid_int):
            return True
        return False

    # 3. On Master Bot:
    return bool(PUBLIC_FILE_STORE)

def unauthorized_markup(client=None):
    """Generate inline keyboard with Create Clone Bot button for unauthorized users."""
    buttons = []
    if BOT_USERNAME:
        buttons.append([InlineKeyboardButton("🤖 CREATE MY CLONE BOT", url=f"https://t.me/{BOT_USERNAME}?start=clone")])
    return InlineKeyboardMarkup(buttons) if buttons else None

async def require_clone_auth(client, update) -> bool:
    """
    Helper function to check authorization for Message or CallbackQuery.
    Returns True if authorized, False otherwise (and replies/alerts the user).
    """
    user = getattr(update, "from_user", None)
    if not user:
        return False
    user_id = user.id

    if is_clone_authorized(client, user_id):
        return True

    # Unauthorized:
    if hasattr(update, "answer") and callable(update.answer):
        # CallbackQuery
        try:
            await update.answer("⚠️ You are not my Master / Admin!", show_alert=True)
        except Exception:
            pass
    elif hasattr(update, "reply") and callable(update.reply):
        # Message
        try:
            await update.reply(
                UNAUTHORIZED_MESSAGE_TEXT,
                reply_markup=unauthorized_markup(client),
                disable_web_page_preview=True
            )
        except Exception:
            pass
    return False
