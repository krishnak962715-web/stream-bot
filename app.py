import os
import re
import math
import logging
import asyncio
import pyrogram
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

# ====================================================
# 🔴 MASTERSTROKE 1: BROWSER SECURITY BYPASS (CORS) 🔴
# ====================================================
@web.middleware
async def cors_middleware(request, handler):
    if request.method == 'OPTIONS':
        response = web.Response(status=200)
    else:
        try:
            response = await handler(request)
        except web.HTTPException as ex:
            response = ex
        except Exception as e:
            return web.Response(status=500, text=str(e))
            
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, HEAD, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Range'
    return response

# ====================================================
# WATCH ROUTE: DIRECT WEB PLAYER SCREEN
# ====================================================
async def watch_handler(request):
    try:
        message_id = int(request.match_info.get("message_id"))
        host = request.host
        
        html_page = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Video Player</title>
            <link rel="stylesheet" href="https://cdn.plyr.io/3.7.8/plyr.css" />
            <style>
                body {{ background-color: #000; margin: 0; padding: 0; display: flex; justify-content: center; align-items: center; height: 100vh; overflow: hidden; font-family: sans-serif; }}
                .video-container {{ width: 100%; max-width: 1000px; box-shadow: 0 0 20px rgba(255,255,255,0.1); }}
                video {{ width: 100%; height: 100%; outline: none; }}
            </style>
        </head>
        <body>
            <div class="video-container">
                <video id="player" playsinline controls crossorigin>
                    <source src="https://{host}/stream/{message_id}" type="video/mp4" />
                </video>
            </div>
            <script src="https://cdn.plyr.io/3.7.8/plyr.polyfilled.js"></script>
            <script>
                const player = new Plyr('#player', {{
                    controls: ['play-large', 'play', 'progress', 'current-time', 'mute', 'volume', 'settings', 'fullscreen']
                }});
            </script>
        </body>
        </html>
        """
        return web.Response(text=html_page, content_type="text/html")
    except Exception as e:
        return web.Response(status=500, text=f"Error loading player: {str(e)}")


# ====================================================
# STREAM & DOWNLOAD HANDLER (Now with /dl/ support)
# ====================================================
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
        }
        
        # Agar request /dl/ se aayi hai, toh browser ko force download/raw file bhejo
        if request.path.startswith("/dl/"):
            headers["Content-Disposition"] = f'attachment; filename="ALL_NETFLIX_{message_id}.mp4"'
        else:
            headers["Content-Disposition"] = 'inline'

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

# ====================================================
# TELEGRAM BOT HANDLERS
# ====================================================
@bot.on_message(filters.private & filters.command("start"))
async def start_cmd(client, message):
    await message.reply_text("👋 Hello! Send me any video and I will give you a direct stream link.")

@bot.on_message(filters.private & filters.media)
async def media_cmd(client, message):
    try:
        sent_msg = await message.copy(BIN_CHANNEL)
        host = os.environ.get("RENDER_EXTERNAL_HOSTNAME", f"localhost:{PORT}")
        
        watch_link = f"https://{host}/watch/{sent_msg.id}"
        stream_link = f"https://{host}/stream/{sent_msg.id}"
        dl_link = f"https://{host}/dl/{sent_msg.id}"
        
        reply_message = (
            f"🎬 **Link Generated Successfully!**\n\n"
            f"📥 **Download Link (Use this in Website):**\n`{dl_link}`\n\n"
            f"📺 **Web Player:**\n`{watch_link}`\n\n"
            f"🔗 **Raw Stream Link:**\n`{stream_link}`"
        )
        await message.reply_text(reply_message)
    except Exception as e:
        await message.reply_text(f"Error: {e}")

# ====================================================
# START SERVER (With CORS Middleware)
# ====================================================
async def web_server():
    app = web.Application(middlewares=[cors_middleware])
    app.router.add_get("/", lambda r: web.Response(text="ALL NETFLIX Server is Awake!"))
    app.router.add_route("*", "/watch/{message_id}", watch_handler)
    app.router.add_route("*", "/stream/{message_id}", stream_handler)
    app.router.add_route("*", "/dl/{message_id}", stream_handler) # Map /dl/ to stream handler
    
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
