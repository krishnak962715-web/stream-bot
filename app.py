import os
import logging
import asyncio

# Naya Event Loop
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

import aiohttp
from aiohttp import web
from pyrogram import Client, filters

logging.basicConfig(level=logging.INFO)

API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
BIN_CHANNEL = int(os.environ.get("BIN_CHANNEL", 0))
PORT = int(os.environ.get("PORT", 8080))

bot = Client("AllNetflixBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, in_memory=True)

class Streamer:
    async def stream_handler(self, request):
        try:
            msg_id = int(request.match_info['message_id'])
            msg = await bot.get_messages(BIN_CHANNEL, msg_id)
            if not msg or not getattr(msg, msg.media.value):
                return web.Response(status=404, text="File Not Found")
            
            media = getattr(msg, msg.media.value)
            file_size = getattr(media, "file_size", 0)
            mime_type = getattr(media, 'mime_type', 'video/mp4')
            
            # Telegram se direct file ka path nikalenge
            file_info = await bot.get_file(media.file_id)
            file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_info.file_path}"
            
            req_headers = {}
            range_header = request.headers.get("Range")
            if range_header:
                req_headers["Range"] = range_header
            
            async with aiohttp.ClientSession() as session:
                async with session.get(file_url, headers=req_headers) as resp:
                    if resp.status not in [200, 206]:
                        return web.Response(status=resp.status, text="Error fetching from Telegram")
                    
                    response_headers = {
                        "Content-Type": mime_type,
                        "Accept-Ranges": "bytes",
                        "Content-Length": resp.headers.get("Content-Length", str(file_size)),
                    }
                    if "Content-Range" in resp.headers:
                        response_headers["Content-Range"] = resp.headers["Content-Range"]
                    
                    response = web.StreamResponse(status=resp.status, headers=response_headers)
                    await response.prepare(request)
                    
                    async for chunk in resp.content.iter_chunked(1024 * 64):
                        await response.write(chunk)
                    return response
        except Exception as e:
            logging.error(f"Stream Error: {e}")
            return web.Response(status=500, text=f"Internal Server Error: {e}")

streamer = Streamer()

@bot.on_message(filters.private & filters.command("start"))
async def start_cmd(c, m):
    await m.reply_text("Welcome to **ALL NETFLIX** Stream Bot! 🎬\n\nSend me any Video, and I will generate a direct high-speed streaming link for your website.")

@bot.on_message(filters.private & filters.media)
async def media_recv(c, m):
    try:
        sent_msg = await m.copy(BIN_CHANNEL)
        host = os.environ.get("RENDER_EXTERNAL_HOSTNAME", f"localhost:{PORT}")
        stream_link = f"https://{host}/stream/{sent_msg.id}"
        await m.reply_text(f"✅ **Stream Link Generated!**\n\n**Link:** `{stream_link}`\n\nCopy and paste this link into your website/database.")
    except Exception as e:
        await m.reply_text(f"⚠️ **Error:** {e}")

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
    loop.run_until_complete(start_services())
