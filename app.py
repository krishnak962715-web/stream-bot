import os
import re
import math
import logging
from aiohttp import web
from pyrogram import Client, filters

logging.basicConfig(level=logging.INFO)

# Environment Variables
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
BIN_CHANNEL = int(os.environ.get("BIN_CHANNEL", 0))
PORT = int(os.environ.get("PORT", 8080))

# Initialize Bot
bot = Client("StreamBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, in_memory=True)

# Helper function streaming chunk
class ByteStreamer:
    def __init__(self, client, message):
        self.client = client
        self.message = message
    
    async def yield_file(self, offset, limit):
        async for chunk in self.client.stream_media(self.message, limit=limit, offset=offset):
            yield chunk

# Web Server Handler (Jo Video stream karega)
async def stream_handler(request):
    try:
        message_id = int(request.match_info.get("message_id"))
        msg = await bot.get_messages(BIN_CHANNEL, message_id)
        
        if not msg or not msg.media:
            return web.Response(status=404, text="Video Not Found")
        
        media_type = msg.media.value
        media = getattr(msg, media_type)
        file_size = getattr(media, "file_size", 0)
        mime_type = getattr(media, "mime_type", "video/mp4")

        headers = {
            "Content-Type": mime_type,
            "Accept-Ranges": "bytes",
            "Access-Control-Allow-Origin": "*",  # Yahi wo jadoo hai jo website par video chalayega!
            "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
            "Access-Control-Allow-Headers": "Range, Content-Type"
        }

        if request.method == "OPTIONS":
            return web.Response(headers=headers)

        range_header = request.headers.get("Range", 0)
        
        if range_header:
            range_match = re.search(r'bytes=(\d+)-(\d*)', range_header)
            offset = int(range_match.group(1)) if range_match else 0
            end = int(range_match.group(2)) if range_match and range_match.group(2) else file_size - 1
            limit = end - offset + 1
            
            headers["Content-Range"] = f"bytes {offset}-{end}/{file_size}"
            headers["Content-Length"] = str(limit)
            
            response = web.StreamResponse(status=206, headers=headers)
            await response.prepare(request)
            
            streamer = ByteStreamer(bot, msg)
            async for chunk in streamer.yield_file(offset, limit):
                await response.write(chunk)
            
            return response
        else:
            headers["Content-Length"] = str(file_size)
            response = web.StreamResponse(status=200, headers=headers)
            await response.prepare(request)
            
            streamer = ByteStreamer(bot, msg)
            async for chunk in streamer.yield_file(0, file_size):
                await response.write(chunk)
                
            return response

    except Exception as e:
        logging.error(f"Error: {e}")
        return web.Response(status=500, text="Internal Server Error")

# Telegram Bot Handlers
@bot.on_message(filters.private & filters.command("start"))
async def start_cmd(client, message):
    await message.reply_text("👋 Hello! Send me any video and I will give you a direct stream link.")

@bot.on_message(filters.private & filters.media)
async def media_cmd(client, message):
    try:
        sent_msg = await message.copy(BIN_CHANNEL)
        host = os.environ.get("RENDER_EXTERNAL_HOSTNAME", f"localhost:{PORT}")
        stream_link = f"https://{host}/stream/{sent_msg.id}"
        await message.reply_text(f"🔗 **Your Direct Stream Link:**\n\n`{stream_link}`")
    except Exception as e:
        await message.reply_text(f"Error: {e}")

# Start Server
async def web_server():
    app = web.Application()
    app.router.add_get("/", lambda r: web.Response(text="Bot is running!"))
    app.router.add_route("*", "/stream/{message_id}", stream_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logging.info("Web Server Started")

async def main():
    await bot.start()
    await web_server()
    logging.info("Bot is active")
    await pyrogram.idle()

if __name__ == "__main__":
    import asyncio
    import pyrogram
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
