# NEW Stream Routes - Direct file_id download with new link structure
import logging
import hashlib
import time
import math
from aiohttp import web
from WebStreamer.bot import StreamBot, multi_clients
from WebStreamer.database import db_manager
from WebStreamer.database.models import File, GeneratedLink
from WebStreamer.vars import Var
from pyrogram.errors import FloodWait
import asyncio

routes = web.RouteTableDef()

# Helper to format file size
async def format_file_size(bytes_size):
    """Format bytes to human readable size"""
    if bytes_size is None or bytes_size == 0:
        return "0 B"
    bytes_size = int(bytes_size)
    k = 1024
    sizes = ["B", "KB", "MB", "GB", "TB"]
    i = math.floor(math.log(bytes_size) / math.log(k))
    return f"{round(bytes_size / math.pow(k, i), 2)} {sizes[i]}"


@routes.get("/f/{unique_file_id}/{expiry}/{integrity}", allow_head=True)
async def stream_file_new(request: web.Request):
    """
    NEW: Stream file using unique_file_id with expiry and integrity check
    Format: /f/{unique_file_id}/{expiry_timestamp}/{integrity_hash}
    """
    try:
        unique_file_id = request.match_info['unique_file_id']
        expiry_timestamp = int(request.match_info['expiry'])
        integrity_hash = request.match_info['integrity']
        
        logging.info(f"Stream request for file: {unique_file_id}")
        
        # Check if link expired
        current_time = int(time.time())
        if current_time > expiry_timestamp:
            return web.Response(
                text="⏰ **Link Expired**\n\nThis link has expired. Please request a new one.",
                status=410,
                content_type='text/plain'
            )
        
        # Verify integrity
        expected_hash = GeneratedLink.generate_integrity_hash(unique_file_id, expiry_timestamp, Var.SECRET_KEY)
        if integrity_hash != expected_hash:
            logging.warning(f"Integrity check failed for {unique_file_id}")
            return web.Response(
                text="🔒 **Invalid Link**\n\nLink integrity verification failed.",
                status=403,
                content_type='text/plain'
            )
        
        # Get file from database
        async with db_manager.pool.acquire() if not db_manager.is_sqlite else db_manager.sqlite_conn as conn:
            file_data = await File.get_by_unique_id(conn, unique_file_id)
            
            if not file_data:
                return web.Response(
                    text="❌ **File Not Found**\n\nThe requested file does not exist.",
                    status=404,
                    content_type='text/plain'
                )
            
            # Increment view count
            await File.increment_views(conn, unique_file_id)
            
            # Update link access (find link by params)
            link_data = await GeneratedLink.get_by_params(conn, unique_file_id, expiry_timestamp, integrity_hash)
            if link_data:
                await GeneratedLink.increment_access(conn, link_data['id'])
            
            if db_manager.is_sqlite:
                await conn.commit()
        
        # Get bot file_id (try bot_0 first, then bot_1, etc.)
        bot_file_id = file_data.get('bot_0_file_id')
        bot_index = 0
        
        if not bot_file_id:
            bot_file_id = file_data.get('bot_1_file_id')
            bot_index = 1
        
        if not bot_file_id:
            bot_file_id = file_data.get('bot_2_file_id')
            bot_index = 2
        
        if not bot_file_id:
            return web.Response(
                text="❌ **File Not Available**\n\nNo bot has this file available.",
                status=404,
                content_type='text/plain'
            )
        
        # Select bot client
        if bot_index < len(multi_clients):
            client = multi_clients[bot_index]
        else:
            client = StreamBot
        
        # Get file from Telegram using file_id
        logging.info(f"Downloading file with file_id: {bot_file_id} from bot {bot_index}")
        
        try:
            # Get file location
            file = await client.get_messages(client.me.id, 1)  # Dummy, we use file_id directly
            
            # Download and stream
            file_name = file_data['file_name']
            file_size = file_data['file_size']
            mime_type = file_data['mime_type']
            
            # Handle range requests
            range_header = request.headers.get('Range')
            offset = 0
            limit = file_size
            
            if range_header:
                from_bytes = int(range_header.split('=')[1].split('-')[0])
                offset = from_bytes
                limit = file_size - offset
            
            # Stream file using file_id
            async def file_stream():
                try:
                    async for chunk in client.stream_media(bot_file_id, offset=offset, limit=limit):
                        yield chunk
                except Exception as e:
                    logging.error(f"Stream error: {e}")
                    raise
            
            # Determine disposition
            disposition = "attachment"
            if "video/" in mime_type or "audio/" in mime_type:
                disposition = "inline"
            
            # Increment download count
            asyncio.create_task(increment_download(unique_file_id))
            
            # Build headers
            headers = {
                "Content-Type": mime_type,
                "Content-Disposition": f'{disposition}; filename="{file_name}"',
                "Content-Length": str(limit),
                "Accept-Ranges": "bytes"
            }
            
            # Add Content-Range only if range header exists
            if range_header:
                headers["Content-Range"] = f"bytes {offset}-{offset + limit - 1}/{file_size}"
            
            return web.Response(
                status=206 if range_header else 200,
                body=file_stream(),
                headers=headers
            )
            
        except Exception as e:
            logging.error(f"Error streaming file: {e}")
            import traceback
            traceback.print_exc()
            return web.Response(
                text=f"❌ **Download Error**\n\n{str(e)}",
                status=500,
                content_type='text/plain'
            )
    
    except Exception as e:
        logging.error(f"Error in stream_file_new: {e}")
        import traceback
        traceback.print_exc()
        return web.Response(
            text=f"❌ **Server Error**\n\n{str(e)}",
            status=500,
            content_type='text/plain'
        )


async def increment_download(unique_file_id: str):
    """Background task to increment download count"""
    try:
        async with db_manager.pool.acquire() if not db_manager.is_sqlite else db_manager.sqlite_conn as conn:
            await File.increment_downloads(conn, unique_file_id)
            if db_manager.is_sqlite:
                await conn.commit()
    except Exception as e:
        logging.error(f"Error incrementing download: {e}")


@routes.get("/{encrypted_channel_id}/{message_id}", allow_head=True)
async def stream_file_legacy(request: web.Request):
    """
    LEGACY: Support external apps using encrypted channel_id + message_id
    Format: /{encrypted_channel_id}/{message_id}
    """
    try:
        from WebStreamer.utils import decrypt_channel_id  # Import here to avoid circular import
        
        encrypted_channel_id = request.match_info['encrypted_channel_id']
        message_id = int(request.match_info['message_id'])
        
        # Decrypt channel ID
        try:
            channel_id = decrypt_channel_id(encrypted_channel_id)
        except:
            return web.Response(
                text="❌ **Invalid Link**\n\nCould not decrypt channel ID.",
                status=400,
                content_type='text/plain'
            )
        
        logging.info(f"Legacy stream request for channel {channel_id}, message {message_id}")
        
        # Get file from database using channel_id and message_id
        async with db_manager.pool.acquire() if not db_manager.is_sqlite else db_manager.sqlite_conn as conn:
            result = await conn.fetchrow(
                'SELECT * FROM files WHERE channel_id = $1 AND message_id = $2',
                channel_id, message_id
            )
            
            if not result:
                return web.Response(
                    text="❌ **File Not Found**\n\nNo file found for this channel/message.",
                    status=404,
                    content_type='text/plain'
                )
            
            file_data = dict(result)
            unique_file_id = file_data['unique_file_id']
            
            # Increment view count
            await File.increment_views(conn, unique_file_id)
            
            if db_manager.is_sqlite:
                await conn.commit()
        
        # Get bot file_id
        bot_file_id = file_data.get('bot_0_file_id') or file_data.get('bot_1_file_id') or file_data.get('bot_2_file_id')
        
        if not bot_file_id:
            return web.Response(
                text="❌ **File Not Available**",
                status=404,
                content_type='text/plain'
            )
        
        # Use StreamBot for legacy requests
        client = StreamBot
        
        # Stream file (similar logic as above)
        file_name = file_data['file_name']
        file_size = file_data['file_size']
        mime_type = file_data['mime_type']
        
        # Handle range requests
        range_header = request.headers.get('Range')
        offset = 0
        limit = file_size
        
        if range_header:
            from_bytes = int(range_header.split('=')[1].split('-')[0])
            offset = from_bytes
            limit = file_size - offset
        
        # Stream file
        async def file_stream():
            try:
                async for chunk in client.stream_media(bot_file_id, offset=offset, limit=limit):
                    yield chunk
            except Exception as e:
                logging.error(f"Stream error: {e}")
                raise
        
        # Increment download count
        asyncio.create_task(increment_download(unique_file_id))
        
        # Build headers
        headers = {
            "Content-Type": mime_type,
            "Content-Disposition": f'attachment; filename="{file_name}"',
            "Content-Length": str(limit),
            "Accept-Ranges": "bytes"
        }
        
        # Add Content-Range only if range header exists
        if range_header:
            headers["Content-Range"] = f"bytes {offset}-{offset + limit - 1}/{file_size}"
        
        return web.Response(
            status=206 if range_header else 200,
            body=file_stream(),
            headers=headers
        )
    
    except Exception as e:
        logging.error(f"Error in stream_file_legacy: {e}")
        import traceback
        traceback.print_exc()
        return web.Response(
            text=f"❌ **Server Error**\n\n{str(e)}",
            status=500,
            content_type='text/plain'
        )


# ===========================
# API ROUTES FOR FRONTEND
# ===========================

import jwt
from datetime import datetime, timedelta
START_TIME = time.time()

# JWT Configuration (from environment)
JWT_SECRET = Var.JWT_SECRET or "webstreamer_jwt_secret_key_change_in_production"
JWT_ALGORITHM = "HS256"

def get_readable_time(seconds):
    """Convert seconds to human readable format"""
    count = 0
    ping_time = ""
    time_list = []
    time_suffix_list = ["s", "m", "h", "days"]

    while count < 4:
        count += 1
        remainder, result = divmod(seconds, 60) if count < 3 else divmod(seconds, 24)
        if seconds == 0 and remainder == 0:
            break
        time_list.append(int(result))
        seconds = int(remainder)

    for x in range(len(time_list)):
        time_list[x] = str(time_list[x]) + time_suffix_list[x]
    if len(time_list) == 4:
        ping_time += time_list.pop() + ", "

    time_list.reverse()
    ping_time += ":".join(time_list)

    return ping_time

@routes.get("/api/stats")
async def get_stats(request):
    """Get global statistics"""
    try:
        async with db_manager.pool.acquire() if not db_manager.is_sqlite else db_manager.sqlite_conn as conn:
            # Get total files
            total_files = await db_manager.fetchval("SELECT COUNT(*) FROM files") or 0
            
            # Get total users
            total_users = await db_manager.fetchval("SELECT COUNT(*) FROM users") or 0
            
            # Get total views
            total_views = await db_manager.fetchval("SELECT SUM(total_views) FROM files") or 0
            
            # Get total downloads
            total_downloads = await db_manager.fetchval("SELECT SUM(total_downloads) FROM files") or 0
            
            # Get total bandwidth
            total_bandwidth = await db_manager.fetchval("SELECT SUM(total_bandwidth) FROM files") or 0
            
            # Get active links (not expired)
            active_links = await db_manager.fetchval(
                "SELECT COUNT(*) FROM generated_links WHERE is_active = TRUE AND expiry_date > NOW()" if not db_manager.is_sqlite 
                else "SELECT COUNT(*) FROM generated_links WHERE is_active = 1 AND expiry_date > datetime('now')"
            ) or 0
            
            return web.json_response({
                "total_files": total_files,
                "total_users": total_users,
                "total_views": total_views,
                "total_downloads": total_downloads,
                "total_bandwidth": total_bandwidth,
                "total_bandwidth_formatted": await format_file_size(total_bandwidth),
                "active_links": active_links,
                "active_bots": 1,
                "uptime": get_readable_time(time.time() - START_TIME)
            })
    except Exception as e:
        logging.error(f"Error in get_stats: {e}")
        return web.json_response({"error": str(e)}, status=500)

@routes.get("/api/files")
async def get_files(request):
    """Get list of files with pagination and search"""
    try:
        # Get query parameters
        limit = int(request.query.get('limit', 20))
        offset = int(request.query.get('offset', 0))
        search = request.query.get('search', '')
        sort_by = request.query.get('sort_by', 'upload_date')
        sort_order = request.query.get('sort_order', 'DESC')
        
        async with db_manager.pool.acquire() if not db_manager.is_sqlite else db_manager.sqlite_conn as conn:
            # Build query
            where_clause = ""
            params = []
            
            if search:
                where_clause = "WHERE file_name LIKE ?"
                params.append(f"%{search}%")
            
            # Count total
            count_query = f"SELECT COUNT(*) FROM files {where_clause}"
            total = await db_manager.fetchval(count_query, *params) or 0
            
            # Get files
            files_query = f"""
                SELECT unique_file_id, file_name, file_size, mime_type, upload_date, 
                       total_views, total_downloads, total_bandwidth
                FROM files
                {where_clause}
                ORDER BY {sort_by} {sort_order}
                LIMIT ? OFFSET ?
            """
            params.extend([limit, offset])
            
            files = await db_manager.fetch(files_query, *params)
            
            # Format response
            files_data = []
            for file in files:
                files_data.append({
                    "id": file['unique_file_id'] if isinstance(file, dict) else file[0],
                    "file_name": file['file_name'] if isinstance(file, dict) else file[1],
                    "file_size": file['file_size'] if isinstance(file, dict) else file[2],
                    "file_size_formatted": await format_file_size(file['file_size'] if isinstance(file, dict) else file[2]),
                    "mime_type": file['mime_type'] if isinstance(file, dict) else file[3],
                    "upload_date": str(file['upload_date'] if isinstance(file, dict) else file[4]),
                    "total_views": file['total_views'] if isinstance(file, dict) else file[5],
                    "total_downloads": file['total_downloads'] if isinstance(file, dict) else file[6],
                    "total_bandwidth": file['total_bandwidth'] if isinstance(file, dict) else file[7]
                })
            
            return web.json_response({
                "files": files_data,
                "total": total,
                "limit": limit,
                "offset": offset
            })
    except Exception as e:
        logging.error(f"Error in get_files: {e}")
        import traceback
        traceback.print_exc()
        return web.json_response({"error": str(e)}, status=500)

@routes.post("/api/auth/request-otp")
async def request_otp(request):
    """Request OTP for login"""
    try:
        data = await request.json()
        telegram_id = data.get('telegram_id')
        
        if not telegram_id:
            return web.json_response({"error": "Telegram ID is required"}, status=400)
        
        # Generate 6-digit OTP
        import secrets
        otp = ''.join([str(secrets.randbelow(10)) for _ in range(6)])
        
        async with db_manager.pool.acquire() if not db_manager.is_sqlite else db_manager.sqlite_conn as conn:
            # Store OTP in database
            query = """
                INSERT INTO otp_tokens (user_id, otp_code, created_at, expires_at, used)
                VALUES (?, ?, ?, ?, ?)
            """
            now = datetime.now()
            expires_at = now + timedelta(minutes=Var.OTP_EXPIRY_MINUTES)
            
            await db_manager.execute(query, telegram_id, otp, now, expires_at, False)
            
            if db_manager.is_sqlite:
                await conn.commit()
        
        # TODO: Send OTP via Telegram bot
        logging.info(f"Generated OTP for {telegram_id}: {otp}")
        
        return web.json_response({
            "success": True,
            "message": "OTP sent successfully",
            "otp": otp  # In production, don't return OTP - send via Telegram
        })
    except Exception as e:
        logging.error(f"Error in request_otp: {e}")
        return web.json_response({"error": str(e)}, status=500)

@routes.post("/api/auth/verify-otp")
async def verify_otp(request):
    """Verify OTP and issue JWT token"""
    try:
        data = await request.json()
        telegram_id = data.get('telegram_id')
        otp_code = data.get('otp_code')
        
        if not telegram_id or not otp_code:
            return web.json_response({"error": "Telegram ID and OTP are required"}, status=400)
        
        async with db_manager.pool.acquire() if not db_manager.is_sqlite else db_manager.sqlite_conn as conn:
            # Verify OTP
            query = """
                SELECT id, expires_at, used FROM otp_tokens
                WHERE user_id = ? AND otp_code = ?
                ORDER BY created_at DESC
                LIMIT 1
            """
            otp_record = await db_manager.fetchrow(query, telegram_id, otp_code)
            
            if not otp_record:
                return web.json_response({"error": "Invalid OTP"}, status=401)
            
            # Check if OTP is expired
            expires_at = otp_record['expires_at'] if isinstance(otp_record, dict) else otp_record[1]
            if isinstance(expires_at, str):
                expires_at = datetime.fromisoformat(expires_at)
            
            if datetime.now() > expires_at:
                return web.json_response({"error": "OTP expired"}, status=401)
            
            # Check if OTP is already used
            used = otp_record['used'] if isinstance(otp_record, dict) else otp_record[2]
            if used:
                return web.json_response({"error": "OTP already used"}, status=401)
            
            # Mark OTP as used
            update_query = "UPDATE otp_tokens SET used = ?, used_at = ? WHERE id = ?"
            otp_id = otp_record['id'] if isinstance(otp_record, dict) else otp_record[0]
            await db_manager.execute(update_query, True, datetime.now(), otp_id)
            
            if db_manager.is_sqlite:
                await conn.commit()
        
        # Generate JWT token
        token_payload = {
            "user_id": telegram_id,
            "exp": datetime.utcnow() + timedelta(hours=Var.JWT_EXPIRY_HOURS)
        }
        token = jwt.encode(token_payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
        
        return web.json_response({
            "success": True,
            "token": token,
            "user_id": telegram_id
        })
    except Exception as e:
        logging.error(f"Error in verify_otp: {e}")
        import traceback
        traceback.print_exc()
        return web.json_response({"error": str(e)}, status=500)

