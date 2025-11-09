# Database migration script
import asyncio
import logging
import sys
from .connection import db_manager

async def run_migrations():
    """Run all database migrations"""
    logging.info("🚀 Starting database migrations...")
    
    # Connect to database
    success = await db_manager.connect()
    if not success:
        logging.error("Failed to connect to database")
        return False
    
    try:
        conn = await db_manager.get_connection()
        
        # For SQLite, we need to execute directly
        if db_manager.is_sqlite:
            # Create tables for SQLite
            logging.info("Creating users table...")
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_banned INTEGER DEFAULT 0,
                    trust_score INTEGER DEFAULT 100
                )
            ''')
            
            logging.info("Creating files table...")
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_hash TEXT UNIQUE NOT NULL,
                    file_name TEXT,
                    file_size INTEGER,
                    mime_type TEXT,
                    uploaded_by INTEGER REFERENCES users(id),
                    upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    total_views INTEGER DEFAULT 0,
                    total_downloads INTEGER DEFAULT 0
                )
            ''')
            await conn.execute('CREATE INDEX IF NOT EXISTS idx_files_hash ON files(file_hash)')
            
            logging.info("Creating file_bot_mapping table...")
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS file_bot_mapping (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_id INTEGER REFERENCES files(id) ON DELETE CASCADE,
                    bot_index INTEGER NOT NULL,
                    telegram_file_id TEXT NOT NULL,
                    telegram_message_id INTEGER NOT NULL,
                    channel_id INTEGER NOT NULL,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(file_id, bot_index)
                )
            ''')
            
            logging.info("Creating generated_links table...")
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS generated_links (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    unique_file_id TEXT UNIQUE NOT NULL,
                    file_id INTEGER REFERENCES files(id) ON DELETE CASCADE,
                    user_id INTEGER REFERENCES users(id),
                    expiry_date TIMESTAMP NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    access_count INTEGER DEFAULT 0,
                    last_accessed TIMESTAMP,
                    is_active INTEGER DEFAULT 1
                )
            ''')
            await conn.execute('CREATE INDEX IF NOT EXISTS idx_generated_links_unique_id ON generated_links(unique_file_id)')
            
            logging.info("Creating link_access_logs table...")
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS link_access_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    link_id INTEGER REFERENCES generated_links(id) ON DELETE CASCADE,
                    accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    ip_address TEXT,
                    user_agent TEXT,
                    access_type TEXT DEFAULT 'view'
                )
            ''')
            
            logging.info("Creating otp_tokens table...")
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS otp_tokens (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER REFERENCES users(id),
                    otp_code TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP NOT NULL,
                    used INTEGER DEFAULT 0,
                    used_at TIMESTAMP
                )
            ''')
            
            logging.info("Creating rate_limit_tracker table...")
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS rate_limit_tracker (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER REFERENCES users(id),
                    period_type TEXT NOT NULL,
                    period_start TIMESTAMP NOT NULL,
                    link_count INTEGER DEFAULT 0,
                    UNIQUE(user_id, period_type, period_start)
                )
            ''')
            
            await conn.commit()
            
        else:
            # PostgreSQL migrations
            from .models import User, File, GeneratedLink, LinkAccessLog, OTPToken, RateLimitTracker
            
            logging.info("Creating users table...")
            await User.create_table(conn)
            
            logging.info("Creating files table...")
            await File.create_table(conn)
            
            logging.info("Creating generated_links table...")
            await GeneratedLink.create_table(conn)
            
            logging.info("Creating link_access_logs table...")
            await LinkAccessLog.create_table(conn)
            
            logging.info("Creating otp_tokens table...")
            await OTPToken.create_table(conn)
            
            logging.info("Creating rate_limit_tracker table...")
            await RateLimitTracker.create_table(conn)
            
        logging.info("✅ All migrations completed successfully!")
        return True
        
    except Exception as e:
        logging.error(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        await db_manager.disconnect()

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s][%(levelname)s] => %(message)s"
    )
    
    result = asyncio.run(run_migrations())
    sys.exit(0 if result else 1)
