import os
import logging
import asyncio

# --- EVENT LOOP FIX ---
try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())
# ----------------------

from aiohttp import web
from pyrogram import Client, filters

logging.basicConfig(level=logging.INFO)

API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
BIN_CHANNEL = int(os.environ.get("BIN_CHANNEL", 0))
PORT = int(os.environ.get("PORT", 8080))

bot = Client("AllNetflixBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

class Streamer:
    async def stream_handler(self, request):
        try:
            msg_id = int(request.match_info['message_id'])
            msg = await bot.get_messages(BIN_CHANNEL, msg_id)
            if not msg or not getattr(msg, msg.media.value):
                return web.Response(status=404, text="File Not Found")
            
            media = getattr(msg, msg.media.value)
            file_size = media.file_size
            
            headers = {
                "Content-Type": getattr(media, 'mime_type', 'video/mp4'),
                "Accept-Ranges": "bytes",
            }
            
            range_header = request.headers.get("Range")
            if range_header:
                from_bytes, to_bytes = range_header.replace("bytes=", "").split("-")
                from_bytes = int(from_bytes)
                to_bytes = int(to_bytes) if to_bytes else file_size - 1
                headers["Content-Range"] = f"bytes {from_bytes}-{to_bytes}/{file_size}"
                headers["Content-Length"] = str(to_bytes - from_bytes + 1)
                
                response = web.StreamResponse(status=206, headers=headers)
                await response.prepare(request)
                
                offset = from_bytes
                limit = to_bytes - from_bytes + 1
                
                async for chunk in bot.stream_media(msg, offset=offset, limit=limit):
                    await response.write(chunk)
                return response
            else:
                headers["Content-Length"] = str(file_size)
                response = web.StreamResponse(status=200, headers=headers)
                await response.prepare(request)
                async for chunk in bot.stream_media(msg):
                    await response.write(chunk)
                return response
        except Exception as e:
            logging.error(e)
            return web.Response(status=500, text="Internal Server Error")

streamer = Streamer()

@bot.on_message(filters.private & filters.command("start"))
async def start_cmd(c, m):
    await m.reply_text("Welcome to **ALL NETFLIX** Stream Bot! 🎬\n\nSend me any Video, and I will generate a direct high-speed streaming link for your website.")

@bot.on_message(filters.private & filters.media)
async def media_recv(c, m):
    sent_msg = await m.copy(BIN_CHANNEL)
    host = os.environ.get("RENDER_EXTERNAL_HOSTNAME", f"localhost:{PORT}")
    stream_link = f"https://{host}/stream/{sent_msg.id}"
    await m.reply_text(f"✅ **Stream Link Generated!**\n\n**Link:** `{stream_link}`\n\nCopy and paste this link into your Firebase Database.")

async def start_services():
    await bot.start()
    app = web.Application()
    app.router.add_get("/", lambda r: web.Response(text="ALL NETFLIX STREAMING SERVER IS ALIVE!"))
    app.router.add_get("/stream/{message_id}", streamer.stream_handler)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logging.info(f"Web Server started on port {PORT}")
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(start_services())
