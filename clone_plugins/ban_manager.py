# 🚫 BAN & RESTRICTION MANAGER FOR CLONE BOTS
import logging

try:
    from pyrogram.types import CallbackQuery
except Exception:
    CallbackQuery = None

_BANNED_CACHE = {}  # {bot_id: {user_id: bool}}

def set_banned_in_cache(bot_id: int, user_id: int, banned: bool):
    try:
        bid = int(bot_id)
        uid = int(user_id)
        if bid not in _BANNED_CACHE:
            _BANNED_CACHE[bid] = {}
        _BANNED_CACHE[bid][uid] = bool(banned)
    except Exception:
        pass

def get_banned_from_cache(bot_id: int, user_id: int):
    try:
        bid = int(bot_id)
        uid = int(user_id)
        if bid in _BANNED_CACHE and uid in _BANNED_CACHE[bid]:
            return _BANNED_CACHE[bid][uid]
    except Exception:
        pass
    return None

def clear_ban_cache(bot_id: int = None):
    try:
        if bot_id is None:
            _BANNED_CACHE.clear()
        elif int(bot_id) in _BANNED_CACHE:
            _BANNED_CACHE[int(bot_id)].clear()
    except Exception:
        pass

async def is_user_banned(client, user_id: int) -> bool:
    if not user_id:
        return False
    try:
        uid = int(user_id)
        me = getattr(client, "me", None)
        if not me and hasattr(client, "get_me"):
            me = await client.get_me()
        bot_id = int(me.id) if me and getattr(me, "id", None) else None

        # 1. Bot owner or bot self cannot be banned
        if bot_id and uid == bot_id:
            return False
        try:
            from clone_plugins.clone_settings_ui import is_bot_owner
            if is_bot_owner(client, uid):
                return False
        except Exception:
            pass

        # 2. Check memory cache
        if bot_id:
            cached = get_banned_from_cache(bot_id, uid)
            if cached is not None:
                return cached

        # 3. Check clonedb (async motor)
        if bot_id:
            try:
                from clone_plugins.dbusers import clonedb
                u_doc = await clonedb.db[str(bot_id)].find_one({"user_id": uid})
                if u_doc:
                    if u_doc.get("banned") is True:
                        set_banned_in_cache(bot_id, uid, True)
                        return True
                    elif u_doc.get("banned") is False:
                        set_banned_in_cache(bot_id, uid, False)
                        return False
            except Exception:
                pass

        # 4. Check mongo_db (sync pymongo)
        if bot_id:
            try:
                from plugins.clone import mongo_db
                if mongo_db is not None:
                    if mongo_db.clone_bans.find_one({"bot_id": bot_id, "user_id": uid}):
                        set_banned_in_cache(bot_id, uid, True)
                        return True

                    b_rec = mongo_db.bots.find_one({"$or": [{"bot_id": int(bot_id)}, {"bot_id": str(bot_id)}]})
                    if b_rec:
                        b_list = b_rec.get("banned_users", [])
                        if isinstance(b_list, list) and uid in [int(x) for x in b_list if str(x).isdigit() or isinstance(x, int)]:
                            set_banned_in_cache(bot_id, uid, True)
                            return True
            except Exception:
                pass

        if bot_id:
            set_banned_in_cache(bot_id, uid, False)
        return False
    except Exception as e:
        logging.exception(f"Error checking ban for user {user_id}: {e}")
        return False

BANNED_REPLY_TEXT = (
    "🚫 <b>Sorry, you are banned!</b>\n\n"
    "<i>You cannot use this bot as you have been banned by the administrator.</i>"
)

async def check_user_banned_or_block(client, message_or_query) -> bool:
    try:
        from_user = getattr(message_or_query, "from_user", None)
        if not from_user:
            return False
        uid = getattr(from_user, "id", None)
        if not uid:
            return False

        banned = await is_user_banned(client, uid)
        if not banned:
            return False

        # If CallbackQuery:
        is_cb = False
        if CallbackQuery is not None and isinstance(message_or_query, CallbackQuery):
            is_cb = True
        elif hasattr(message_or_query, "data") and hasattr(message_or_query, "answer"):
            is_cb = True

        if is_cb:
            try:
                await message_or_query.answer("🚫 Sorry, you are banned!", show_alert=True)
            except Exception:
                pass
            return True

        # If Message:
        try:
            msg = getattr(message_or_query, "message", None) or message_or_query
            await msg.reply_text(BANNED_REPLY_TEXT)
        except Exception:
            pass
        return True
    except Exception as e:
        logging.exception(f"Error in check_user_banned_or_block: {e}")
        return False

async def ban_user(client, target_uid: int):
    uid = int(target_uid)
    me = getattr(client, "me", None) or (await client.get_me())
    bot_id = int(me.id)

    # 1. Update clonedb
    try:
        from clone_plugins.dbusers import clonedb
        await clonedb.set_user_ban_status(bot_id, uid, True)
    except Exception:
        pass

    # 2. Update mongo_db
    try:
        from plugins.clone import mongo_db
        if mongo_db is not None:
            mongo_db.clone_bans.update_one(
                {"bot_id": bot_id, "user_id": uid},
                {"$set": {"bot_id": bot_id, "user_id": uid}},
                upsert=True
            )
            mongo_db.bots.update_one(
                {"$or": [{"bot_id": int(bot_id)}, {"bot_id": str(bot_id)}]},
                {"$addToSet": {"banned_users": uid}}
            )
    except Exception:
        pass

    # 3. Update in-memory cache
    set_banned_in_cache(bot_id, uid, True)

async def unban_user(client, target_uid: int):
    uid = int(target_uid)
    me = getattr(client, "me", None) or (await client.get_me())
    bot_id = int(me.id)

    # 1. Update clonedb
    try:
        from clone_plugins.dbusers import clonedb
        await clonedb.set_user_ban_status(bot_id, uid, False)
    except Exception:
        pass

    # 2. Update mongo_db
    try:
        from plugins.clone import mongo_db
        if mongo_db is not None:
            mongo_db.clone_bans.delete_many(
                {"bot_id": bot_id, "user_id": uid}
            )
            mongo_db.bots.update_one(
                {"$or": [{"bot_id": int(bot_id)}, {"bot_id": str(bot_id)}]},
                {"$pull": {"banned_users": uid}}
            )
    except Exception:
        pass

    # 3. Update in-memory cache
    set_banned_in_cache(bot_id, uid, False)
