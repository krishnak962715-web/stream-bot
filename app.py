import os
import logging
import asyncio
from aiohttp import web
from pyrogram import Client, filters

logging.basicConfig(level=logging.INFO)

API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
BIN_CHANNEL = int(os.environ.get("BIN_CHANNEL", 0))
PORT = int(os.environ.get("PORT", 8080))

# Pyrogram Bot Client
bot = Client(
    "AllNetflixBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    in_memory=True
)

class Streamer:
    async def stream_handler(self, request):
        try:
            msg_id = int(request.match_info['message_id'])
            msg = await bot.get_messages(BIN_CHANNEL, msg_id)
            
            if not msg or not msg.media:
                return web.Response(status=404, text="File Not Found")
            
            media_type = msg.media.value
            media = getattr(msg, media_type)
            file_size = getattr(media, "file_size", 0)
            mime_type = getattr(media, 'mime_type', 'video/mp4')
            
            headers = {
                "Content-Type": mime_type,
                "Accept-Ranges": "bytes",
            }
            
            range_header = request.headers.get("Range")
            offset = 0
            limit = file_size
            status = 200
            
            if range_header:
                range_match = range_header.replace("bytes=", "").split("-")
                offset = int(range_match[0]) if range_match[0] else 0
                end = int(range_match[1]) if len(range_match) > 1 and range_match[1] else file_size - 1
                limit = end - offset + 1
                status = 206
                headers["Content-Range"] = f"bytes {offset}-{end}/{file_size}"
                
            headers["Content-Length"] = str(limit)
            
            response = web.StreamResponse(status=status, headers=headers)
            await response.prepare(request)
            
            async for chunk in bot.stream_media(msg, limit=limit, offset=offset):
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

async def web_server():
    app = web.Application()
    app.router.add_get("/", lambda r: web.Response(text="ALL NETFLIX STREAMING SERVER IS ALIVE!"))
    app.router.add_get("/stream/{message_id}", streamer.stream_handler)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logging.info(f"Web Server started and listening on port {PORT}")

# Fix applied here: async def main()
async def main():
    await bot.start()
    logging.info("Telegram Bot Started Successfully!")
    await web_server()
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
