# Database models using asyncpg (raw SQL approach for simplicity)
import asyncpg
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import hashlib
import secrets
import time

class User:
    """User model - Telegram ID based"""
    
    @staticmethod
    async def create_table(conn: asyncpg.Connection):
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id BIGINT PRIMARY KEY,
                username VARCHAR(255),
                first_name VARCHAR(255),
                last_name VARCHAR(255),
                created_at TIMESTAMP DEFAULT NOW(),
                is_banned BOOLEAN DEFAULT FALSE,
                trust_score INT DEFAULT 100
            )
        ''')
    
    @staticmethod
    async def create_or_get(conn: asyncpg.Connection, user_id: int, username: str = None, 
                           first_name: str = None, last_name: str = None):
        """Create user or return existing"""
        existing = await conn.fetchrow(
            'SELECT * FROM users WHERE id = $1', user_id
        )
        if existing:
            return dict(existing)
        
        await conn.execute('''
            INSERT INTO users (id, username, first_name, last_name)
            VALUES ($1, $2, $3, $4)
        ''', user_id, username, first_name, last_name)
        
        return await conn.fetchrow('SELECT * FROM users WHERE id = $1', user_id)
    
    @staticmethod
    async def is_banned(conn: asyncpg.Connection, user_id: int) -> bool:
        result = await conn.fetchval(
            'SELECT is_banned FROM users WHERE id = $1', user_id
        )
        return result or False


class File:
    """File model - New simplified single-table design"""
    
    @staticmethod
    async def create_table(conn: asyncpg.Connection):
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS files (
                unique_file_id VARCHAR(255) PRIMARY KEY,
                file_name VARCHAR(500),
                file_size BIGINT,
                mime_type VARCHAR(100),
                
                -- Bot file IDs (expandable for multi-bot)
                bot_0_file_id VARCHAR(255),
                bot_1_file_id VARCHAR(255),
                bot_2_file_id VARCHAR(255),
                
                -- Metadata
                uploaded_by BIGINT REFERENCES users(id),
                upload_date TIMESTAMP DEFAULT NOW(),
                total_views INT DEFAULT 0,
                total_downloads INT DEFAULT 0,
                
                -- Optional: channel info for external app compatibility
                channel_id BIGINT,
                message_id BIGINT
            )
        ''')
        
        # Create indexes
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_files_name ON files(file_name)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_files_uploaded_by ON files(uploaded_by)')
    
    @staticmethod
    async def create_or_get(conn: asyncpg.Connection, unique_file_id: str, file_name: str,
                           file_size: int, mime_type: str, user_id: int, bot_index: int = 0,
                           bot_file_id: str = None, channel_id: int = None, message_id: int = None) -> Dict:
        """Create file or update if exists"""
        # Check if file exists
        existing = await conn.fetchrow(
            'SELECT * FROM files WHERE unique_file_id = $1', unique_file_id
        )
        
        if existing:
            # Update bot file_id if provided
            if bot_file_id:
                bot_column = f'bot_{bot_index}_file_id'
                await conn.execute(f'''
                    UPDATE files SET {bot_column} = $1 WHERE unique_file_id = $2
                ''', bot_file_id, unique_file_id)
            return dict(existing)
        
        # Create new file
        bot_column = f'bot_{bot_index}_file_id'
        result = await conn.fetchrow(f'''
            INSERT INTO files (unique_file_id, file_name, file_size, mime_type, uploaded_by, 
                             {bot_column}, channel_id, message_id)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING *
        ''', unique_file_id, file_name, file_size, mime_type, user_id, bot_file_id, channel_id, message_id)
        
        return dict(result)
    
    @staticmethod
    async def get_by_unique_id(conn: asyncpg.Connection, unique_file_id: str) -> Optional[Dict]:
        """Get file by unique file ID"""
        result = await conn.fetchrow(
            'SELECT * FROM files WHERE unique_file_id = $1', unique_file_id
        )
        return dict(result) if result else None
    
    @staticmethod
    async def increment_views(conn: asyncpg.Connection, unique_file_id: str):
        await conn.execute(
            'UPDATE files SET total_views = total_views + 1 WHERE unique_file_id = $1', unique_file_id
        )
    
    @staticmethod
    async def increment_downloads(conn: asyncpg.Connection, unique_file_id: str):
        await conn.execute(
            'UPDATE files SET total_downloads = total_downloads + 1 WHERE unique_file_id = $1', unique_file_id
        )


class FileBotMapping:
    """Mapping between files and bots that have them"""
    
    @staticmethod
    async def create_table(conn: asyncpg.Connection):
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS file_bot_mapping (
                id SERIAL PRIMARY KEY,
                file_id INTEGER REFERENCES files(id) ON DELETE CASCADE,
                bot_index INTEGER NOT NULL,
                telegram_file_id VARCHAR(255) NOT NULL,
                telegram_message_id BIGINT NOT NULL,
                channel_id BIGINT NOT NULL,
                added_at TIMESTAMP DEFAULT NOW()
            )
        ''')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_file_bot_file_id ON file_bot_mapping(file_id)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_file_bot_bot_index ON file_bot_mapping(bot_index)')
    
    @staticmethod
    async def add_mapping(conn: asyncpg.Connection, file_id: int, bot_index: int, 
                         telegram_file_id: str, telegram_message_id: int, channel_id: int):
        """Add a new bot-file mapping"""
        await conn.execute('''
            INSERT INTO file_bot_mapping 
            (file_id, bot_index, telegram_file_id, telegram_message_id, channel_id)
            VALUES ($1, $2, $3, $4, $5)
        ''', file_id, bot_index, telegram_file_id, telegram_message_id, channel_id)
    
    @staticmethod
    async def get_bot_for_file(conn: asyncpg.Connection, file_id: int):
        """Get a bot that has this file"""
        return await conn.fetchrow('''
            SELECT * FROM file_bot_mapping 
            WHERE file_id = $1 
            LIMIT 1
        ''', file_id)
    
    @staticmethod
    async def get_all_bots_for_file(conn: asyncpg.Connection, file_id: int):
        """Get all bots that have this file"""
        return await conn.fetch('''
            SELECT * FROM file_bot_mapping 
            WHERE file_id = $1
        ''', file_id)
    
    @staticmethod
    async def delete_mapping(conn: asyncpg.Connection, file_id: int, bot_index: int):
        """Delete a specific bot-file mapping"""
        await conn.execute('''
            DELETE FROM file_bot_mapping 
            WHERE file_id = $1 AND bot_index = $2
        ''', file_id, bot_index)



class GeneratedLink:
    """Generated links for files - New structure with expiry/integrity"""
    
    @staticmethod
    async def create_table(conn: asyncpg.Connection):
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS generated_links (
                id SERIAL PRIMARY KEY,
                unique_file_id VARCHAR(255) REFERENCES files(unique_file_id) ON DELETE CASCADE,
                user_id BIGINT REFERENCES users(id),
                expiry_timestamp BIGINT NOT NULL,
                integrity_hash VARCHAR(64) NOT NULL,
                created_at TIMESTAMP DEFAULT NOW(),
                access_count INT DEFAULT 0,
                last_accessed TIMESTAMP,
                is_active BOOLEAN DEFAULT TRUE
            )
        ''')
        
        # Create indexes
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_links_file_id ON generated_links(unique_file_id)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_links_user_id ON generated_links(user_id)')
    
    @staticmethod
    def generate_integrity_hash(unique_file_id: str, expiry_timestamp: int, secret_key: str) -> str:
        """Generate integrity hash for link verification"""
        data = f"{unique_file_id}:{expiry_timestamp}:{secret_key}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]  # Short hash
    
    @staticmethod
    async def create_link(conn: asyncpg.Connection, unique_file_id: str, user_id: int,
                         expiry_hours: int = 168, secret_key: str = "default_secret") -> Dict:
        """Create new link for file"""
        expiry_timestamp = int(time.time()) + (expiry_hours * 3600)
        integrity_hash = GeneratedLink.generate_integrity_hash(unique_file_id, expiry_timestamp, secret_key)
        
        result = await conn.fetchrow('''
            INSERT INTO generated_links (unique_file_id, user_id, expiry_timestamp, integrity_hash)
            VALUES ($1, $2, $3, $4)
            RETURNING *
        ''', unique_file_id, user_id, expiry_timestamp, integrity_hash)
        
        return dict(result)
    
    @staticmethod
    async def get_by_params(conn: asyncpg.Connection, unique_file_id: str, 
                           expiry_timestamp: int, integrity_hash: str) -> Optional[Dict]:
        """Get link by parameters and verify"""
        result = await conn.fetchrow('''
            SELECT * FROM generated_links 
            WHERE unique_file_id = $1 AND expiry_timestamp = $2 
            AND integrity_hash = $3 AND is_active = TRUE
        ''', unique_file_id, expiry_timestamp, integrity_hash)
        
        return dict(result) if result else None
    
    @staticmethod
    async def increment_access(conn: asyncpg.Connection, link_id: int):
        await conn.execute('''
            UPDATE generated_links SET 
                access_count = access_count + 1,
                last_accessed = NOW()
            WHERE id = $1
        ''', link_id)


class LinkAccessLog:
    """Access logs for analytics"""
    
    @staticmethod
    async def create_table(conn: asyncpg.Connection):
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS link_access_logs (
                id SERIAL PRIMARY KEY,
                link_id INT REFERENCES generated_links(id) ON DELETE CASCADE,
                accessed_at TIMESTAMP DEFAULT NOW(),
                ip_address VARCHAR(45),
                user_agent TEXT,
                access_type VARCHAR(20) DEFAULT 'view'
            )
        ''')
    
    @staticmethod
    async def log_access(conn: asyncpg.Connection, link_id: int, ip_address: str,
                        user_agent: str, access_type: str = 'view'):
        """Log file access"""
        # Anonymize IP
        if not ip_address:
            ip_address = "unknown"
        else:
            # Truncate if too long (max 250 chars to be safe)
            if len(ip_address) > 250:
                ip_address = ip_address[:250]
            # Anonymize IPv4 (keep first 3 octets)
            ip_parts = ip_address.split('.')
            if len(ip_parts) == 4:
                ip_address = f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}.xxx"
            # For IPv6 or other formats, just keep first part
            elif ':' in ip_address:
                # IPv6 - keep first 3 groups
                ip_parts = ip_address.split(':')
                if len(ip_parts) >= 3:
                    ip_address = f"{ip_parts[0]}:{ip_parts[1]}:{ip_parts[2]}:xxx"
        
        # Truncate user agent if too long
        if user_agent and len(user_agent) > 500:
            user_agent = user_agent[:500]
        
        await conn.execute('''
            INSERT INTO link_access_logs (link_id, ip_address, user_agent, access_type)
            VALUES ($1, $2, $3, $4)
        ''', link_id, ip_address, user_agent, access_type)


class OTPToken:
    """OTP tokens for web authentication"""
    
    @staticmethod
    async def create_table(conn: asyncpg.Connection):
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS otp_tokens (
                id SERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(id),
                otp_code VARCHAR(6) NOT NULL,
                created_at TIMESTAMP DEFAULT NOW(),
                expires_at TIMESTAMP NOT NULL,
                used BOOLEAN DEFAULT FALSE,
                used_at TIMESTAMP
            )
        ''')
    
    @staticmethod
    def generate_otp() -> str:
        """Generate 6-digit OTP"""
        return str(secrets.randbelow(1000000)).zfill(6)
    
    @staticmethod
    async def create_otp(conn: asyncpg.Connection, user_id: int, expiry_minutes: int = 5) -> str:
        """Create OTP for user"""
        otp_code = OTPToken.generate_otp()
        expires_at = datetime.now() + timedelta(minutes=expiry_minutes)
        
        await conn.execute('''
            INSERT INTO otp_tokens (user_id, otp_code, expires_at)
            VALUES ($1, $2, $3)
        ''', user_id, otp_code, expires_at)
        
        return otp_code
    
    @staticmethod
    async def verify_otp(conn: asyncpg.Connection, user_id: int, otp_code: str) -> bool:
        """Verify OTP and mark as used"""
        result = await conn.fetchrow('''
            SELECT id FROM otp_tokens
            WHERE user_id = $1 AND otp_code = $2 AND used = FALSE
            AND expires_at > NOW()
        ''', user_id, otp_code)
        
        if result:
            await conn.execute('''
                UPDATE otp_tokens SET used = TRUE, used_at = NOW()
                WHERE id = $1
            ''', result['id'])
            return True
        return False


class RateLimitTracker:
    """Track user rate limits"""
    
    @staticmethod
    async def create_table(conn: asyncpg.Connection):
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS rate_limit_tracker (
                id SERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(id),
                period_type VARCHAR(10) NOT NULL,
                period_start TIMESTAMP NOT NULL,
                link_count INT DEFAULT 0,
                UNIQUE(user_id, period_type, period_start)
            )
        ''')
    
    @staticmethod
    async def check_limit(conn: asyncpg.Connection, user_id: int, period_type: str, 
                         max_links: int) -> bool:
        """Check if user is within rate limit"""
        now = datetime.now()
        
        # Calculate period start based on type
        if period_type == '5min':
            period_start = now.replace(second=0, microsecond=0)
            period_start = period_start - timedelta(minutes=period_start.minute % 5)
        elif period_type == 'hour':
            period_start = now.replace(minute=0, second=0, microsecond=0)
        elif period_type == 'day':
            period_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            return False
        
        # Get current count
        count = await conn.fetchval('''
            SELECT link_count FROM rate_limit_tracker
            WHERE user_id = $1 AND period_type = $2 AND period_start = $3
        ''', user_id, period_type, period_start)
        
        return (count or 0) < max_links
    
    @staticmethod
    async def increment_count(conn: asyncpg.Connection, user_id: int, period_type: str):
        """Increment rate limit counter"""
        now = datetime.now()
        
        # Calculate period start
        if period_type == '5min':
            period_start = now.replace(second=0, microsecond=0)
            period_start = period_start - timedelta(minutes=period_start.minute % 5)
        elif period_type == 'hour':
            period_start = now.replace(minute=0, second=0, microsecond=0)
        elif period_type == 'day':
            period_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            return
        
        await conn.execute('''
            INSERT INTO rate_limit_tracker (user_id, period_type, period_start, link_count)
            VALUES ($1, $2, $3, 1)
            ON CONFLICT (user_id, period_type, period_start) DO UPDATE
            SET link_count = rate_limit_tracker.link_count + 1
        ''', user_id, period_type, period_start)
