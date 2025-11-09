# Enhanced start command with database integration
import logging
from pyrogram import filters
from WebStreamer.vars import Var
from WebStreamer.bot import StreamBot
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from WebStreamer.database import db_manager
from WebStreamer.database.models import User

@StreamBot.on_message(filters.command(["start"]))
async def start(_, m: Message):
    user = m.from_user
    user_id = user.id
    username = user.username
    first_name = user.first_name
    last_name = user.last_name
    
    # Auto-register user in database
    try:
        async with db_manager.pool.acquire() if not db_manager.is_sqlite else db_manager.sqlite_conn as conn:
            await User.create_or_get(conn, user_id, username, first_name, last_name)
            if db_manager.is_sqlite:
                await conn.commit()
    except Exception as e:
        logging.error(f"Error registering user: {e}")
    
    # Build usage message based on enabled features
    usage_options = []
    if Var.ALLOW_PRIVATE_CHAT:
        usage_options.append("💬 **Private Chat**: Send me files directly to get streaming links")
    if Var.ENABLE_CHANNEL_TRACKING:
        usage_options.append("📢 **Channel Mode**: Add me to your channel to track and manage files")
    
    usage_text = "\n".join(usage_options) if usage_options else "📤 Send me files to get started!"
    
    # Create inline keyboard - simple buttons without callback
    keyboard = []
    keyboard.append([InlineKeyboardButton("📚 Help & Commands", callback_data="help")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await m.reply_text(
        f'👋 Hello {m.from_user.mention(style="md")}!\n\n'
        f'🎬 **Welcome to LinkerX CDN Bot**\n\n'
        f'I can help you stream and share files via HTTP/HTTPS.\n\n'
        f'**📍 How to Use:**\n{usage_text}\n\n'
        f'⚡️ **Features:**\n'
        f'• Fast file streaming\n'
        f'• Automatic deduplication\n'
        f'• Multiple bot support\n'
        f'• Web-based file management\n'
        f'• Analytics tracking\n\n'
        f'📝 Use /help to see all commands\n\n'
        f'🔒 Powered by Hash Hackers & LiquidX Projects',
        reply_markup=reply_markup,
        reply_to_message_id=m.id
    )
