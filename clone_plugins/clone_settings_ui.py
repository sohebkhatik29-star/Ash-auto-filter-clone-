# ASH FILE STORE & CLONE MANAGER - SETTINGS UI (MODULAR)
import asyncio
import time
from pyrogram import filters
from pyrogram.handlers import MessageHandler, CallbackQueryHandler
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from clone_plugins.sessions import cancel_all_listeners
from config import ADMINS, BOT_USERNAME

# Import modular handler functions
from settings_modules.premium_plan import handle_premium_callbacks
from settings_modules.free_limit import handle_free_limit_callbacks
from settings_modules.refer_earn import handle_refer_callbacks
from settings_modules.link_shortener import handle_shortener_callbacks
from settings_modules.token_verify import handle_token_callbacks
from settings_modules.force_sub import handle_fsub_callbacks
from settings_modules.caption import handle_caption_callbacks
from settings_modules.thumbnail import handle_thumbnail_callbacks
from settings_modules.custom_button import handle_custom_button_callbacks
from settings_modules.auto_delete import handle_auto_delete_callbacks
from settings_modules.permanent_link import handle_permanent_link_callbacks
from settings_modules.protect_content import handle_protect_content_callbacks
from settings_modules.monetization import handle_monetization_callbacks
from settings_modules.start_message import handle_start_message_callbacks
from settings_modules.log_channel import handle_log_channel_callbacks
from settings_modules.database_channel import handle_database_channel_callbacks
from settings_modules.admins import handle_admins_callbacks
from settings_modules.bot_status import handle_bot_status_callbacks
from settings_modules.bot_mode import handle_bot_mode_callbacks
from settings_modules.restart_bot import handle_restart_bot_callbacks
from settings_modules.delete_bot import handle_delete_bot_callbacks

def db():
    from plugins.clone import mongo_db
    return mongo_db

def record(client):
    m = db()
    if m is None:
        return {}
    return m.bots.find_one({"bot_id": client.me.id}) or {}

def is_bot_owner(client, uid):
    try:
        if int(uid) in [int(x) for x in ADMINS if str(x).strip().lstrip("-").isdigit()]:
            return True
    except Exception:
        pass
    r = record(client)
    try:
        if int(r.get("user_id", 0)) == int(uid):
            return True
    except Exception:
        pass
    return False

def get_bot_admins(client):
    r = record(client)
    adms = r.get("admins", [])
    if isinstance(adms, dict):
        return list(adms.values())
    elif isinstance(adms, list):
        return adms
    return []

def get_admin_data(client, uid):
    for a in get_bot_admins(client):
        if int(a.get("user_id", 0)) == int(uid):
            return a
    return None

def has_permission(client, uid, perm):
    if is_bot_owner(client, uid):
        return True
    adm = get_admin_data(client, uid)
    if not adm:
        return False
    return bool(adm.get(perm, False))

def save(client, **data):
    m = db()
    if m is not None:
        m.bots.update_one({"bot_id": client.me.id}, {"$set": data}, upsert=True)

def cancel_user_listeners(client, chat_id, user_id=None):
    cancel_all_listeners(client, chat_id, user_id)

async def edit_or_reply(query_or_msg, text, reply_markup=None, disable_web_page_preview=False):
    msg = getattr(query_or_msg, "message", None) or query_or_msg
    if not msg:
        return
    try:
        if getattr(msg, "photo", None) or getattr(msg, "media", None):
            try:
                return await msg.edit_caption(caption=text, reply_markup=reply_markup)
            except Exception as e:
                err = str(e).upper()
                if "MESSAGE_NOT_MODIFIED" in err:
                    return msg
                try:
                    return await msg.edit_text(text=text, reply_markup=reply_markup, disable_web_page_preview=disable_web_page_preview)
                except Exception:
                    pass
                try:
                    await msg.delete()
                except Exception:
                    pass
                return await msg.reply_text(text=text, reply_markup=reply_markup, disable_web_page_preview=disable_web_page_preview)
        else:
            try:
                return await msg.edit_text(text=text, reply_markup=reply_markup, disable_web_page_preview=disable_web_page_preview)
            except Exception as e:
                err = str(e).upper()
                if "MESSAGE_NOT_MODIFIED" in err:
                    return msg
                try:
                    await msg.delete()
                except Exception:
                    pass
                return await msg.reply_text(text=text, reply_markup=reply_markup, disable_web_page_preview=disable_web_page_preview)
    except Exception:
        pass

# ----------------- MARKUPS & MENUS ----------------- #

def settings_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💸 PREMIUM PLAN", callback_data="master_premium_plan")],
        [InlineKeyboardButton("🆓 FREE USAGE LIMIT", callback_data="cset_free_limit_menu")],
        [InlineKeyboardButton("🌍 REFER AND EARN", callback_data="cset_refer_earn")],
        [InlineKeyboardButton("🖇️ LINK SHORTNER", callback_data="link_shortener")],
        [InlineKeyboardButton("⏰ TOKEN VERIFICATION", callback_data="cset_token_main")],
        [InlineKeyboardButton("🔒 FORCE SUBSCRIBE", callback_data="cset_fsub_menu")],
        [InlineKeyboardButton("🍿 CAPTION", callback_data="custom_caption"), InlineKeyboardButton("🖼️ THUMBNAIL", callback_data="custom_thumbnail")],
        [InlineKeyboardButton("🔘 BUTTON", callback_data="custom_button"), InlineKeyboardButton("♻️ AUTO DELETE", callback_data="cset_auto_delete_menu")],
        [InlineKeyboardButton("♾️ PERMANENT LINK", callback_data="cset_permanent_link")],
        [InlineKeyboardButton("🔒 PROTECT CONTENT", callback_data="protect_menu")],
        [InlineKeyboardButton("🪧 BACK", callback_data="clone_my_clone_info")]
    ])

def clone_manage_hub_markup(bot_username, bot_id=None):
    deep_link = f"https://t.me/{BOT_USERNAME}?start=csettings_{bot_id}" if bot_id else f"https://t.me/{BOT_USERNAME}?start=clone"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🪙 MONETIZATION", callback_data="cset_monetization")],
        [InlineKeyboardButton("📝 START MESSAGE", callback_data="cset_start_msg_menu")],
        [InlineKeyboardButton("📢 LOG CHANNEL", callback_data="log_channel")],
        [InlineKeyboardButton("☁️ DATABASE CHANNEL", callback_data="database_channel")],
        [InlineKeyboardButton("👥 ADMINS", callback_data="admins_menu")],
        [InlineKeyboardButton("📊 BOT STATUS", callback_data="cset_bot_status")],
        [InlineKeyboardButton("🎁 BOT MODE", callback_data="cset_bot_mode")],
        [InlineKeyboardButton("🔄 RESTART BOT", callback_data="cset_restart_bot")],
        [InlineKeyboardButton("🚫 DELETE BOT", callback_data="cset_delete_bot")],
        [InlineKeyboardButton("🔎 MORE FEATURES ↗", url=deep_link)]
    ])

# ----------------- MAIN SETTINGS COMMAND & CALLBACKS ----------------- #

async def settings(client, message):
    me = client.me or (await client.get_me())
    text = (
        f"🤖 <b>YOUR CLONE BOT - @{me.username}</b>\n\n"
        "<i>YOU CAN CUSTOMISE YOUR BOT SETTINGS FROM GIVEN BELOW BUTTONS</i>"
    )
    await message.reply(text, reply_markup=clone_manage_hub_markup(me.username, me.id))

async def callbacks(client, query):
    data = query.data
    user_id = query.from_user.id
    try:
        cancel_user_listeners(client, user_id)
    except Exception:
        pass
    
    r = record(client)
    me = client.me
    
    def client_save(**kwargs):
        return save(client, **kwargs)

    # Master / clone creator callbacks that are ignored here
    if data in ("my_clone", "my_clones", "clone_my_bots", "create_clone_prompt", "clone_limit") or data.startswith(("manage_clone:", "cm:", "cad:", "cmdelete:")):
        return

    if data in ("settings", "settings_back", "cset:home", "clone_my_clone_info", "start_back", "cset:hub"):
        text = (
            f"🤖 <b>YOUR CLONE BOT - @{me.username}</b>\n\n"
            "<i>YOU CAN CUSTOMISE YOUR BOT SETTINGS FROM GIVEN BELOW BUTTONS</i>"
        )
        return await edit_or_reply(query, text, reply_markup=clone_manage_hub_markup(me.username))

    # Dispatch to modular handlers based on callback data prefix / match
    # 1. Premium Plan
    if data.startswith(("master_premium_plan", "cset_prem")):
        return await handle_premium_callbacks(client, query, data, user_id, r, client_save, cancel_user_listeners, edit_or_reply)

    # 2. Free Limit
    if data.startswith("cset_") and ("free_limit" in data or data in ("cset_set_free_limit", "cset_del_free_limit")):
        return await handle_free_limit_callbacks(client, query, data, user_id, r, client_save, cancel_user_listeners, edit_or_reply)

    # 3. Refer & Earn
    if data == "cset_refer_earn":
        return await handle_refer_callbacks(client, query, data, user_id, r, client_save, cancel_user_listeners, edit_or_reply)

    # 4. Token Verification
    if (
        data in ("cset_token_main", "cset_token_verification", "cset_verify_log_channel")
        or data.startswith((
            "cset_token_main", "cset_token_verification", "cset_verify_log_channel",
            "cset_v_", "cset_del_v_", "cset_set_v_"
        ))
    ):
        return await handle_token_callbacks(client, query, data, user_id, r, client_save, lambda: record(client), cancel_user_listeners, edit_or_reply)

    # 5. Force Subscribe
    if data.startswith("cset_fsub") or data in ("master_fsub_menu", "m_tgl_fsub", "m_clear_fsub", "m_add_fsub"):
        return await handle_fsub_callbacks(client, query, data, user_id, r, client_save, cancel_user_listeners, edit_or_reply)

    # 6. Caption
    if (
        data in ("custom_caption", "cset_caption", "m_set_caption", "m_del_caption", "cset_set_caption", "cset_del_caption", "cset_tgl_cap_invert", "cset_tgl_cap_spoiler", "m_tgl_cap_invert", "m_tgl_cap_spoiler", "caption_invert", "caption_spoiler", "caption_delete", "caption_edit")
        or data.startswith(("caption_", "cset_cap_", "custom_caption", "cset_caption", "m_set_caption", "m_del_caption", "m_tgl_cap_"))
    ):
        return await handle_caption_callbacks(client, query, data, user_id, r, client_save, cancel_user_listeners, edit_or_reply)

    # 7. Thumbnail
    if (
        data in ("custom_thumbnail", "cset_thumbnail", "m_set_thumb", "m_del_thumb", "m_view_thumb", "cset_set_thumb", "cset_del_thumb", "cset_view_thumb")
        or data.startswith(("custom_thumbnail:", "m_set_thumb:", "m_del_thumb:", "m_view_thumb:", "cset_"))
    ):
        return await handle_thumbnail_callbacks(client, query, data, user_id, r, client_save, cancel_user_listeners, edit_or_reply)

    # 8. Custom Button
    if (
        data in ("custom_button", "master_custom_button", "cset_button", "m_btn_add", "m_btn_rem", "m_btn_see", "cset_start_button", "cset_prem_button", "cset_fsub_btn")
        or data.startswith(("custom_button:", "m_btn_add:", "m_btn_rem:", "m_btn_see:", "btn_add:", "btn_rem:", "btn_see:", "btn_del_idx:"))
    ):
        return await handle_custom_button_callbacks(client, query, data, user_id, r, client_save, cancel_user_listeners, edit_or_reply)

    # 9. Auto Delete
    if data.startswith(("cset_auto_delete", "cset_ad_", "cset_tgl_ad", "cset_set_ad", "cset_autodelete", "master_auto_delete_menu", "m_ad_", "m_set_ad", "m_tgl_ad")):
        return await handle_auto_delete_callbacks(client, query, data, user_id, r, client_save, cancel_user_listeners, edit_or_reply)


    # 10. Permanent Link
    if data == "cset_permanent_link":
        return await handle_permanent_link_callbacks(client, query, data, user_id, r, client_save, cancel_user_listeners, edit_or_reply)

    # 11. Protect Content
    if data in ("protect_menu", "cset_tgl_protect"):
        return await handle_protect_content_callbacks(client, query, data, user_id, r, client_save, cancel_user_listeners, edit_or_reply)

    # 12. Link Shortener
    if data in ("link_shortener", "cset_shortener"):
        return await handle_shortener_callbacks(client, query, data, user_id, r, client_save, cancel_user_listeners, edit_or_reply)

    # 13. Monetization
    if data == "cset_monetization":
        return await handle_monetization_callbacks(client, query, data, user_id, r, client_save, cancel_user_listeners, edit_or_reply)

    # 14. Start Message
    if data in ("cset_start_msg_menu", "cset_start_text", "cset_set_start_text", "cset_def_start_text", "cset_start_pic", "cset_set_start_pic", "cset_del_start_pic", "cset_view_start_pic", "cset_tgl_start_spoiler", "cset_start_btn", "cset_start_button", "cset_sbtn_add", "cset_sbtn_rem", "cset_sbtn_see"):
        return await handle_start_message_callbacks(client, query, data, user_id, r, client_save, cancel_user_listeners, edit_or_reply)

    # 15. Log Channel
    if data in ("log_channel", "cset_set_log", "cset_del_log"):
        return await handle_log_channel_callbacks(client, query, data, user_id, r, client_save, cancel_user_listeners, edit_or_reply)

    # 16. Database Channel
    if data in ("database_channel", "cset_set_db_ch", "cset_del_db_ch"):
        return await handle_database_channel_callbacks(client, query, data, user_id, r, client_save, cancel_user_listeners, edit_or_reply)

    # 17. Admins
    if data in ("admins_menu", "adm_add") or data.startswith(("adm_manage:", "adm_tgl:", "adm_rem:", "adm_transfer:", "adm_do_transfer:")):
        return await handle_admins_callbacks(client, query, data, user_id, r, client_save, cancel_user_listeners, edit_or_reply)

    # 18. Bot Status
    if data in ("cset_bot_status", "bot_status"):
        return await handle_bot_status_callbacks(client, query, data, user_id, r, client_save, cancel_user_listeners, edit_or_reply)

    # 19. Bot Mode
    if data == "cset_bot_mode":
        return await handle_bot_mode_callbacks(client, query, data, user_id, r, client_save, cancel_user_listeners, edit_or_reply, clone_manage_hub_markup)

    # 20. Restart Bot
    if data == "cset_restart_bot":
        return await handle_restart_bot_callbacks(client, query, data, user_id, r, client_save, cancel_user_listeners, edit_or_reply)

    # 21. Delete Bot
    if data in ("cset_delete_bot", "cset_confirm_del_bot"):
        return await handle_delete_bot_callbacks(client, query, data, user_id, r, client_save, db, cancel_user_listeners, edit_or_reply)

    # Fallback
    await query.answer()

def register(client):
    client.add_handler(MessageHandler(settings, filters.command(["settings"]) & filters.private), group=2)
    client.add_handler(CallbackQueryHandler(callbacks), group=2)
