# 📢 CLONE POST MANAGER: /addpost, /delpost, /delallpost
import asyncio
import time
import secrets
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery
from pyrogram.errors import InputUserDeactivated, UserIsBlocked, FloodWait, PeerIdInvalid
from clone_plugins.dbusers import clonedb
from clone_plugins.auth import is_clone_authorized, UNAUTHORIZED_MESSAGE_TEXT, unauthorized_markup

POST_CACHE = {}

def get_db():
    try:
        from plugins.clone import mongo_db
        return mongo_db
    except Exception:
        return None

def sync_save_post_record(client, record_doc):
    bot_id = int(client.me.id)
    for k in (bot_id, str(bot_id)):
        POST_CACHE.setdefault(k, []).append(dict(record_doc))
        if len(POST_CACHE[k]) > 100:
            POST_CACHE[k].pop(0)

    db = get_db()
    if db is not None:
        try:
            db[f"clone_posts_{bot_id}"].insert_one(dict(record_doc))
            db["clone_posts"].insert_one(dict(record_doc))
        except Exception as e:
            print(f"Error saving to mongo_db clone_posts: {e}")

async def async_save_post_record(client, record_doc):
    sync_save_post_record(client, record_doc)
    bot_id = int(client.me.id)
    try:
        await clonedb.db[f"clone_posts_{bot_id}"].insert_one(dict(record_doc))
    except Exception as e:
        print(f"Error saving to clonedb clone_posts_{bot_id}: {e}")
    try:
        await clonedb.db["clone_posts"].insert_one(dict(record_doc))
    except Exception as e:
        print(f"Error saving to clonedb clone_posts: {e}")

async def find_post_record(client, chat_id, reply_msg):
    reply_id = int(reply_msg.id)
    raw_text = getattr(reply_msg, 'text', None) or getattr(reply_msg, 'caption', None) or ''
    reply_text = str(raw_text).strip() if raw_text else ''
    bot_id = int(client.me.id)

    # 1. In-memory cache
    for k in (bot_id, str(bot_id)):
        for rec in reversed(POST_CACHE.get(k, [])):
            if reply_id in rec.get("all_msg_ids", []):
                return rec
            if rec.get("source_msg_id") == reply_id or rec.get("owner_copy_id") == reply_id:
                return rec
            if rec.get("user_messages", {}).get(str(chat_id)) == reply_id:
                return rec
            if reply_text and rec.get("text") and (reply_text == rec.get("text") or reply_text in rec.get("text") or rec.get("text") in reply_text):
                return rec

    query_filter = {
        "$or": [
            {"all_msg_ids": reply_id},
            {"source_msg_id": reply_id},
            {"owner_copy_id": reply_id},
            {f"user_messages.{chat_id}": reply_id}
        ]
    }

    # 2. Synchronous MongoDB
    db = get_db()
    if db is not None:
        try:
            for col_name in (f"clone_posts_{bot_id}", "clone_posts"):
                col = db[col_name]
                q = dict(query_filter)
                if col_name == "clone_posts":
                    q["bot_id"] = bot_id
                rec = col.find_one(q, sort=[("created_at", -1)])
                if rec:
                    return rec
                if reply_text:
                    t_q = {"text": reply_text}
                    if col_name == "clone_posts":
                        t_q["bot_id"] = bot_id
                    rec = col.find_one(t_q, sort=[("created_at", -1)])
                    if rec:
                        return rec
        except Exception as e:
            print(f"Error checking mongo_db clone_posts: {e}")

    # 3. Async clonedb
    try:
        for col_name in (f"clone_posts_{bot_id}", "clone_posts"):
            col = clonedb.db[col_name]
            q = dict(query_filter)
            if col_name == "clone_posts":
                q["bot_id"] = bot_id
            rec = await col.find_one(q, sort=[("created_at", -1)])
            if rec:
                return rec
            if reply_text:
                t_q = {"text": reply_text}
                if col_name == "clone_posts":
                    t_q["bot_id"] = bot_id
                rec = await col.find_one(t_q, sort=[("created_at", -1)])
                if rec:
                    return rec
    except Exception as e:
        print(f"Error checking clonedb clone_posts: {e}")

    # 4. Fallback to latest post in cache
    for k in (bot_id, str(bot_id)):
        c_list = POST_CACHE.get(k, [])
        if c_list:
            return c_list[-1]

    return None

async def remove_post_record(client, record):
    bot_id = int(client.me.id)
    for k in (bot_id, str(bot_id)):
        c_list = POST_CACHE.get(k, [])
        if record in c_list:
            try:
                c_list.remove(record)
            except Exception:
                pass
    rec_id = record.get("_id")
    post_id = record.get("post_id")
    del_query = {"_id": rec_id} if rec_id else ({"post_id": post_id} if post_id else None)
    if del_query:
        db = get_db()
        if db is not None:
            try:
                db[f"clone_posts_{bot_id}"].delete_one(del_query)
                db["clone_posts"].delete_one(del_query)
            except Exception:
                pass
        try:
            await clonedb.db[f"clone_posts_{bot_id}"].delete_one(del_query)
            await clonedb.db["clone_posts"].delete_one(del_query)
        except Exception:
            pass

async def get_all_post_records(client):
    bot_id = int(client.me.id)
    records = []
    seen_ids = set()

    # 1. From cache
    for k in (bot_id, str(bot_id)):
        for rec in POST_CACHE.get(k, []):
            pid = rec.get("post_id") or str(rec.get("_id", ""))
            if pid and pid not in seen_ids:
                seen_ids.add(pid)
                records.append(rec)

    # 2. From clonedb
    try:
        cursor = clonedb.db[f"clone_posts_{bot_id}"].find({})
        async for doc in cursor:
            pid = doc.get("post_id") or str(doc.get("_id", ""))
            if pid and pid not in seen_ids:
                seen_ids.add(pid)
                records.append(doc)
    except Exception as e:
        print(f"Error fetching from clonedb: {e}")

    return records

async def clear_all_post_records(client):
    bot_id = int(client.me.id)
    for k in (bot_id, str(bot_id)):
        POST_CACHE[k] = []
    db = get_db()
    if db is not None:
        try:
            db[f"clone_posts_{bot_id}"].delete_many({})
            db["clone_posts"].delete_many({"bot_id": bot_id})
        except Exception:
            pass
    try:
        await clonedb.db[f"clone_posts_{bot_id}"].delete_many({})
        await clonedb.db["clone_posts"].delete_many({"bot_id": bot_id})
    except Exception:
        pass


# -------------------------------------------------------------------------- #
# 1. ADD POST (/addpost, /add_post, /post)                                    #
# -------------------------------------------------------------------------- #
async def add_post_cmd(client: Client, message: Message):
    user_id = message.from_user.id if message.from_user else None
    if not user_id or not is_clone_authorized(client, user_id):
        return await message.reply(
            UNAUTHORIZED_MESSAGE_TEXT,
            reply_markup=unauthorized_markup(client),
            disable_web_page_preview=True
        )

    b_msg = message.reply_to_message
    if not b_msg:
        try:
            b_msg = await client.ask(
                chat_id=user_id,
                text="📝 <b>Now Send or Forward Me Your Post Message:</b>\n\n(Send /cancel to abort)",
                timeout=300
            )
            if not b_msg or (not b_msg.text and not b_msg.media):
                return await message.reply("❌ <b>Invalid message. Post cancelled.</b>")
            if getattr(b_msg, 'text', '') == "/cancel":
                return await message.reply("❌ <b>Post cancelled.</b>")
        except Exception:
            return await message.reply("❌ <b>Post cancelled or timed out.</b>")

    sts = await message.reply("⏳ <b>Broadcasting post to all users...</b>")
    sent = 0
    failed = 0
    total_users = await clonedb.total_users_count(client.me.id)
    user_messages = {}
    owner_copy_id = None

    users = await clonedb.get_all_users(client.me.id)
    async for u in users:
        uid = u.get("user_id")
        if not uid or u.get("banned") is True:
            continue
        try:
            # DO NOT PIN THE MESSAGE (as per requirement)
            m = await b_msg.copy(chat_id=uid)
            user_messages[str(uid)] = int(m.id)
            if int(uid) == int(message.chat.id):
                owner_copy_id = int(m.id)
            sent += 1
        except FloodWait as e:
            await asyncio.sleep(e.value)
            try:
                m = await b_msg.copy(chat_id=uid)
                user_messages[str(uid)] = int(m.id)
                if int(uid) == int(message.chat.id):
                    owner_copy_id = int(m.id)
                sent += 1
            except Exception:
                failed += 1
        except (InputUserDeactivated, UserIsBlocked, PeerIdInvalid):
            failed += 1
        except Exception:
            failed += 1

        if (sent + failed) % 20 == 0:
            try:
                await sts.edit(
                    f"⏳ <b>Post Delivery in progress:</b>\n\n"
                    f"👥 Total Users: <code>{total_users}</code>\n"
                    f"🔄 Progress: <code>{sent + failed}</code> / <code>{total_users}</code>\n"
                    f"✅ Sent: <code>{sent}</code>\n"
                    f"❌ Failed: <code>{failed}</code>"
                )
            except Exception:
                pass
        await asyncio.sleep(0.04)

    # Save record for /delpost and /delallpost
    try:
        source_id = int(getattr(b_msg, 'id', None) or getattr(b_msg, 'message_id', None) or 0)
        raw_text = getattr(b_msg, 'text', None) or getattr(b_msg, 'caption', None) or ''
        text_content = str(raw_text).strip() if raw_text else ''

        all_ids = []
        if source_id:
            all_ids.append(source_id)
        if owner_copy_id:
            all_ids.append(owner_copy_id)
        for u_k, u_v in user_messages.items():
            all_ids.append(int(u_v))
        all_ids = list(set(all_ids))

        post_id = f"post_{int(time.time())}_{secrets.token_hex(4)}"
        record_doc = {
            "post_id": post_id,
            "bot_id": int(client.me.id),
            "owner_id": int(user_id),
            "source_msg_id": source_id,
            "owner_copy_id": owner_copy_id,
            "text": text_content,
            "created_at": time.time(),
            "sent_count": sent,
            "user_messages": user_messages,
            "all_msg_ids": all_ids,
        }
        await async_save_post_record(client, record_doc)
    except Exception as e:
        print(f"Error recording post: {e}")

    try:
        await sts.edit(
            f"✅ <b>Post Successfully Sent to All Users!</b>\n\n"
            f"👥 Total Users: <code>{total_users}</code>\n"
            f"✅ Delivered: <code>{sent}</code>\n"
            f"❌ Failed / Blocked: <code>{failed}</code>\n\n"
            f"💡 <i>To delete this post later from all users, reply to it with <code>/delpost</code></i>"
        )
    except Exception:
        pass


# -------------------------------------------------------------------------- #
# 2. DEL POST (/delpost, /del_post, /delposts)                                 #
# -------------------------------------------------------------------------- #
async def del_post_cmd(client: Client, message: Message):
    user_id = message.from_user.id if message.from_user else None
    if not user_id or not is_clone_authorized(client, user_id):
        return await message.reply(
            UNAUTHORIZED_MESSAGE_TEXT,
            reply_markup=unauthorized_markup(client),
            disable_web_page_preview=True
        )

    reply = message.reply_to_message
    if not reply:
        return await message.reply(
            "⚠️ <b>Please reply to the post you want to delete!</b>\n\n"
            "<i>Jis post ko aapne /addpost se bheja tha, us post ke reply me <code>/delpost</code> command bhejein.</i>"
        )

    record = await find_post_record(client, message.chat.id, reply)
    if not record:
        return await message.reply("❌ <b>Post record not found or already deleted.</b>")

    sts = await message.reply("⏳ <b>Deleting post from all users... Please wait.</b>")
    user_msgs = record.get("user_messages", {})
    deleted = 0
    failed = 0

    for uid_str, mid in user_msgs.items():
        try:
            uid = int(uid_str)
            await client.delete_messages(chat_id=uid, message_ids=int(mid))
            deleted += 1
        except FloodWait as e:
            await asyncio.sleep(e.value)
            try:
                await client.delete_messages(chat_id=int(uid_str), message_ids=int(mid))
                deleted += 1
            except Exception:
                failed += 1
        except Exception:
            failed += 1

        if (deleted + failed) % 25 == 0:
            await asyncio.sleep(0.05)

    await remove_post_record(client, record)

    try:
        await sts.edit(
            f"🗑️ <b>Post Successfully Deleted From All Users!</b>\n\n"
            f"👥 Deleted from: <code>{deleted}</code> users' chats."
        )
    except Exception:
        pass


# -------------------------------------------------------------------------- #
# 3. DEL ALL POSTS (/delallpost, /del_all_post, /delallposts)                 #
# -------------------------------------------------------------------------- #
async def del_all_posts_cmd(client: Client, message: Message):
    user_id = message.from_user.id if message.from_user else None
    if not user_id or not is_clone_authorized(client, user_id):
        return await message.reply(
            UNAUTHORIZED_MESSAGE_TEXT,
            reply_markup=unauthorized_markup(client),
            disable_web_page_preview=True
        )

    markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ YES, DELETE ALL POSTS", callback_data="clone_del_all_posts_confirm"),
            InlineKeyboardButton("❌ NO, CANCEL", callback_data="clone_del_all_posts_cancel")
        ]
    ])
    await message.reply(
        "⚠️ <b>CONFIRM DELETE ALL POSTS:</b>\n\n"
        "Are you sure you want to delete <b>ALL</b> posts ever sent by this bot to all users?\n\n"
        "<i>Yeh command bot dwara bhejhe gaye sabhi posts ko sabhi users ke pass se delete kar degi!</i>",
        reply_markup=markup
    )

async def handle_del_all_posts_callback(client: Client, query: CallbackQuery):
    user_id = query.from_user.id if query.from_user else None
    if not user_id or not is_clone_authorized(client, user_id):
        return await query.answer("⚠️ You are not authorized!", show_alert=True)

    if query.data == "clone_del_all_posts_cancel":
        await query.answer("Cancelled!")
        try:
            await query.message.edit_text("❌ <b>Delete all posts cancelled.</b>")
        except Exception:
            pass
        return

    if query.data == "clone_del_all_posts_confirm":
        await query.answer("Deleting all posts...", show_alert=False)
        try:
            await query.message.edit_text("⏳ <b>Deleting ALL posts from all users... Please wait.</b>")
        except Exception:
            pass

        records = await get_all_post_records(client)
        if not records:
            try:
                await query.message.edit_text("ℹ️ <b>No posts found to delete.</b>")
            except Exception:
                pass
            return

        total_posts = len(records)
        total_messages_deleted = 0

        for rec in records:
            user_msgs = rec.get("user_messages", {})
            for uid_str, mid in user_msgs.items():
                try:
                    await client.delete_messages(chat_id=int(uid_str), message_ids=int(mid))
                    total_messages_deleted += 1
                except FloodWait as e:
                    await asyncio.sleep(e.value)
                    try:
                        await client.delete_messages(chat_id=int(uid_str), message_ids=int(mid))
                        total_messages_deleted += 1
                    except Exception:
                        pass
                except Exception:
                    pass

        await clear_all_post_records(client)

        try:
            await query.message.edit_text(
                f"✅ <b>All Posts Have Been Successfully Deleted!</b>\n\n"
                f"🗑️ Total Posts Deleted: <code>{total_posts}</code>\n"
                f"💬 Total Messages Removed: <code>{total_messages_deleted}</code>"
            )
        except Exception:
            pass
