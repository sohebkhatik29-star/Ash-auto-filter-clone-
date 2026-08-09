from pyrogram import Client, types
from config import *
from typing import Union, Optional, AsyncGenerator
from aiohttp import web

class StreamXBot(Client):

    def __init__(self):
        super().__init__(
            name="ashfiletolink",
            api_id=API_ID,
            api_hash=API_HASH,
            bot_token=BOT_TOKEN,
            workers=150,
            plugins={"root": "plugins"},
            sleep_threshold=5,
        )

    async def iter_messages(
        self,
        chat_id: Union[int, str],
        limit: int,
        offset: int = 0,
    ) -> Optional[AsyncGenerator["types.Message", None]]:
        """Iterate through a chat sequentially."""
        current = offset
        while True:
            new_diff = min(200, limit - current)
            if new_diff <= 0:
                return
            messages = await self.get_messages(chat_id, list(range(current, current + new_diff + 1)))
            for message in messages:
                yield message
                current += 1

StreamBot = StreamXBot()

multi_clients = {}
work_loads = {}
