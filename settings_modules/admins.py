# 👥 ADMINS SETTINGS MODULE
import asyncio
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from clone_plugins.sessions import start_user_session, is_user_session_active, clear_user_session

def admins_menu_markup(adms):
    rows = []
    for a in adms:
        name = a.get("name") or a.get("first_name") or str(a.get("user_id"))
        uid = a.get("user_id")
        rows.append([InlineKeyboardButton(f"{name}", callback_data=f"adm_manage:{uid}")])
    rows.append([InlineKeyboardButton("➕ ADD ADMIN ➕", callback_data="adm_add")])
    rows.append([InlineKeyboardButton("🪧 BACK", callback_data="clone_my_clone_info")])
    return InlineKeyboardMarkup(rows)

def single_admin_markup(adm, target_uid):
    b_cast = "✅" if adm.get("can_broadcast", True) else "❌"
    c_set = "✅" if adm.get("can_settings", True) else "❌"
    a_adm = "✅" if adm.get("can_add_admins", False) else "❌"
    d_bot = "✅" if adm.get("can_delete_bot", False) else "❌"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"📢 BROADCAST - {b_cast}", callback_data=f"adm_tgl:{target_uid}:can_broadcast")],
        [InlineKeyboardButton(f"⚙️ CLONE BOT SETTINGS - {c_set}", callback_data=f"adm_tgl:{target_uid}:can_settings")],
        [InlineKeyboardButton(f"👥 ADD ADMINS - {a_adm}", callback_data=f"adm_tgl:{target_uid}:can_add_admins")],
        [InlineKeyboardButton(f"🚫 DELETE BOT - {d_bot}", callback_data=f"adm_tgl:{target_uid}:can_delete_bot")],
        [InlineKeyboardButton("🗑️ REMOVE ADMIN", callback_data=f"adm_rem:{target_uid}")],
        [InlineKeyboardButton("🪧 BACK", callback_data="admins_menu")]
    ])

async def handle_admins_callbacks(client, query, data, user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn):
    raw_adms = r.get("admins", [])
    if isinstance(raw_adms, dict):
        adms = list(raw_adms.values())
    elif isinstance(raw_adms, list):
        adms = list(raw_adms)
    else:
        adms = []

    if data == "admins_menu":
        text = (
            "👥 <b>ADMINS:</b>\n\n"
            "<b>YOU CAN CHANGE WHAT ADMINS CAN USE OR NOT BY CLICKING ON ADMIN NAME BUTTON.</b>\n\n"
            "<b>YOU CAN CUSTOMISE FOLLOWING ADMINS SETTINGS:</b>\n\n"
            "- <b>CAN DO BROADCAST</b>\n"
            "- <b>CAN USE CLONE BOT CUSTOMISATION</b>\n"
            "- <b>CAN ADD ADMINS OR CHANGE ADMIN SETTINGS</b>\n"
            "- <b>CAN DELETE BOT</b>\n\n"
            "<b>YOU CAN CUSTOMISE THE EACH ADMIN SETTINGS THAT WHAT THEY CAN USE OR WHAT THEY CAN NOT USE.</b>"
        )
        return await edit_or_reply_fn(query, text, reply_markup=admins_menu_markup(adms))

    if data.startswith("adm_manage:"):
        target_uid = int(data.split(":")[1])
        adm = next((a for a in adms if int(a.get("user_id", 0)) == target_uid), {})
        name = adm.get("name") or adm.get("first_name") or str(target_uid)
        uname = adm.get("username") or "None"
        text = (
            f"- <b>NAME:</b> {name}\n"
            f"- <b>USER ID:</b> <code>{target_uid}</code>\n"
            f"- <b>USERNAME:</b> @{uname}\n\n"
            "<b>IF YOU ENABLE ALL SETTINGS WHICH IS GIVEN BELOW OF THIS ADMINS IT MEANS THIS ADMINS CAN DO EVERYTHING WHICH CAN DONE BY OWNER AND THIS ALSO HELP IF BY MISTAKE YOUR TELEGRAM ACCOUNT DELETED BUT ADMIN CAN NOT TRANSFER OWNERSHIP TO OTHER ADMIN ONLY OWNER CAN.</b>"
        )
        return await edit_or_reply_fn(query, text, reply_markup=single_admin_markup(adm, target_uid))

    if data.startswith("adm_tgl:"):
        parts = data.split(":")
        target_uid = int(parts[1])
        perm_key = parts[2]
        updated_adm = {}
        for a in adms:
            if int(a.get("user_id", 0)) == target_uid:
                a[perm_key] = not bool(a.get(perm_key, True if perm_key in ("can_broadcast", "can_settings") else False))
                updated_adm = a
                break
        save_fn(admins=adms)
        await query.answer("Permission updated!")
        return await edit_or_reply_fn(query, query.message.text.html if query.message.text else "👥 <b>ADMIN PERMISSIONS:</b>", reply_markup=single_admin_markup(updated_adm, target_uid))

    if data.startswith("adm_rem:"):
        target_uid = int(data.split(":")[1])
        adms = [a for a in adms if int(a.get("user_id", 0)) != target_uid]
        save_fn(admins=adms)
        await query.answer("Admin removed successfully!")
        return await handle_admins_callbacks(client, query, "admins_menu", user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn)

    if data == "adm_add":
        cancel_listeners_fn(client, user_id, user_id)
        sess_token = start_user_session(user_id, "add_admin")
        await query.answer()
        await edit_or_reply_fn(
            query,
            "<b>SEND USER ID OR USERNAME OF USER YOU WANT TO MAKE ADMIN.</b>\n\n/cancel - CANCEL THIS PROCESS.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🪧 BACK", callback_data="admins_menu")]])
        )
        async def _adm_worker():
            try:
                ans = await client.listen(chat_id=user_id, timeout=120)
            except Exception:
                await client.send_message(user_id, "❌ <b>Timeout. Process cancelled.</b>")
                clear_user_session(user_id)
                return
            if not is_user_session_active(user_id, sess_token):
                return
            inp = (ans.text or "").strip()
            clear_user_session(user_id)
            if inp == "/cancel":
                return await client.send_message(chat_id=user_id, text="❌ <b>Cancelled.</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🪧 BACK", callback_data="admins_menu")]]) )
            try:
                u_obj = await client.get_users(inp)
                if not any(int(a.get("user_id", 0)) == u_obj.id for a in adms):
                    adms.append({
                        "user_id": u_obj.id,
                        "name": u_obj.first_name,
                        "username": u_obj.username,
                        "can_broadcast": True,
                        "can_settings": True,
                        "can_add_admins": False,
                        "can_delete_bot": False
                    })
                    save_fn(admins=adms)
                return await client.send_message(
                    chat_id=user_id,
                    text=f"✅ <b>Successfully added {u_obj.first_name} as Admin!</b>",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🪧 BACK", callback_data="admins_menu")]])
                )
            except Exception as e:
                return await client.send_message(
                    chat_id=user_id,
                    text=f"❌ <b>Error adding admin:</b> <code>{e}</code>",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🪧 BACK", callback_data="admins_menu")]])
                )
        asyncio.create_task(_adm_worker())
        return
