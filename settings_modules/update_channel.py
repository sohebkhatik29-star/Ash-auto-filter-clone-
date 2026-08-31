"""Update Channel management & delivery helper.
Allows managing update channel join-request / public links easily,
and provides unified 'Please wait...' with [ • cancel ] and [ 📢 UPDATE CHANNEL ] buttons
across all link generators (/link, /genlink, /batch, /custom_batch, /special_link, /universal_link).
"""
import logging
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from config import UPDATE_CHANNEL, tg_link

logger = logging.getLogger(__name__)

# Default list of update channels (can include join-request links like https://t.me/+... or usernames)
# You can add or edit as many update channel links as you want here!
DEFAULT_UPDATE_CHANNELS = [
    "MoviesGroupG3",  # default username or join link e.g. "https://t.me/+YourJoinRequestLink"
]


def format_telegram_link(link_or_username: str) -> str:
    """Format any join request link, invite link or username into a valid Telegram URL."""
    val = (link_or_username or "").strip()
    if not val:
        return "https://t.me/MoviesGroupG3"
    if val.startswith("https://") or val.startswith("http://"):
        return val
    if val.startswith("+"):
        return f"https://t.me/{val}"
    return f"https://t.me/{val.lstrip('@')}"


def get_update_channel_url(client=None, bot_id=None) -> str:
    """Get the configured update channel / join-request link for this bot or master.
    Checks bot record in DB, master DB, env var, and default fallback list.
    """
    try:
        from clone_plugins.database import mongo_db
        b_id = None
        if bot_id:
            b_id = int(bot_id)
        elif client and getattr(client, "me", None):
            b_id = int(client.me.id)

        rec = None
        if mongo_db is not None and b_id:
            rec = mongo_db.bots.find_one({"$or": [{"bot_id": b_id}, {"bot_id": str(b_id)}]})

        if not rec and client:
            try:
                from clone_plugins.commands import bot_record
                rec = bot_record(client)
            except Exception:
                pass

        if rec:
            # Check custom join link / update channel in bot record
            custom_link = (
                rec.get("update_channel_link")
                or rec.get("join_request_link")
                or rec.get("update_channel")
                or rec.get("updates_channel")
            )
            if custom_link:
                return format_telegram_link(custom_link)

            # Check list of channels if multiple configured
            ch_list = rec.get("update_channels") or rec.get("update_channel_list")
            if isinstance(ch_list, list) and ch_list:
                return format_telegram_link(str(ch_list[0]))

        # Check master settings in DB
        if mongo_db is not None:
            m_rec = mongo_db.master_settings.find_one({"type": "master_config"}) or mongo_db.master_settings.find_one({})
            if m_rec:
                m_link = (
                    m_rec.get("update_channel_link")
                    or m_rec.get("join_request_link")
                    or m_rec.get("update_channel")
                    or m_rec.get("updates_channel")
                )
                if m_link:
                    return format_telegram_link(m_link)

    except Exception as e:
        logger.warning(f"Error getting update channel link: {e}")

    # Fallback to config or default list
    if UPDATE_CHANNEL:
        return format_telegram_link(UPDATE_CHANNEL)
    if DEFAULT_UPDATE_CHANNELS:
        return format_telegram_link(DEFAULT_UPDATE_CHANNELS[0])

    return "https://t.me/MoviesGroupG3"


def get_wait_markup(client=None, cancel_callback_data: str = "cancel_delivery", custom_channel_url: str = None) -> InlineKeyboardMarkup:
    """Build the exact 'Please wait...' inline markup:
    Row 1: [ • cancel ]
    Row 2: [ 📢 UPDATE CHANNEL ↗ ]
    """
    ch_url = custom_channel_url or get_update_channel_url(client)
    buttons = [
        [InlineKeyboardButton("• cancel", callback_data=cancel_callback_data)],
        [InlineKeyboardButton("📢 UPDATE CHANNEL", url=ch_url)],
    ]
    return InlineKeyboardMarkup(buttons)


async def send_wait_message(client, user_id_or_message, cancel_callback_data: str = "cancel_delivery"):
    """Send the standard 'Please wait...\n\n• cancel' message with markup."""
    markup = get_wait_markup(client, cancel_callback_data=cancel_callback_data)
    text = "Please wait...\n\n• cancel"
    if hasattr(user_id_or_message, "reply"):
        return await user_id_or_message.reply(text, reply_markup=markup)
    return await client.send_message(user_id_or_message, text, reply_markup=markup)


def set_update_channel_link(bot_id: int, new_link: str) -> bool:
    """Dynamically set/change the update channel join request link for a bot."""
    try:
        from clone_plugins.database import mongo_db
        if mongo_db is None:
            return False
        mongo_db.bots.update_one(
            {"$or": [{"bot_id": int(bot_id)}, {"bot_id": str(bot_id)}]},
            {"$set": {"update_channel_link": new_link, "update_channel": new_link}},
            upsert=False
        )
        return True
    except Exception as e:
        logger.error(f"Failed to update channel link in DB: {e}")
        return False
