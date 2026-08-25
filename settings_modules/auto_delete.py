import asyncio
import re
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Function 1: Seconds ko normal time text me badalne ke liye
def get_time_string(seconds):
    if seconds < 60:
        return f"{seconds} Seconds"
    elif seconds < 3600:
        return f"{seconds // 60} Minutes"
    elif seconds < 86400:
        return f"{seconds // 3600} Hours"
    else:
        return f"{seconds // 86400} Days"

# Function 2: User ke bheje gaye text (5s, 10m) ko Seconds me badalne ke liye
def parse_time_input(text_input):
    match = re.match(r"^(\d+)([smhd])$", text_input.strip().lower())
    if not match:
        return None
    value = int(match.group(1))
    unit = match.group(2)
    
    if unit == 's': return value
    elif unit == 'm': return value * 60
    elif unit == 'h': return value * 3600
    elif unit == 'd': return value * 86400
    return None

async def handle_auto_delete_callbacks(client, query, data, user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn):
    
    # 1. MAIN MENU
    if data in ("master_auto_delete_menu", "cset_autodelete"):
        ad_on = bool(r.get("auto_delete_enabled", False))
        ad_time = r.get("auto_delete_time", 60) # Default 60 seconds
        
        time_display = get_time_string(ad_time)
        status_txt = f"ON ({time_display}) ✅" if ad_on else "OFF ❌"
        
        text = (
            "♻️ **AUTO DELETE MESSAGES:**\n\n"
            f"• **STATUS:** **{status_txt}**\n\n"
            "**Automatically delete delivered files after a given time to protect copyright.**"
        )
        tgl_btn = "DISABLE AUTO DELETE" if ad_on else "ENABLE AUTO DELETE"
        
        # Yahan Button Menu update kiya gaya hai
        return await edit_or_reply_fn(query, text, reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(tgl_btn, callback_data="m_tgl_ad")],
            [InlineKeyboardButton("⏰ SET CUSTOM TIME", callback_data="m_ask_ad_time")],
            [InlineKeyboardButton("🔘 SET CUSTOM BUTTON", callback_data="m_ask_ad_btn")], # NAYA BUTTON
            [InlineKeyboardButton("🪧 BACK", callback_data="settings")]
        ]))

    # 2. ON / OFF LOGIC
    if data in ("m_tgl_ad", "cset_autodelete_toggle"):
        new_s = not bool(r.get("auto_delete_enabled", False))
        save_fn(auto_delete_enabled=new_s)
        await query.answer(f"Auto delete {'Enabled' if new_s else 'Disabled'}!", show_alert=True)
        return await handle_auto_delete_callbacks(client, query, "master_auto_delete_menu", user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn)

    # 3. CUSTOM TIME LOGIC
    if data == "m_ask_ad_time":
        await query.answer()
        ask_msg = await query.message.reply(
            "**Please send the auto-delete time you want to set.**\n\n"
            "**Examples:** `5s`, `10m`, `2h`, `1d`"
        )
        try:
            user_input = await client.listen(query.message.chat.id, timeout=60)
            if user_input.text:
                time_in_seconds = parse_time_input(user_input.text)
                if time_in_seconds:
                    save_fn(auto_delete_enabled=True, auto_delete_time=time_in_seconds)
                    await user_input.reply(f"✅ **Success!** Time set to **{get_time_string(time_in_seconds)}**.")
                else:
                    await user_input.reply("❌ **Invalid format!**")
        except asyncio.TimeoutError:
            await ask_msg.edit("❌ **Time out!**")
        
        return await handle_auto_delete_callbacks(client, query, "master_auto_delete_menu", user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn)

    # 4. CUSTOM BUTTON LOGIC (NAYA ADD KIYA HAI)
    if data == "m_ask_ad_btn":
        await query.answer()
        ask_text = (
            "**Apne Button ka Text aur Link is format me bhejein:**\n\n"
            "`Button Ka Naam | https://aapkalink.com`\n\n"
            "**Example:**\n"
            "`Google | https://google.com`\n\n"
            "*(Agar button hatana hai toh sirf `off` likh kar bhejein)*"
        )
        ask_msg = await query.message.reply(ask_text)
        
        try:
            user_input = await client.listen(query.message.chat.id, timeout=60)
            
            if user_input.text:
                # Agar user ko button delete karna hai
                if user_input.text.strip().lower() == 'off':
                    save_fn(auto_delete_button_text="", auto_delete_button_url="")
                    await user_input.reply("✅ **Button hata diya gaya hai!**")
                
                # Agar user ne Text aur URL diya hai
                elif "|" in user_input.text:
                    parts = user_input.text.split("|")
                    btn_text = parts[0].strip()
                    btn_url = parts[1].strip()
                    
                    # Link check karega ki asli hai ya nahi
                    if btn_url.startswith("http://") or btn_url.startswith("https://") or btn_url.startswith("t.me/"):
                        save_fn(auto_delete_button_text=btn_text, auto_delete_button_url=btn_url)
                        await user_input.reply(f"✅ **Button Set Ho Gaya!**\n\n**Text:** {btn_text}\n**Link:** {btn_url}")
                    else:
                        await user_input.reply("❌ **Invalid Link!** Link hamesha http, https ya t.me se shuru hona chahiye.")
                else:
                    await user_input.reply("❌ **Invalid Format!** Kripya `Text | Link` wala format use karein.")
                    
        except asyncio.TimeoutError:
            await ask_msg.edit("❌ **Time out!** Aapne reply karne me der kardi.")
        
        return await handle_auto_delete_callbacks(client, query, "master_auto_delete_menu", user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn)
