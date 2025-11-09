# Callback query handlers for inline buttons
import logging
from pyrogram import filters
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from WebStreamer.bot import StreamBot
from WebStreamer.vars import Var

@StreamBot.on_callback_query()
async def callback_handler(client, callback_query: CallbackQuery):
    """Handle all callback queries from inline buttons"""
    data = callback_query.data
    
    if data == "help":
        # Show help message
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
        
        # Add back button
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="start")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await callback_query.message.edit_text(
            text,
            reply_markup=reply_markup
        )
        
    elif data == "start":
        # Back to start message
        usage_options = []
        if Var.ALLOW_PRIVATE_CHAT:
            usage_options.append("💬 **Private Chat**: Send me files directly to get streaming links")
        if Var.ENABLE_CHANNEL_TRACKING:
            usage_options.append("📢 **Channel Mode**: Add me to your channel to track and manage files")
        
        usage_text = "\n".join(usage_options) if usage_options else "📤 Send me files to get started!"
        
        keyboard = [[InlineKeyboardButton("📚 Help & Commands", callback_data="help")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await callback_query.message.edit_text(
            f'👋 Hello {callback_query.from_user.mention(style="md")}!\n\n'
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
            reply_markup=reply_markup
        )
    
    # Answer the callback query to remove loading state
    await callback_query.answer()
