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
    b_cast = "✅" if adm.get("can_broadcast", False) else "❌"
    c_set = "✅" if adm.get("can_settings", False) else "❌"
    a_adm = "✅" if adm.get("can_add_admins", False) else "❌"
    d_bot = "✅" if adm.get("can_delete_bot", False) else "❌"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"📡 BROADCAST - {b_cast}", callback_data=f"adm_tgl:{target_uid}:can_broadcast")],
        [InlineKeyboardButton(f"⚙️ CLONE BOT SETTINGS - {c_set}", callback_data=f"adm_tgl:{target_uid}:can_settings")],
        [InlineKeyboardButton(f"👥 ADD ADMINS - {a_adm}", callback_data=f"adm_tgl:{target_uid}:can_add_admins")],
        [InlineKeyboardButton(f"❌ DELETE BOT - {d_bot}", callback_data=f"adm_tgl:{target_uid}:can_delete_bot")],
        [InlineKeyboardButton("🌐 TRANSFER CLONE OWNERSHIP", callback_data=f"adm_transfer:{target_uid}")],
        [InlineKeyboardButton("🗑️ REMOVE ADMIN", callback_data=f"adm_rem:{target_uid}")],
        [InlineKeyboardButton("🪧 BACK", callback_data="admins_menu")]
    ])

async def handle_admins_callbacks(client, query, data, user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn):
    me = client.me
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
        uname_str = f"@{uname}" if uname != "None" else "None"
        text = (
            "👥 <b>ADMINS:</b>\n\n"
            f"- <b>NAME:</b> {name}\n"
            f"- <b>USER ID:</b> <code>{target_uid}</code>\n"
            f"- <b>USERNAME:</b> {uname_str}\n\n"
            "<b>IF YOU ENABLE ALL SETTINGS WHICH IS GIVEN BELOW OF THIS ADMINS IT MEANS THIS ADMINS CAN DO EVERYTHING WHICH CAN DONE BY OWNER AND THIS ALSO HELP IF BY MISTAKE YOUR MAIN TELEGRAM ACCOUNT DELETED BUT ADMIN CAN NOT TRANSFER OWNERSHIP TO OTHER ADMIN ONLY OWNER CAN.</b>"
        )
        return await edit_or_reply_fn(query, text, reply_markup=single_admin_markup(adm, target_uid))

    if data.startswith("adm_tgl:"):
        parts = data.split(":")
        target_uid = int(parts[1])
        perm_key = parts[2]
        updated_adm = {}
        for a in adms:
            if int(a.get("user_id", 0)) == target_uid:
                a[perm_key] = not bool(a.get(perm_key, False))
                updated_adm = a
                break
        save_fn(admins=adms)
        r["admins"] = adms
        await query.answer()
        name = updated_adm.get("name") or updated_adm.get("first_name") or str(target_uid)
        uname = updated_adm.get("username") or "None"
        uname_str = f"@{uname}" if uname != "None" else "None"
        text = (
            "👥 <b>ADMINS:</b>\n\n"
            f"- <b>NAME:</b> {name}\n"
            f"- <b>USER ID:</b> <code>{target_uid}</code>\n"
            f"- <b>USERNAME:</b> {uname_str}\n\n"
            "<b>IF YOU ENABLE ALL SETTINGS WHICH IS GIVEN BELOW OF THIS ADMINS IT MEANS THIS ADMINS CAN DO EVERYTHING WHICH CAN DONE BY OWNER AND THIS ALSO HELP IF BY MISTAKE YOUR MAIN TELEGRAM ACCOUNT DELETED BUT ADMIN CAN NOT TRANSFER OWNERSHIP TO OTHER ADMIN ONLY OWNER CAN.</b>"
        )
        return await edit_or_reply_fn(query, text, reply_markup=single_admin_markup(updated_adm, target_uid))

    if data.startswith("adm_rem:"):
        target_uid = int(data.split(":")[1])
        adms = [a for a in adms if int(a.get("user_id", 0)) != target_uid]
        save_fn(admins=adms)
        r["admins"] = adms
        await query.answer("Admin removed successfully!")
        return await handle_admins_callbacks(client, query, "admins_menu", user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn)

    if data.startswith("adm_transfer:"):
        target_uid = int(data.split(":")[1])
        owner_uid = int(r.get("user_id", 0))
        if user_id != owner_uid:
            return await query.answer("❌ Only the bot owner can transfer ownership!", show_alert=True)
        adm = next((a for a in adms if int(a.get("user_id", 0)) == target_uid), {})
        name = adm.get("name") or adm.get("first_name") or str(target_uid)
        text = (
            "⚠️ <b>TRANSFER BOT OWNERSHIP</b>\n\n"
            f"<b>ARE YOU SURE YOU WANT TO TRANSFER THIS BOT OWNERSHIP TO {name} (<code>{target_uid}</code>)?</b>\n\n"
            "<i>Note: After transfer, you will no longer be the owner and only the new owner can manage ownership.</i>"
        )
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ YES, TRANSFER OWNERSHIP", callback_data=f"adm_do_transfer:{target_uid}")],
            [InlineKeyboardButton("🪧 BACK", callback_data=f"adm_manage:{target_uid}")]
        ])
        return await edit_or_reply_fn(query, text, reply_markup=markup)

    if data.startswith("adm_do_transfer:"):
        target_uid = int(data.split(":")[1])
        owner_uid = int(r.get("user_id", 0))
        if user_id != owner_uid:
            return await query.answer("❌ Only the bot owner can transfer ownership!", show_alert=True)
        adm = next((a for a in adms if int(a.get("user_id", 0)) == target_uid), {})
        name = adm.get("name") or adm.get("first_name") or str(target_uid)
        
        # New admin list: remove target_uid and add old owner as an admin
        new_adms = [a for a in adms if int(a.get("user_id", 0)) != target_uid]
        try:
            old_owner_obj = await client.get_users(owner_uid)
            old_name = old_owner_obj.first_name if old_owner_obj else str(owner_uid)
            old_uname = old_owner_obj.username if old_owner_obj else "None"
        except Exception:
            old_name = str(owner_uid)
            old_uname = "None"
        
        new_adms.append({
            "user_id": owner_uid,
            "name": old_name,
            "username": old_uname,
            "can_broadcast": True,
            "can_settings": True,
            "can_add_admins": True,
            "can_delete_bot": True
        })
        
        save_fn(user_id=target_uid, admins=new_adms)
        r["user_id"] = target_uid
        r["admins"] = new_adms
        await query.answer("Ownership transferred successfully!", show_alert=True)
        return await edit_or_reply_fn(
            query,
            f"👑 <b>OWNERSHIP TRANSFERRED SUCCESSFULLY TO {name}!</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🪧 BACK", callback_data="clone_my_clone_info")]])
        )

    if data == "adm_add":
        cancel_listeners_fn(client, user_id, user_id)
        sess_token = start_user_session(user_id, "add_admin")
        await query.answer()
        prompt_msg = await edit_or_reply_fn(
            query,
            "<b>NOW SEND ME USER ID</b>\n\n"
            "<b>FOR USER ID , TOLD THAT USER TO GIVE /id COMMAND IN THIS BOT TO GET THAT USER ID</b>\n\n"
            "<b>AND MAKE SURE YOUR ADMIN START THIS BOT ELSE YOU WILL GET ERROR THAT THIS IS NOT USER ID</b>\n\n"
            "/cancel - CANCEL THIS PROCESS",
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

            # Clean up prompt message from above so everything appears fresh at the bottom
            try:
                if prompt_msg:
                    await prompt_msg.delete()
                elif getattr(query, "message", None):
                    await query.message.delete()
            except Exception:
                pass

            inp = (ans.text or "").strip()
            if inp == "/cancel":
                clear_user_session(user_id)
                return await client.send_message(
                    chat_id=user_id,
                    text="❌ <b>Cancelled.</b>",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🪧 BACK", callback_data="admins_menu")]])
                )

            # Validate user ID / username and check if user has started the bot
            try:
                if inp.isdigit() or inp.lstrip("-").isdigit():
                    u_obj = await client.get_users(int(inp))
                else:
                    u_obj = await client.get_users(inp)
            except Exception:
                clear_user_session(user_id)
                return await client.send_message(
                    chat_id=user_id,
                    text=(
                        "❌ <b>THIS IS NOT USER ID OR USER NOT STARTED THIS BOT YET.</b>\n\n"
                        f"<i>Make sure the user has started @{me.username} and try again.</i>"
                    ),
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🪧 BACK", callback_data="admins_menu")]])
                )

            existing = next((a for a in adms if int(a.get("user_id", 0)) == u_obj.id), None)
            if not existing:
                adms.append({
                    "user_id": u_obj.id,
                    "name": u_obj.first_name or str(u_obj.id),
                    "username": u_obj.username or "None",
                    "can_broadcast": False,
                    "can_settings": False,
                    "can_add_admins": False,
                    "can_delete_bot": False
                })
            else:
                existing["name"] = u_obj.first_name or existing.get("name")
                existing["username"] = u_obj.username or existing.get("username")
            
            save_fn(admins=adms)
            r["admins"] = adms
            clear_user_session(user_id)
            return await client.send_message(
                chat_id=user_id,
                text="<b>SUCCESSFULLY UPDATED</b>",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🪧 BACK", callback_data="admins_menu")]])
            )

        asyncio.create_task(_adm_worker())
        return

