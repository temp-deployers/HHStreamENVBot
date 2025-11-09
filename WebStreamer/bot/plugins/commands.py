# Bot commands for user management
import logging
from pyrogram import filters
from pyrogram.types import Message
from WebStreamer.bot import StreamBot
from WebStreamer.database import db_manager
from WebStreamer.database.models import User, GeneratedLink, File, RateLimitTracker
from WebStreamer.vars import Var
from datetime import datetime


@StreamBot.on_message(filters.command(["mylinks"]))
async def my_links_command(_, m: Message):
    """Show user's generated links"""
    user_id = m.from_user.id
    
    try:
        async with db_manager.pool.acquire() if not db_manager.is_sqlite else db_manager.sqlite_conn as conn:
            # Get user's links
            query = '''
                SELECT gl.unique_file_id, gl.expiry_date, gl.access_count, gl.created_at,
                       f.file_name, f.file_size
                FROM generated_links gl
                JOIN files f ON gl.file_id = f.id
                WHERE gl.user_id = ? AND gl.is_active = 1
                ORDER BY gl.created_at DESC
                LIMIT 10
            ''' if db_manager.is_sqlite else '''
                SELECT gl.unique_file_id, gl.expiry_date, gl.access_count, gl.created_at,
                       f.file_name, f.file_size
                FROM generated_links gl
                JOIN files f ON gl.file_id = f.id
                WHERE gl.user_id = $1 AND gl.is_active = TRUE
                ORDER BY gl.created_at DESC
                LIMIT 10
            '''
            
            links = await db_manager.fetch(query, user_id)
            
            if not links:
                await m.reply_text(
                    "📭 **No Links Found**\n\n"
                    "You haven't generated any links yet.\n"
                    "Send me a file to get started!",
                    reply_to_message_id=m.id
                )
                return
            
            text = "🔗 **Your Recent Links**\n\n"
            
            for idx, link in enumerate(links, 1):
                file_name = link['file_name'] if isinstance(link, dict) else link[4]
                unique_id = link['unique_file_id'] if isinstance(link, dict) else link[0]
                access_count = link['access_count'] if isinstance(link, dict) else link[2]
                expiry = link['expiry_date'] if isinstance(link, dict) else link[1]
                
                # Check if expired
                is_expired = expiry < datetime.now() if isinstance(expiry, datetime) else False
                status = "❌ Expired" if is_expired else "✅ Active"
                
                url = f"{Var.URL}f/{unique_id}"
                text += f"{idx}. **{file_name[:30]}**\n"
                text += f"   {status} | 👁️ {access_count} views\n"
                text += f"   `{url}`\n\n"
            
            text += "💡 *Tip: Links expire after 7 days*"
            
            await m.reply_text(text, reply_to_message_id=m.id)
            
    except Exception as e:
        logging.error(f"Error in my_links_command: {e}")
        await m.reply_text("❌ Error fetching your links. Please try again.", reply_to_message_id=m.id)


@StreamBot.on_message(filters.command(["stats"]))
async def stats_command(_, m: Message):
    """Show user statistics"""
    user_id = m.from_user.id
    
    try:
        async with db_manager.pool.acquire() if not db_manager.is_sqlite else db_manager.sqlite_conn as conn:
            # Get total files uploaded
            total_files_query = 'SELECT COUNT(*) FROM files WHERE uploaded_by = ?' if db_manager.is_sqlite else 'SELECT COUNT(*) FROM files WHERE uploaded_by = $1'
            total_files = await db_manager.fetchval(total_files_query, user_id) or 0
            
            # Get total links generated
            total_links_query = 'SELECT COUNT(*) FROM generated_links WHERE user_id = ?' if db_manager.is_sqlite else 'SELECT COUNT(*) FROM generated_links WHERE user_id = $1'
            total_links = await db_manager.fetchval(total_links_query, user_id) or 0
            
            # Get total views
            total_views_query = '''
                SELECT SUM(f.total_views)
                FROM files f
                WHERE f.uploaded_by = ?
            ''' if db_manager.is_sqlite else '''
                SELECT SUM(f.total_views)
                FROM files f
                WHERE f.uploaded_by = $1
            '''
            total_views = await db_manager.fetchval(total_views_query, user_id) or 0
            
            text = (
                "📊 **Your Statistics**\n\n"
                f"📁 Total Files: **{total_files}**\n"
                f"🔗 Total Links: **{total_links}**\n"
                f"👁️ Total Views: **{total_views}**\n\n"
                f"🎉 Thank you for using LinkerX CDN!"
            )
            
            await m.reply_text(text, reply_to_message_id=m.id)
            
    except Exception as e:
        logging.error(f"Error in stats_command: {e}")
        await m.reply_text("❌ Error fetching statistics. Please try again.", reply_to_message_id=m.id)


@StreamBot.on_message(filters.command(["quota"]))
async def quota_command(_, m: Message):
    """Check remaining quota"""
    user_id = m.from_user.id
    
    try:
        async with db_manager.pool.acquire() if not db_manager.is_sqlite else db_manager.sqlite_conn as conn:
            # Check all three quotas
            can_5min = await RateLimitTracker.check_limit(
                conn, user_id, '5min', Var.RATE_LIMIT_PER_5MIN
            )
            can_hour = await RateLimitTracker.check_limit(
                conn, user_id, 'hour', Var.RATE_LIMIT_PER_HOUR
            )
            can_day = await RateLimitTracker.check_limit(
                conn, user_id, 'day', Var.RATE_LIMIT_PER_DAY
            )
            
            # Get current counts
            from datetime import datetime, timedelta
            now = datetime.now()
            
            # 5 min count
            period_start_5min = now.replace(second=0, microsecond=0)
            period_start_5min = period_start_5min - timedelta(minutes=period_start_5min.minute % 5)
            count_5min_query = 'SELECT link_count FROM rate_limit_tracker WHERE user_id = ? AND period_type = "5min" AND period_start = ?' if db_manager.is_sqlite else 'SELECT link_count FROM rate_limit_tracker WHERE user_id = $1 AND period_type = $2 AND period_start = $3'
            count_5min = await db_manager.fetchval(count_5min_query, user_id, '5min', period_start_5min) if not db_manager.is_sqlite else await db_manager.fetchval(count_5min_query, user_id, '5min') or 0
            
            # Hour count
            period_start_hour = now.replace(minute=0, second=0, microsecond=0)
            count_hour_query = 'SELECT link_count FROM rate_limit_tracker WHERE user_id = ? AND period_type = "hour" AND period_start = ?' if db_manager.is_sqlite else 'SELECT link_count FROM rate_limit_tracker WHERE user_id = $1 AND period_type = $2 AND period_start = $3'
            count_hour = await db_manager.fetchval(count_hour_query, user_id, 'hour', period_start_hour) if not db_manager.is_sqlite else await db_manager.fetchval(count_hour_query, user_id, 'hour') or 0
            
            # Day count
            period_start_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
            count_day_query = 'SELECT link_count FROM rate_limit_tracker WHERE user_id = ? AND period_type = "day" AND period_start = ?' if db_manager.is_sqlite else 'SELECT link_count FROM rate_limit_tracker WHERE user_id = $1 AND period_type = $2 AND period_start = $3'
            count_day = await db_manager.fetchval(count_day_query, user_id, 'day', period_start_day) if not db_manager.is_sqlite else await db_manager.fetchval(count_day_query, user_id, 'day') or 0
            
            # Calculate remaining
            remaining_5min = Var.RATE_LIMIT_PER_5MIN - (count_5min or 0)
            remaining_hour = Var.RATE_LIMIT_PER_HOUR - (count_hour or 0)
            remaining_day = Var.RATE_LIMIT_PER_DAY - (count_day or 0)
            
            text = (
                "⏰ **Your Rate Limits**\n\n"
                f"**Per 5 Minutes:**\n"
                f"{'✅' if can_5min else '❌'} {remaining_5min}/{Var.RATE_LIMIT_PER_5MIN} links remaining\n\n"
                f"**Per Hour:**\n"
                f"{'✅' if can_hour else '❌'} {remaining_hour}/{Var.RATE_LIMIT_PER_HOUR} links remaining\n\n"
                f"**Per Day:**\n"
                f"{'✅' if can_day else '❌'} {remaining_day}/{Var.RATE_LIMIT_PER_DAY} links remaining\n\n"
                f"💡 *Limits reset automatically*"
            )
            
            await m.reply_text(text, reply_to_message_id=m.id)
            
    except Exception as e:
        logging.error(f"Error in quota_command: {e}")
        await m.reply_text("❌ Error checking quota. Please try again.", reply_to_message_id=m.id)


@StreamBot.on_message(filters.command(["help"]))
async def help_command(_, m: Message):
    """Show help message"""
    text = (
        "📚 **LinkerX CDN Bot - Help**\n\n"
        "**Available Commands:**\n"
        "• /start - Start the bot\n"
        "• /help - Show this help message\n"
        "• /mylinks - View your recent links\n"
        "• /stats - View your statistics\n"
        "• /quota - Check rate limit quota\n\n"
        "**How to Use:**\n"
        "1. Send any file to the bot\n"
        "2. Bot will generate a streaming link\n"
        "3. Share the link with anyone\n"
        "4. Links expire after 7 days\n\n"
        "**Rate Limits:**\n"
        f"• {Var.RATE_LIMIT_PER_5MIN} link per 5 minutes\n"
        f"• {Var.RATE_LIMIT_PER_HOUR} links per hour\n"
        f"• {Var.RATE_LIMIT_PER_DAY} links per day\n\n"
        "**Features:**\n"
        "✅ File deduplication (saves storage)\n"
        "✅ Fast streaming with range support\n"
        "✅ Analytics tracking\n"
        "✅ Secure encrypted links\n\n"
        "🌐 **Web Portal:** Visit our website for more features!\n\n"
        "Made with ❤️ by Hash Hackers & LiquidX Projects"
    )
    
    await m.reply_text(text, reply_to_message_id=m.id)
