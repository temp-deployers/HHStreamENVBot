# Enhanced file handler with NEW database architecture
import logging
import time
from pyrogram import filters
from WebStreamer.vars import Var
from WebStreamer.bot import StreamBot
from pyrogram.types import Message
from WebStreamer.database import db_manager
from WebStreamer.database.models import User, File, GeneratedLink, RateLimitTracker

# Media filter - documents, videos, and audio
media_filter = (
    filters.document
    | filters.video
    | filters.audio
)

# Helper function to get media info
def get_media_info(message):
    """Extract media info from message"""
    media_types = {
        'document': 'document',
        'video': 'video', 
        'audio': 'audio'
    }
    
    for attr, media_type in media_types.items():
        media = getattr(message, attr, None)
        if media:
            return {
                'media': media,
                'media_type': media_type,
                'attr': attr,
                'file_id': getattr(media, 'file_id', ''),
                'file_unique_id': getattr(media, 'file_unique_id', ''),
                'file_name': getattr(media, 'file_name', f'{media_type}_{getattr(media, "file_unique_id", "unknown")[:8]}'),
                'file_size': getattr(media, 'file_size', 0),
                'mime_type': getattr(media, 'mime_type', 'application/octet-stream')
            }
    return None


def register_channel_handler(client):
    """Register channel media handler for additional bot clients"""
    @client.on_message(filters.channel & media_filter, group=5)
    async def channel_handler_wrapper(c, m):
        await channel_media_handler(c, m)


@StreamBot.on_message(
    filters.private & media_filter,
    group=4,
)
async def private_media_handler(bot, m: Message):
    """Handle media in private chats - NEW ARCHITECTURE"""
    
    # Check if private chat is allowed
    if not Var.ALLOW_PRIVATE_CHAT:
        await m.reply_text(
            "❌ **Private chat is disabled**\n\n"
            "Please add the bot to a channel to use file tracking features.\n\n"
            "Use /start to learn more.",
            reply_to_message_id=m.id
        )
        return
    
    try:
        # Get user info
        user = m.from_user
        user_id = user.id
        username = user.username
        first_name = user.first_name
        last_name = user.last_name
        
        # Get file properties
        media_info = get_media_info(m)
        if not media_info:
            await m.reply_text("❌ No media found in message", reply_to_message_id=m.id)
            return
        
        unique_file_id = media_info['file_unique_id']  # Telegram's unique file ID
        bot_file_id = media_info['file_id']            # Bot-specific file ID
        file_name = media_info['file_name']
        file_size = media_info['file_size']
        mime_type = media_info['mime_type']
        
        logging.info(f"Processing file from user {user_id}: {file_name} (unique_id: {unique_file_id})")
        
        # Connect to database
        async with db_manager.pool.acquire() if not db_manager.is_sqlite else db_manager.sqlite_conn as conn:
            # Create or get user
            await User.create_or_get(conn, user_id, username, first_name, last_name)
            
            # Check rate limits
            can_generate_5min = await RateLimitTracker.check_limit(
                conn, user_id, '5min', Var.RATE_LIMIT_PER_5MIN
            )
            can_generate_hour = await RateLimitTracker.check_limit(
                conn, user_id, 'hour', Var.RATE_LIMIT_PER_HOUR
            )
            can_generate_day = await RateLimitTracker.check_limit(
                conn, user_id, 'day', Var.RATE_LIMIT_PER_DAY
            )
            
            if not (can_generate_5min and can_generate_hour and can_generate_day):
                await m.reply_text(
                    "⚠️ **Rate Limit Exceeded**\n\n"
                    "You've reached your link generation limit:\n"
                    f"• Per 5 minutes: {Var.RATE_LIMIT_PER_5MIN} links\n"
                    f"• Per hour: {Var.RATE_LIMIT_PER_HOUR} links\n"
                    f"• Per day: {Var.RATE_LIMIT_PER_DAY} links\n\n"
                    "Please try again later! ⏰",
                    reply_to_message_id=m.id
                )
                return
            
            # Create or get file (automatically handles deduplication via unique_file_id)
            file_data = await File.create_or_get(
                conn, unique_file_id, file_name, file_size, mime_type, 
                user_id, bot_index=0, bot_file_id=bot_file_id
            )
            
            # Generate link with expiry and integrity
            link_data = await GeneratedLink.create_link(
                conn, unique_file_id, user_id, expiry_hours=168, secret_key=Var.SECRET_KEY
            )
            
            expiry_timestamp = link_data['expiry_timestamp']
            integrity_hash = link_data['integrity_hash']
            
            # Increment rate limit counters
            await RateLimitTracker.increment_count(conn, user_id, '5min')
            await RateLimitTracker.increment_count(conn, user_id, 'hour')
            await RateLimitTracker.increment_count(conn, user_id, 'day')
            
            if db_manager.is_sqlite:
                await conn.commit()
        
        # Build link URL
        link_url = f"{Var.URL}f/{unique_file_id}/{expiry_timestamp}/{integrity_hash}"
        
        # Format file size
        def format_size(bytes_size):
            for unit in ['B', 'KB', 'MB', 'GB']:
                if bytes_size < 1024.0:
                    return f"{bytes_size:.2f} {unit}"
                bytes_size /= 1024.0
            return f"{bytes_size:.2f} TB"
        
        # REPLY to original message (not send new)
        await m.reply_text(
            f"✅ **File Link Generated!**\n\n"
            f"📄 **Name:** `{file_name}`\n"
            f"📦 **Size:** `{format_size(file_size)}`\n"
            f"🔗 **Link:** `{link_url}`\n\n"
            f"⏰ **Expires in:** 7 days\n\n"
            f"_Click the link to stream or download your file_",
            disable_web_page_preview=True,
            reply_to_message_id=m.id
        )
        
        logging.info(f"✅ Link generated for {file_name}: {link_url}")
        
    except Exception as e:
        logging.error(f"Error in private_media_handler: {e}")
        import traceback
        traceback.print_exc()
        await m.reply_text(
            "❌ **Error Processing File**\n\n"
            "Something went wrong. Please try again later.",
            reply_to_message_id=m.id
        )


@StreamBot.on_message(
    filters.channel & media_filter,
    group=5,
)
async def channel_media_handler(bot, m: Message):
    """Handle media in channels - NEW ARCHITECTURE"""
    
    # Check if channel tracking is enabled
    if not Var.ENABLE_CHANNEL_TRACKING:
        return
    
    try:
        channel_id = m.chat.id
        message_id = m.id
        
        # Get file properties
        media_info = get_media_info(m)
        if not media_info:
            return
        
        unique_file_id = media_info['file_unique_id']  # Telegram's unique file ID
        bot_file_id = media_info['file_id']            # Bot-specific file ID
        file_name = media_info['file_name']
        file_size = media_info['file_size']
        mime_type = media_info['mime_type']
        
        logging.info(f"Processing file from channel {channel_id}: {file_name} (unique_id: {unique_file_id})")
        
        # Connect to database
        async with db_manager.pool.acquire() if not db_manager.is_sqlite else db_manager.sqlite_conn as conn:
            # Use channel ID as uploader (already exists as user from bot fixes)
            # Create or get file
            file_data = await File.create_or_get(
                conn, unique_file_id, file_name, file_size, mime_type, 
                channel_id, bot_index=0, bot_file_id=bot_file_id,
                channel_id=channel_id, message_id=message_id
            )
            
            # Generate link with expiry and integrity
            link_data = await GeneratedLink.create_link(
                conn, unique_file_id, channel_id, expiry_hours=168, secret_key=Var.SECRET_KEY
            )
            
            expiry_timestamp = link_data['expiry_timestamp']
            integrity_hash = link_data['integrity_hash']
            
            if db_manager.is_sqlite:
                await conn.commit()
        
        # Build link URL
        link_url = f"{Var.URL}f/{unique_file_id}/{expiry_timestamp}/{integrity_hash}"
        
        # Format file size
        def format_size(bytes_size):
            for unit in ['B', 'KB', 'MB', 'GB']:
                if bytes_size < 1024.0:
                    return f"{bytes_size:.2f} {unit}"
                bytes_size /= 1024.0
            return f"{bytes_size:.2f} TB"
        
        # REPLY to channel message (not send new)
        await m.reply_text(
            f"✅ **File Processed**\n\n"
            f"📄 **Name:** `{file_name}`\n"
            f"📦 **Size:** `{format_size(file_size)}`\n"
            f"🔗 **Link:** `{link_url}`\n\n"
            f"⏰ **Expires in:** 7 days",
            disable_web_page_preview=True,
            reply_to_message_id=m.id
        )
        
        logging.info(f"✅ Link generated for channel file {file_name}: {link_url}")
        
    except Exception as e:
        logging.error(f"Error in channel_media_handler: {e}")
        import traceback
        traceback.print_exc()
