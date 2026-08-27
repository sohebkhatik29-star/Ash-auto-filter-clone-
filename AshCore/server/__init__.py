# Don't Remove Credit @movies_1780
# Subscribe YouTube Channel For Amazing Bot @tech_as_0
# Ask Doubt on telegram @movies_1780

from aiohttp import web
from .stream_routes import routes


async def web_server():
    web_app = web.Application(client_max_size=30000000)
    web_app.add_routes(routes)
    return web_app
