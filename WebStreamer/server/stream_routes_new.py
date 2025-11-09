# Enhanced stream routes with database integration and new link system
import re
import time
import math
import logging
import secrets
import mimetypes
from aiohttp import web
from aiohttp.http_exceptions import BadStatusLine
from WebStreamer import bot_loop
from functools import partial
from WebStreamer.bot import multi_clients, work_loads
from WebStreamer.server.exceptions import FIleNotFound, InvalidHash
from WebStreamer import Var, utils, StartTime, __version__, StreamBot
from WebStreamer.database import db_manager
from WebStreamer.database.models import GeneratedLink, File, LinkAccessLog
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from hashlib import sha256
import urllib.parse

THREADPOOL = ThreadPoolExecutor(max_workers=1000)

async def sync_to_async(func, *args, wait=True, **kwargs):
    pfunc = partial(func, *args, **kwargs)
    future = bot_loop.run_in_executor(THREADPOOL, pfunc)
    return await future if wait else future

routes = web.RouteTableDef()

@routes.get("/", allow_head=True)
async def root_route_handler(_):
    return web.Response(
        text='<html> <head> <title>LinkerX CDN</title> <style> body{ margin:0; padding:0; width:100%; height:100%; color:#b0bec5; display:table; font-weight:100; font-family:Lato } .container{ text-align:center; display:table-cell; vertical-align:middle } .content{ text-align:center; display:inline-block } .message{ font-size:80px; margin-bottom:40px } .submessage{ font-size:40px; margin-bottom:40px } .copyright{ font-size:20px; } a{ text-decoration:none; color:#3498db } </style> </head> <body> <div class="container"> <div class="content"> <div class="message">LinkerX CDN</div> <div class="submessage">All Systems Operational since '+utils.get_readable_time(time.time() - StartTime)+'</div> <div class="copyright">Hash Hackers and LiquidX Projects</div> </div> </div> </body> </html>', 
        content_type="text/html"
    )

# NEW: File ID route - redirects to bot-specific stream
@routes.get("/f/{unique_file_id}", allow_head=True)
async def file_id_route_handler(request: web.Request):
    """New link system: /f/{unique_file_id} redirects to /bot{N}/{file_id}/{expiry}/{hash}"""
    try:
        unique_file_id = request.match_info['unique_file_id']
        
        # Get link details from database
        async with db_manager.pool.acquire() if not db_manager.is_sqlite else db_manager.sqlite_conn as conn:
            link_data = await GeneratedLink.get_by_unique_id(conn, unique_file_id)
            
            if not link_data:
                raise web.HTTPNotFound(
                    text=error_page("Link Not Found", "This link does not exist or has been deleted."),
                    content_type="text/html"
                )
            
            # Check if expired
            expiry_date = link_data['expiry_date']
            if isinstance(expiry_date, str):
                from dateutil import parser
                expiry_date = parser.parse(expiry_date)
            
            if expiry_date < datetime.now():
                raise web.HTTPForbidden(
                    text=error_page("Link Expired", "This link has expired."),
                    content_type="text/html"
                )
            
            # Get file and bot mapping
            file_id = link_data['file_id']
            bot_mapping = await FileBotMapping.get_bot_for_file(conn, file_id)
            
            if not bot_mapping:
                raise web.HTTPNotFound(
                    text=error_page("File Not Found", "File data not found in storage."),
                    content_type="text/html"
                )
            
            bot_index = bot_mapping['bot_index'] if isinstance(bot_mapping, dict) else bot_mapping[2]
            telegram_message_id = bot_mapping['telegram_message_id'] if isinstance(bot_mapping, dict) else bot_mapping[4]
            channel_id = bot_mapping['channel_id'] if isinstance(bot_mapping, dict) else bot_mapping[5]
            
            # Generate hash for security
            expiry_timestamp = int(expiry_date.timestamp())
            hash_data = f"{channel_id}|{telegram_message_id}|{expiry_timestamp}|{Var.SECRET_KEY}"
            hash_value = sha256(hash_data.encode()).hexdigest()
            
            # Increment access count
            link_id = link_data['id']
            await GeneratedLink.increment_access(conn, link_id)
            
            # Log access (view)
            ip_address = request.headers.get('X-Forwarded-For', request.remote)
            user_agent = request.headers.get('User-Agent', '')
            await LinkAccessLog.log_access(conn, link_id, ip_address, user_agent, 0, 'view')
            
            # Increment file views
            await File.increment_views(conn, file_id)
            
            if db_manager.is_sqlite:
                await conn.commit()
        
        # Redirect to bot-specific stream URL
        redirect_url = f"/bot{bot_index}/{telegram_message_id}/{expiry_timestamp}/{hash_value}"
        
        raise web.HTTPFound(redirect_url)
        
    except web.HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error in file_id_route_handler: {e}")
        import traceback
        traceback.print_exc()
        raise web.HTTPInternalServerError(
            text=error_page("Server Error", str(e)),
            content_type="text/html"
        )

# Bot-specific stream route
@routes.get("/bot{bot_index}/{message_id}/{expiry_time}/{hash_value}", allow_head=True)
async def bot_stream_handler(request: web.Request):
    """Handle bot-specific streaming"""
    try:
        bot_index = int(request.match_info['bot_index'])
        message_id = int(request.match_info['message_id'])
        expiry_time = int(request.match_info['expiry_time'])
        hash_value = request.match_info['hash_value']
        
        # Verify expiration
        current_time = int(time.time())
        if expiry_time < current_time:
            raise web.HTTPForbidden(
                text=error_page("Link Expired", "This streaming link has expired."),
                content_type="text/html"
            )
        
        # Get bot client
        if bot_index not in multi_clients:
            bot_index = 0  # Fallback to main bot
        
        client = multi_clients[bot_index]
        channel_id = Var.BIN_CHANNEL
        
        # Verify hash
        hash_data = f"{channel_id}|{message_id}|{expiry_time}|{Var.SECRET_KEY}"
        expected_hash = sha256(hash_data.encode()).hexdigest()
        
        if hash_value != expected_hash:
            raise web.HTTPForbidden(
                text=error_page("Invalid Hash", "Link has been tampered with."),
                content_type="text/html"
            )
        
        # Stream the file
        return await media_streamer(request, message_id, channel_id, bot_index)
        
    except web.HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error in bot_stream_handler: {e}")
        raise web.HTTPInternalServerError(
            text=error_page("Streaming Error", str(e)),
            content_type="text/html"
        )

class_cache = {}

async def media_streamer(request: web.Request, message_id: int, channel_id: int, bot_index: int = None):
    """Stream media file"""
    try:
        range_header = request.headers.get("Range", 0)
        
        # Use specified bot or select least busy
        if bot_index is not None and bot_index in multi_clients:
            faster_client = multi_clients[bot_index]
            index = bot_index
        else:
            index = min(work_loads, key=work_loads.get)
            faster_client = multi_clients[index]
        
        if Var.MULTI_CLIENT:
            logging.info(f"Client {index} is now serving {request.remote}")

        if faster_client in class_cache:
            tg_connect = class_cache[faster_client]
            logging.debug(f"Using cached ByteStreamer object for client {index}")
        else:
            logging.debug(f"Creating new ByteStreamer object for client {index}")
            tg_connect = utils.ByteStreamer(faster_client)
            class_cache[faster_client] = tg_connect
        
        logging.debug("before calling get_file_properties")
        file_id = await tg_connect.get_file_properties(message_id, channel_id)
        logging.debug("after calling get_file_properties")

        file_size = file_id.file_size

        if range_header:
            from_bytes, until_bytes = range_header.replace("bytes=", "").split("-")
            from_bytes = int(from_bytes)
            until_bytes = int(until_bytes) if until_bytes else file_size - 1
        else:
            from_bytes = request.http_range.start or 0
            until_bytes = (request.http_range.stop or file_size) - 1

        if (until_bytes > file_size) or (from_bytes < 0) or (until_bytes < from_bytes):
            return web.Response(
                status=416,
                body="416: Range not satisfiable",
                headers={"Content-Range": f"bytes */{file_size}"},
            )

        chunk_size = 1024 * 1024
        until_bytes = min(until_bytes, file_size - 1)

        offset = from_bytes - (from_bytes % chunk_size)
        first_part_cut = from_bytes - offset
        last_part_cut = until_bytes % chunk_size + 1

        req_length = until_bytes - from_bytes + 1
        part_count = math.ceil(until_bytes / chunk_size) - math.floor(offset / chunk_size)
        body = tg_connect.yield_file(
            file_id, index, offset, first_part_cut, last_part_cut, part_count, chunk_size
        )
        mime_type = file_id.mime_type
        file_name = file_id.file_name
        disposition = "attachment"

        if mime_type:
            if not file_name:
                try:
                    file_name = f"{secrets.token_hex(2)}.{mime_type.split('/')[1]}"
                except (IndexError, AttributeError):
                    file_name = f"{secrets.token_hex(2)}.unknown"
        else:
            if file_name:
                mime_type = mimetypes.guess_type(file_id.file_name)
            else:
                mime_type = "application/octet-stream"
                file_name = f"{secrets.token_hex(2)}.unknown"

        if "video/" in mime_type or "audio/" in mime_type or "/html" in mime_type:
            disposition = "inline"
        
        # Log download in database (background task)
        try:
            asyncio.create_task(log_download(message_id, channel_id))
        except:
            pass

        return web.Response(
            status=206 if range_header else 200,
            body=body,
            headers={
                "Content-Type": f"{mime_type}",
                "Content-Range": f"bytes {from_bytes}-{until_bytes}/{file_size}",
                "Content-Length": str(req_length),
                "Content-Disposition": f'{disposition}; filename="{file_name}"',
                "Accept-Ranges": "bytes",
            },
        )
    except Exception as e:
        logging.error(f"Error in media streamer: {str(e)}")
        return web.Response(
            text=error_page("Streaming Error", str(e)),
            content_type="text/html"
        )

async def log_download(message_id: int, channel_id: int):
    """Log download to database"""
    try:
        async with db_manager.pool.acquire() if not db_manager.is_sqlite else db_manager.sqlite_conn as conn:
            # Find file by message_id and channel_id
            query = '''
                SELECT file_id FROM file_bot_mapping
                WHERE telegram_message_id = ? AND channel_id = ?
            ''' if db_manager.is_sqlite else '''
                SELECT file_id FROM file_bot_mapping
                WHERE telegram_message_id = $1 AND channel_id = $2
            '''
            result = await db_manager.fetchrow(query, message_id, channel_id)
            
            if result:
                file_id = result['file_id'] if isinstance(result, dict) else result[0]
                await File.increment_downloads(conn, file_id)
                
                if db_manager.is_sqlite:
                    await conn.commit()
    except Exception as e:
        logging.error(f"Error logging download: {e}")

async def formatFileSize(bytes):
    if bytes == 0:
        return "0B"
    k = 1024
    sizes = ["B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB"]
    i = math.floor(math.log(bytes) / math.log(k))
    return f"{round(bytes / math.pow(k, i), 2)} {sizes[i]}"

def error_page(title: str, message: str) -> str:
    """Generate error page HTML"""
    return f'''<html>
    <head>
        <title>LinkerX CDN - {title}</title>
        <style>
            body {{ margin:0; padding:0; width:100%; height:100%; color:#b0bec5; 
                   display:table; font-weight:100; font-family:Lato }}
            .container {{ text-align:center; display:table-cell; vertical-align:middle }}
            .content {{ text-align:center; display:inline-block }}
            .message {{ font-size:60px; margin-bottom:40px }}
            .submessage {{ font-size:30px; margin-bottom:40px; color:#e74c3c }}
            .copyright {{ font-size:20px; }}
            a {{ text-decoration:none; color:#3498db }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="content">
                <div class="message">LinkerX CDN</div>
                <div class="submessage">{title}</div>
                <p>{message}</p>
                <div class="copyright">Hash Hackers and LiquidX Projects</div>
            </div>
        </div>
    </body>
    </html>'''

import asyncio

# ========== API Endpoints for Web UI ==========

@routes.get("/api/stats", allow_head=True)
async def api_stats_handler(request: web.Request):
    """Get global statistics"""
    try:
        async with db_manager.pool.acquire() if not db_manager.is_sqlite else db_manager.sqlite_conn as conn:
            # Get total files
            total_files_query = 'SELECT COUNT(*) as count FROM files'
            total_files_result = await conn.fetchrow(total_files_query)
            total_files = total_files_result['count'] if total_files_result else 0
            
            # Get total users
            total_users_query = 'SELECT COUNT(*) as count FROM users'
            total_users_result = await conn.fetchrow(total_users_query)
            total_users = total_users_result['count'] if total_users_result else 0
            
            # Get total views and downloads
            total_views_query = 'SELECT SUM(total_views) as views FROM files'
            total_views_result = await conn.fetchrow(total_views_query)
            total_views = total_views_result['views'] if total_views_result and total_views_result['views'] else 0
            
            total_downloads_query = 'SELECT SUM(total_downloads) as downloads FROM files'
            total_downloads_result = await conn.fetchrow(total_downloads_query)
            total_downloads = total_downloads_result['downloads'] if total_downloads_result and total_downloads_result['downloads'] else 0
            
            # Get active links count
            active_links_query = 'SELECT COUNT(*) as count FROM generated_links WHERE is_active = TRUE AND expiry_date > NOW()' if not db_manager.is_sqlite else 'SELECT COUNT(*) as count FROM generated_links WHERE is_active = 1 AND expiry_date > datetime("now")'
            active_links_result = await conn.fetchrow(active_links_query)
            active_links = active_links_result['count'] if active_links_result else 0
            
            stats = {
                'total_files': total_files,
                'total_users': total_users,
                'total_views': total_views,
                'total_downloads': total_downloads,
                'active_links': active_links,
                'active_bots': len(multi_clients),
                'uptime': utils.get_readable_time(time.time() - StartTime)
            }
            
            return web.json_response(stats)
            
    except Exception as e:
        logging.error(f"Error in api_stats_handler: {e}")
        return web.json_response({'error': str(e)}, status=500)

@routes.get("/api/files", allow_head=True)
async def api_files_handler(request: web.Request):
    """Get paginated file list"""
    try:
        # Get query parameters
        page = int(request.query.get('page', 1))
        limit = int(request.query.get('limit', 20))
        search = request.query.get('search', '').strip()
        sort_by = request.query.get('sort', 'upload_date')  # upload_date, total_views, total_downloads, file_size
        order = request.query.get('order', 'desc').upper()
        
        # Validate inputs
        page = max(1, page)
        limit = min(100, max(1, limit))
        offset = (page - 1) * limit
        
        if order not in ['ASC', 'DESC']:
            order = 'DESC'
        
        if sort_by not in ['upload_date', 'total_views', 'total_downloads', 'file_size', 'file_name']:
            sort_by = 'upload_date'
        
        async with db_manager.pool.acquire() if not db_manager.is_sqlite else db_manager.sqlite_conn as conn:
            # Build query
            if search:
                if db_manager.is_sqlite:
                    count_query = 'SELECT COUNT(*) as count FROM files WHERE file_name LIKE ?'
                    files_query = f'''
                        SELECT f.*, u.username, u.first_name 
                        FROM files f
                        LEFT JOIN users u ON f.uploaded_by = u.id
                        WHERE f.file_name LIKE ?
                        ORDER BY f.{sort_by} {order}
                        LIMIT ? OFFSET ?
                    '''
                    count_result = await conn.fetchrow(count_query, f'%{search}%')
                    files_result = await conn.fetch(files_query, f'%{search}%', limit, offset)
                else:
                    count_query = 'SELECT COUNT(*) as count FROM files WHERE file_name ILIKE $1'
                    files_query = f'''
                        SELECT f.*, u.username, u.first_name 
                        FROM files f
                        LEFT JOIN users u ON f.uploaded_by = u.id
                        WHERE f.file_name ILIKE $1
                        ORDER BY f.{sort_by} {order}
                        LIMIT $2 OFFSET $3
                    '''
                    count_result = await conn.fetchrow(count_query, f'%{search}%')
                    files_result = await conn.fetch(files_query, f'%{search}%', limit, offset)
            else:
                if db_manager.is_sqlite:
                    count_query = 'SELECT COUNT(*) as count FROM files'
                    files_query = f'''
                        SELECT f.*, u.username, u.first_name 
                        FROM files f
                        LEFT JOIN users u ON f.uploaded_by = u.id
                        ORDER BY f.{sort_by} {order}
                        LIMIT ? OFFSET ?
                    '''
                    count_result = await conn.fetchrow(count_query)
                    files_result = await conn.fetch(files_query, limit, offset)
                else:
                    count_query = 'SELECT COUNT(*) as count FROM files'
                    files_query = f'''
                        SELECT f.*, u.username, u.first_name 
                        FROM files f
                        LEFT JOIN users u ON f.uploaded_by = u.id
                        ORDER BY f.{sort_by} {order}
                        LIMIT $1 OFFSET $2
                    '''
                    count_result = await conn.fetchrow(count_query)
                    files_result = await conn.fetch(files_query, limit, offset)
            
            total_count = count_result['count'] if count_result else 0
            total_pages = math.ceil(total_count / limit)
            
            # Format files
            files = []
            for row in files_result:
                file_dict = dict(row)
                # Format file size
                file_dict['file_size_formatted'] = await formatFileSize(file_dict.get('file_size', 0))
                # Format upload date
                upload_date = file_dict.get('upload_date')
                if upload_date:
                    if isinstance(upload_date, str):
                        file_dict['upload_date'] = upload_date
                    else:
                        file_dict['upload_date'] = upload_date.isoformat()
                files.append(file_dict)
            
            response = {
                'files': files,
                'pagination': {
                    'current_page': page,
                    'total_pages': total_pages,
                    'total_count': total_count,
                    'limit': limit,
                    'has_next': page < total_pages,
                    'has_prev': page > 1
                }
            }
            
            return web.json_response(response)
            
    except Exception as e:
        logging.error(f"Error in api_files_handler: {e}")
        import traceback
        traceback.print_exc()
        return web.json_response({'error': str(e)}, status=500)

@routes.get("/api/files/{file_id}", allow_head=True)
async def api_file_detail_handler(request: web.Request):
    """Get detailed file information"""
    try:
        file_id = int(request.match_info['file_id'])
        
        async with db_manager.pool.acquire() if not db_manager.is_sqlite else db_manager.sqlite_conn as conn:
            # Get file details with user info
            if db_manager.is_sqlite:
                file_query = '''
                    SELECT f.*, u.username, u.first_name, u.last_name
                    FROM files f
                    LEFT JOIN users u ON f.uploaded_by = u.id
                    WHERE f.id = ?
                '''
                file_result = await conn.fetchrow(file_query, file_id)
            else:
                file_query = '''
                    SELECT f.*, u.username, u.first_name, u.last_name
                    FROM files f
                    LEFT JOIN users u ON f.uploaded_by = u.id
                    WHERE f.id = $1
                '''
                file_result = await conn.fetchrow(file_query, file_id)
            
            if not file_result:
                return web.json_response({'error': 'File not found'}, status=404)
            
            file_data = dict(file_result)
            file_data['file_size_formatted'] = await formatFileSize(file_data.get('file_size', 0))
            
            # Format upload date
            upload_date = file_data.get('upload_date')
            if upload_date and not isinstance(upload_date, str):
                file_data['upload_date'] = upload_date.isoformat()
            
            # Get bot mappings
            if db_manager.is_sqlite:
                mappings_query = 'SELECT * FROM file_bot_mapping WHERE file_id = ?'
                mappings_result = await conn.fetch(mappings_query, file_id)
            else:
                mappings_query = 'SELECT * FROM file_bot_mapping WHERE file_id = $1'
                mappings_result = await conn.fetch(mappings_query, file_id)
            
            file_data['bot_mappings'] = [dict(row) for row in mappings_result]
            
            # Get recent access logs (last 10)
            if db_manager.is_sqlite:
                logs_query = '''
                    SELECT lal.* FROM link_access_logs lal
                    INNER JOIN generated_links gl ON lal.link_id = gl.id
                    WHERE gl.file_id = ?
                    ORDER BY lal.accessed_at DESC
                    LIMIT 10
                '''
                logs_result = await conn.fetch(logs_query, file_id)
            else:
                logs_query = '''
                    SELECT lal.* FROM link_access_logs lal
                    INNER JOIN generated_links gl ON lal.link_id = gl.id
                    WHERE gl.file_id = $1
                    ORDER BY lal.accessed_at DESC
                    LIMIT 10
                '''
                logs_result = await conn.fetch(logs_query, file_id)
            
            file_data['recent_access'] = [dict(row) for row in logs_result]
            
            return web.json_response(file_data)
            
    except ValueError:
        return web.json_response({'error': 'Invalid file ID'}, status=400)
    except Exception as e:
        logging.error(f"Error in api_file_detail_handler: {e}")
        return web.json_response({'error': str(e)}, status=500)
