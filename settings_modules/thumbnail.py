import logging
from pyrogram import Client
from pyrogram.types import CallbackQuery

logger = logging.getLogger(__name__)

async def handle_thumbnail_callbacks(client: Client, query: CallbackQuery):
    """
    Complete handler for all thumbnail-related callback queries in settings.
    """
    data = query.data
    user_id = query.from_user.id

    # Try importing database handler dynamically to prevent circular imports
    db = None
    try:
        from database.database import db as database_instance
        db = database_instance
    except ImportError:
        try:
            from utils import db as database_instance
            db = database_instance
        except ImportError:
            pass

    if data == "view_thumb":
        try:
            thumbnail = await db.get_thumbnail(user_id) if db and hasattr(db, "get_thumbnail") else None
            if thumbnail:
                await query.message.reply_photo(
                    photo=thumbnail,
                    caption="<b>Aapka current custom thumbnail yeh hai:</b>"
                )
                await query.answer()
            else:
                await query.answer("Aapne abhi tak koi custom thumbnail set nahi kiya hai!", show_alert=True)
        except Exception as e:
            logger.error(f"Error viewing thumbnail for {user_id}: {e}")
            await query.answer("Thumbnail fetch karne me error aayi hai.", show_alert=True)

    elif data == "del_thumb":
        try:
            if db and hasattr(db, "del_thumbnail"):
                await db.del_thumbnail(user_id)
            await query.answer("Thumbnail successfully hata diya gaya hai!", show_alert=True)
            try:
                await query.message.edit_text(
                    "<b>Thumbnail successfully delete kar diya gaya hai!</b>",
                    reply_markup=query.message.reply_markup
                )
            except Exception:
                pass
        except Exception as e:
            logger.error(f"Error deleting thumbnail for {user_id}: {e}")
            await query.answer("Thumbnail delete karne me error aayi hai.", show_alert=True)

    elif data == "set_thumb":
        await query.answer("Kripya agla message ek photo bhejein jise aap thumbnail banana chahte hain.", show_alert=True)
        try:
            await query.message.edit_text(
                "<b>Kripya apna naya thumbnail photo ke roop me yahan send karein:</b>"
            )
        except Exception:
            pass

    else:
        await query.answer("Invalid or expired thumbnail option!", show_alert=True)

