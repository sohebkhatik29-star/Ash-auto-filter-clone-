# 🪙 MONETIZATION SETTINGS MODULE
import asyncio
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

async def handle_monetization_callbacks(client, query, data, user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn):
    if data == "cset_monetization":
        return await edit_or_reply_fn(
            query,
            "🪙 <b>MONETIZATION:</b>\n\n<b>EARN REVENUE VIA LINK SHORTENERS AND PREMIUM MEMBERSHIP SUBSCRIPTIONS.</b>",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🖇️ LINK SHORTNER", callback_data="link_shortener")],
                [InlineKeyboardButton("💸 PREMIUM PLAN", callback_data="master_premium_plan")],
                [InlineKeyboardButton("🪧 BACK", callback_data="clone_my_clone_info")]
            ])
        )
