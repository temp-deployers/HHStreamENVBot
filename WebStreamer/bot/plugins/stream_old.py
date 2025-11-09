# Enhanced file handler with database integration
import logging
from pyrogram import filters
from WebStreamer.vars import Var
from WebStreamer.bot import StreamBot
from WebStreamer.utils import get_hash
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from WebStreamer.database import db_manager
from WebStreamer.database.models import User, File, FileBotMapping, GeneratedLink, RateLimitTracker
import asyncio


# Media filter - ONLY documents, videos, and audio
media_filter = (
    filters.document
    | filters.video
    | filters.audio
)

# Helper function to get media type and file_id
def get_media_info(message):
    """Extract media type, file_id, and other info from message - ONLY document/video/audio"""
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
async def private_media_handler(_, m: Message):
    """Handle media in private chats"""
    
    # Check if private chat is allowed
    if not Var.ALLOW_PRIVATE_CHAT:
        await m.reply_text(
            "❌ **Private chat is disabled**\n\n"
            "Please add the bot to a channel to use file tracking features.\n\n"
            "Use /start to learn more."
        )
        return
    
    """Enhanced media handler with database integration and deduplication"""
    try:
        # Get user info
        user = m.from_user
        user_id = user.id
        username = user.username
        first_name = user.first_name
        last_name = user.last_name
        
        # Send processing message
        status_msg = await m.reply_text(
            "📤 Processing your file...\n"
            "⏳ Checking for duplicates..."
        )
        
        # Get file properties using helper
        media_info = get_media_info(m)
        if not media_info:
            await status_msg.edit_text("❌ No media found in message")
            return
        
        file_unique_id = media_info['file_unique_id']
        telegram_file_id = media_info['file_id']
        file_name = media_info['file_name']
        file_size = media_info['file_size']
        mime_type = media_info['mime_type']
        media_type = media_info['media_type']
        attr = media_info['attr']
        
        # Calculate file hash
        file_hash = File.calculate_file_hash(file_unique_id, file_size)
        
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
                await status_msg.edit_text(
                    "⚠️ **Rate Limit Exceeded**\n\n"
                    "You've reached your link generation limit:\n"
                    f"• Per 5 minutes: {Var.RATE_LIMIT_PER_5MIN} links\n"
                    f"• Per hour: {Var.RATE_LIMIT_PER_HOUR} links\n"
                    f"• Per day: {Var.RATE_LIMIT_PER_DAY} links\n\n"
                    "Please try again later! ⏰"
                )
                return
            
            # Check if file already exists
            file_data = await File.create_or_get(
                conn, file_hash, file_name, file_size, mime_type, user_id
            )
            file_id = file_data['id']
            
            # Check if we already have this file in a bot
            existing_mapping = await FileBotMapping.get_bot_for_file(conn, file_id)
            
            if existing_mapping:
                # File already exists, reuse it
                await status_msg.edit_text(
                    "✨ **File Already Exists!**\n\n"
                    "This file was previously uploaded.\n"
                    "🔄 Generating new link..."
                )
                
                # Generate new link for existing file
                link_data = await GeneratedLink.create_link(
                    conn, file_id, user_id, expiry_days=7
                )
                unique_file_id = link_data['unique_file_id']
                
                # Increment rate limit counters
                await RateLimitTracker.increment_count(conn, user_id, '5min')
                await RateLimitTracker.increment_count(conn, user_id, 'hour')
                await RateLimitTracker.increment_count(conn, user_id, 'day')
                
                # Commit if SQLite
                if db_manager.is_sqlite:
                    await conn.commit()
                
                stream_link = f"{Var.URL}f/{unique_file_id}"
                
                rm = InlineKeyboardMarkup(
                    [[InlineKeyboardButton("🔗 Open Link", url=stream_link)]]
                )
                
                await status_msg.edit_text(
                    f"✅ **Link Generated Successfully!**\n\n"
                    f"📄 File: `{file_name}`\n"
                    f"📦 Size: {file_size / (1024*1024):.2f} MB\n"
                    f"🔗 Link: `{stream_link}`\n\n"
                    f"⏰ Expires in: 7 days\n"
                    f"♻️ File reused (no storage used)",
                    reply_markup=rm
                )
                
            else:
                # New file, need to upload to channel
                await status_msg.edit_text(
                    "📤 **Uploading to storage...**\n\n"
                    "This may take a while for large files..."
                )
                
                # Copy to channel
                log_msg = await m.copy(chat_id=Var.BIN_CHANNEL)
                message_id = log_msg.id
                telegram_file_id = getattr(log_msg, attr, None).file_id if log_msg else ""
                
                # Add bot mapping (bot index 0 for main bot) with media_type
                await FileBotMapping.add_mapping(
                    conn, file_id, 0, telegram_file_id, message_id, Var.BIN_CHANNEL, media_type
                )
                
                # Generate link
                link_data = await GeneratedLink.create_link(
                    conn, file_id, user_id, expiry_days=7
                )
                unique_file_id = link_data['unique_file_id']
                
                # Increment rate limit counters
                await RateLimitTracker.increment_count(conn, user_id, '5min')
                await RateLimitTracker.increment_count(conn, user_id, 'hour')
                await RateLimitTracker.increment_count(conn, user_id, 'day')
                
                # Commit if SQLite
                if db_manager.is_sqlite:
                    await conn.commit()
                
                stream_link = f"{Var.URL}f/{unique_file_id}"
                
                rm = InlineKeyboardMarkup(
                    [[InlineKeyboardButton("🔗 Open Link", url=stream_link)]]
                )
                
                await status_msg.edit_text(
                    f"✅ **Link Generated Successfully!**\n\n"
                    f"📄 File: `{file_name}`\n"
                    f"📦 Size: {file_size / (1024*1024):.2f} MB\n"
                    f"🔗 Link: `{stream_link}`\n\n"
                    f"⏰ Expires in: 7 days\n"
                    f"🆕 New file uploaded",
                    reply_markup=rm
                )
        
    except Exception as e:
        logging.error(f"Error in media_receive_handler: {e}")
        import traceback
        traceback.print_exc()
        await m.reply_text(
            "❌ **Error processing file**\n\n"
            f"Error: {str(e)}\n\n"
            "Please try again or contact support."
        )


@StreamBot.on_message(
    filters.channel & media_filter,
    group=5,
)
async def channel_media_handler(client, m: Message):
    """Handle media in channels - Track files without copying"""
    
    # Check if channel tracking is enabled
    if not Var.ENABLE_CHANNEL_TRACKING:
        return
    
    try:
        from WebStreamer.bot import multi_clients
        import random
        
        # Determine bot index by checking which bot client this is
        bot_index = 0  # Default to main bot
        current_bot_id = client.me.id if hasattr(client, 'me') else None
        
        if current_bot_id:
            for idx, bot_client in multi_clients.items():
                if hasattr(bot_client, 'me') and bot_client.me.id == current_bot_id:
                    bot_index = idx
                    break
        
        # Get file properties using helper function
        media_info = get_media_info(m)
        if not media_info:
            return
        
        file_unique_id = media_info['file_unique_id']
        telegram_file_id = media_info['file_id']
        file_name = media_info['file_name']
        file_size = media_info['file_size']
        mime_type = media_info['mime_type']
        media_type = media_info['media_type']
        
        # Calculate file hash for deduplication
        file_hash = File.calculate_file_hash(file_unique_id, file_size)
        
        channel_id = m.chat.id
        message_id = m.id
        
        file_is_new = False
        
        # Connect to database and save file metadata
        async with db_manager.pool.acquire() if not db_manager.is_sqlite else db_manager.sqlite_conn as conn:
            # Check if file exists
            if not db_manager.is_sqlite:
                existing_file = await conn.fetchrow(
                    'SELECT * FROM files WHERE file_hash = $1', file_hash
                )
            else:
                cursor = await conn.execute(
                    'SELECT * FROM files WHERE file_hash = ?', (file_hash,)
                )
                existing_file = await cursor.fetchone()
            
            file_is_new = (existing_file is None)
            
            # Create or get file (use channel_id as uploader for channel files)
            file_data = await File.create_or_get(
                conn, file_hash, file_name, file_size, mime_type, channel_id
            )
            file_id = file_data['id']
            
            # Check if this bot already has a mapping for this file
            if not db_manager.is_sqlite:
                existing_mapping = await conn.fetchrow(
                    'SELECT * FROM file_bot_mapping WHERE file_id = $1 AND bot_index = $2',
                    file_id, bot_index
                )
            else:
                cursor = await conn.execute(
                    'SELECT * FROM file_bot_mapping WHERE file_id = ? AND bot_index = ?',
                    (file_id, bot_index)
                )
                existing_mapping = await cursor.fetchone()
            
            if not existing_mapping:
                # Add bot mapping with media_type
                await FileBotMapping.add_mapping(
                    conn, file_id, bot_index, telegram_file_id, message_id, channel_id, media_type
                )
                
                logging.info(f"Tracked file in channel {channel_id}: {file_name} (bot_{bot_index}, type={media_type})")
            
            # Commit if SQLite
            if db_manager.is_sqlite:
                await conn.commit()
            
            # If COPY_FILES_TO_CHANNEL is enabled and file is new, send to BIN_CHANNEL
            if Var.COPY_FILES_TO_CHANNEL and file_is_new:
                # Get all bots that have this file
                all_bot_mappings = await FileBotMapping.get_all_bots_for_file(conn, file_id)
                
                if all_bot_mappings:
                    # Randomly select one bot to send the file
                    selected_mapping = random.choice(all_bot_mappings)
                    selected_bot_index = selected_mapping['bot_index'] if isinstance(selected_mapping, dict) else selected_mapping[2]
                    selected_file_id = selected_mapping['telegram_file_id'] if isinstance(selected_mapping, dict) else selected_mapping[3]
                    selected_media_type = selected_mapping['media_type'] if isinstance(selected_mapping, dict) else selected_mapping[6]
                    
                    # Get the bot client
                    send_bot = multi_clients.get(selected_bot_index, StreamBot)
                    
                    # Send file to BIN_CHANNEL using appropriate method (ONLY document/video/audio)
                    try:
                        sent_msg = None
                        if selected_media_type == 'document':
                            sent_msg = await send_bot.send_document(
                                chat_id=Var.BIN_CHANNEL,
                                document=selected_file_id,
                                caption=f"📁 {file_name}"
                            )
                        elif selected_media_type == 'video':
                            sent_msg = await send_bot.send_video(
                                chat_id=Var.BIN_CHANNEL,
                                video=selected_file_id,
                                caption=f"🎬 {file_name}"
                            )
                        elif selected_media_type == 'audio':
                            sent_msg = await send_bot.send_audio(
                                chat_id=Var.BIN_CHANNEL,
                                audio=selected_file_id,
                                caption=f"🎵 {file_name}"
                            )
                        
                        if sent_msg:
                            logging.info(f"Sent new file to BIN_CHANNEL using bot_{selected_bot_index}: {file_name}")
                    
                    except Exception as e:
                        logging.error(f"Failed to send file to BIN_CHANNEL: {e}")
        
        # Check if message is forwarded
        is_forwarded = bool(m.forward_from or m.forward_from_chat or m.forward_sender_name)
        
        # Create button to web UI
        file_detail_url = f"{Var.URL}files/{file_id}"
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🌐 View in Web Dashboard", url=file_detail_url)]
        ])
        
        if is_forwarded:
            # Reply to forwarded message
            await m.reply_text(
                f"📁 **File Tracked Successfully**\n\n"
                f"📄 File: `{file_name}`\n"
                f"📦 Size: {file_size / (1024*1024):.2f} MB\n\n"
                f"🔗 Click the button below to generate a streaming link from the web dashboard.\n\n"
                f"💡 You'll need to login with your Telegram account.",
                reply_markup=keyboard
            )
        else:
            # Edit original message (for non-forwarded files)
            try:
                # Get existing caption or text
                existing_text = m.caption or m.text or ""
                
                # Create new caption/text
                new_text = f"{existing_text}\n\n" if existing_text else ""
                new_text += (
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    "📁 **Tracked by LinkerX CDN**\n"
                    "🔗 Generate streaming link ↓"
                )
                
                # Try to edit caption for media or text for text messages
                if m.caption:
                    await m.edit_caption(new_text, reply_markup=keyboard)
                elif m.text:
                    await m.edit_text(new_text, reply_markup=keyboard)
                else:
                    # Media without caption, edit it
                    await m.edit_caption(new_text, reply_markup=keyboard)
                    
            except Exception as e:
                # If can't edit, reply instead
                logging.warning(f"Could not edit message, replying instead: {e}")
                await m.reply_text(
                    f"📁 **File Tracked Successfully**\n\n"
                    f"📄 File: `{file_name}`\n"
                    f"📦 Size: {file_size / (1024*1024):.2f} MB\n\n"
                    f"🔗 Click the button below to generate a streaming link.",
                    reply_markup=keyboard
                )
        
    except Exception as e:
        logging.error(f"Error in channel_media_handler: {e}")
        import traceback
        traceback.print_exc()

