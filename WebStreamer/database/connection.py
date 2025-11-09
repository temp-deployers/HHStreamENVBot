# Database connection manager
import asyncpg
import aiosqlite
import logging
from typing import Optional
from ..vars import Var

class DatabaseManager:
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None
        self.sqlite_conn = None
        self.database_url = Var.DATABASE_URL
        self.is_sqlite = self.database_url.startswith('sqlite')
    
    async def connect(self):
        """Create database connection pool"""
        try:
            if self.is_sqlite:
                # SQLite connection for local testing
                db_path = self.database_url.replace('sqlite:///', '')
                self.sqlite_conn = await aiosqlite.connect(db_path)
                logging.info(f"✅ SQLite database connected: {db_path}")
            else:
                # PostgreSQL connection for production
                self.pool = await asyncpg.create_pool(
                    self.database_url,
                    min_size=1,
                    max_size=3,
                    command_timeout=60
                )
                logging.info("✅ PostgreSQL database connected successfully")
            return True
        except Exception as e:
            logging.error(f"❌ Database connection failed: {e}")
            return False
    
    async def disconnect(self):
        """Close database connection pool"""
        if self.is_sqlite and self.sqlite_conn:
            await self.sqlite_conn.close()
            logging.info("SQLite database disconnected")
        elif self.pool:
            await self.pool.close()
            logging.info("PostgreSQL database disconnected")
    
    async def execute(self, query: str, *args):
        """Execute a query"""
        if self.is_sqlite:
            # SQLite uses ? placeholders instead of $1, $2
            query = self._convert_query_placeholders(query)
            async with self.sqlite_conn.execute(query, args) as cursor:
                await self.sqlite_conn.commit()
                return cursor.rowcount
        else:
            # Convert ? to $1, $2, etc. for PostgreSQL
            query = self._convert_to_postgres_placeholders(query)
            async with self.pool.acquire() as conn:
                return await conn.execute(query, *args)
    
    async def fetch(self, query: str, *args):
        """Fetch multiple rows"""
        if self.is_sqlite:
            query = self._convert_query_placeholders(query)
            async with self.sqlite_conn.execute(query, args) as cursor:
                rows = await cursor.fetchall()
                # Convert to dict-like objects
                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row)) for row in rows]
        else:
            # Convert ? to $1, $2, etc. for PostgreSQL
            query = self._convert_to_postgres_placeholders(query)
            async with self.pool.acquire() as conn:
                return await conn.fetch(query, *args)
    
    async def fetchrow(self, query: str, *args):
        """Fetch single row"""
        if self.is_sqlite:
            query = self._convert_query_placeholders(query)
            async with self.sqlite_conn.execute(query, args) as cursor:
                row = await cursor.fetchone()
                if row:
                    columns = [desc[0] for desc in cursor.description]
                    return dict(zip(columns, row))
                return None
        else:
            # Convert ? to $1, $2, etc. for PostgreSQL
            query = self._convert_to_postgres_placeholders(query)
            async with self.pool.acquire() as conn:
                return await conn.fetchrow(query, *args)
    
    async def fetchval(self, query: str, *args):
        """Fetch single value"""
        if self.is_sqlite:
            query = self._convert_query_placeholders(query)
            async with self.sqlite_conn.execute(query, args) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else None
        else:
            # Convert ? to $1, $2, etc. for PostgreSQL
            query = self._convert_to_postgres_placeholders(query)
            async with self.pool.acquire() as conn:
                return await conn.fetchval(query, *args)
    
    def _convert_query_placeholders(self, query: str) -> str:
        """Convert PostgreSQL $1, $2 placeholders to SQLite ? placeholders"""
        import re
        # Replace $1, $2, etc. with ?
        return re.sub(r'\$\d+', '?', query)
    
    def _convert_to_postgres_placeholders(self, query: str) -> str:
        """Convert ? placeholders to PostgreSQL $1, $2, $3, etc."""
        counter = 0
        def replacer(match):
            nonlocal counter
            counter += 1
            return f'${counter}'
        import re
        return re.sub(r'\?', replacer, query)
    
    async def get_connection(self):
        """Get raw connection for migrations"""
        if self.is_sqlite:
            return self.sqlite_conn
        else:
            return await self.pool.acquire()

# Global database manager instance
db_manager = DatabaseManager()

async def get_db():
    """Get database connection"""
    return db_manager
