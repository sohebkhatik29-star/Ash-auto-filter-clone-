# © Telegram: @movies_1780
# Project branding: ASH FILE STORE & CLONE MANAGER

import asyncio
import aiohttp
from motor.motor_asyncio import AsyncIOMotorClient
from config import CLONE_DB_URI, CDB_NAME

client = AsyncIOMotorClient(CLONE_DB_URI)
db = client[CDB_NAME]
col = db["users"]

async def get_user(user_id):
    user_id = int(user_id)
    user = await col.find_one({"user_id": user_id})
    if not user:
        user = {
            "user_id": user_id,
            "shortener_api": None,
            "base_site": None,
            "verify_enabled": False,
            "verify_ttl": 86400,
        }
        await col.insert_one(user)
    return user

async def update_user_info(user_id, value: dict):
    await col.update_one({"user_id": int(user_id)}, {"$set": value}, upsert=True)

async def get_short_link(user, link):
    api_key = user.get("shortener_api")
    base_site = (user.get("base_site") or "").strip().rstrip("/")
    if not api_key or not base_site:
        return link

    if not base_site.startswith(("http://", "https://")):
        base_site = "https://" + base_site

    url = f"{base_site}/api"
    try:
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, params={"api": api_key, "url": link}) as response:
                if response.status != 200:
                    return link
                data = await response.json(content_type=None)
                if data.get("status") == "success":
                    return data.get("shortenedUrl") or data.get("shortened_url") or link
    except Exception:
        return link
    return link
