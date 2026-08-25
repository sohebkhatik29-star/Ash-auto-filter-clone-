from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery

# Note: Agar aapka database import alag hai (jaise database.users_chats_db), 
# toh aap apne project ke hisaab se import rakh sakte hain.

@Client.on_callback_query(filters.regex("^auto_delete$"))
async def auto_delete_menu_handler(client: Client, query: CallbackQuery):
    try:
        await query.answer()
    except Exception:
        pass
        
    user_id = query.from_user.id
    
    # Yahan aap apne database se status fetch kar sakte hain (Default values di gayi hain)
    # Example: is_enabled = await db.get_auto_delete_status(user_id)
    # Example: ad_time = int(await db.get_auto_delete_time(user_id, 300))
    
    is_enabled = True  # Default true rakha hai testing ke liye
    ad_time = 300      # Seconds (300 sec = 5 min)
    
    status_text = "🟢 Enabled" if is_enabled else "🔴 Disabled"
    time_display = f"{ad_time // 60} Minutes" if ad_time >= 60 else f"{ad_time} Seconds"
    
    buttons = [
        [
            InlineKeyboardButton(f"Auto Delete: {status_text}", callback_data="toggle_auto_delete"),
        ],
        [
            InlineKeyboardButton(f"⏱️ Set Time: {time_display}", callback_data="set_auto_delete_time"),
        ],
        [
            InlineKeyboardButton("« Back", callback_data="start_settings"),
        ]
    ]
    
    try:
        await query.message.edit_text(
            "<b>⚙️ Auto Delete Settings</b>\n\n"
            "Aap yahan se files ke auto-delete hone ka status aur time configure kar sakte hain.",
            reply_markup=InlineKeyboardMarkup(buttons),
            disable_web_page_preview=True
        )
    except Exception as e:
        print(f"Auto delete menu error: {e}")

@Client.on_callback_query(filters.regex("^toggle_auto_delete$"))
async def toggle_auto_delete_callback(client: Client, query: CallbackQuery):
    await query.answer("Auto Delete status updated!", show_alert=False)
    # TODO: Yahan apna database toggle update code daal dena
    # Phir se menu refresh karne ke liye:
    await auto_delete_menu_handler(client, query)

@Client.on_callback_query(filters.regex("^set_auto_delete_time$"))
async def set_time_menu(client: Client, query: CallbackQuery):
    await query.answer()
    buttons = [
        [
            InlineKeyboardButton("5 Minutes", callback_data="ad_time_300"),
            InlineKeyboardButton("10 Minutes", callback_data="ad_time_600"),
        ],
        [
            InlineKeyboardButton("30 Minutes", callback_data="ad_time_1800"),
            InlineKeyboardButton("1 Hour", callback_data="ad_time_3600"),
        ],
        [
            InlineKeyboardButton("« Back", callback_data="auto_delete"),
        ]
    ]
    await query.message.edit_text(
        "<b>⏱️ Select Auto Delete Time</b>\n\n"
        "Kitne samay baad file delete honi chahiye, uska samay chuniye:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

@Client.on_callback_query(filters.regex("^ad_time_"))
async def save_auto_delete_time(client: Client, query: CallbackQuery):
    try:
        data_parts = query.data.split("_")
        time_seconds = int(data_parts[-1])
    except Exception:
        time_seconds = 300
        
    await query.answer(f"Auto delete time updated successfully!", show_alert=True)
    
    # TODO: Yahan database mein time_seconds save karwa dena
    # Example: await db.update_auto_delete_time(query.from_user.id, time_seconds)
    
    # Wapas main auto-delete menu par redirect kar do
    await auto_delete_menu_handler(client, query)
