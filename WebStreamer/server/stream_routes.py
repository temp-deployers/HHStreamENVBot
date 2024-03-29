# Taken from megadlbot_oss <https://github.com/eyaadh/megadlbot_oss/blob/master/mega/webserver/routes.py>
# Thanks to Eyaadh <https://github.com/eyaadh>

import re
import time
import math
import logging
import secrets
import mimetypes
import time
from aiohttp import web
from aiohttp.http_exceptions import BadStatusLine
from WebStreamer.bot import multi_clients, work_loads
from WebStreamer.server.exceptions import FIleNotFound, InvalidHash
from WebStreamer import Var, utils, StartTime, __version__, StreamBot
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
import base64
import urllib.parse
import hashlib

logging.basicConfig(level=logging.DEBUG)
#CBC with Fix IV
key = 'BHADOO9854752658' #16 char for AES128
#FIX IV
iv =  'CLOUD54158954721'.encode('utf-8') #16 char for AES128

SECRET_KEY = '647e2c1ac884418b5c270862a9a484105e88b11f097fa9d5ddd09eb4c53737bd'

def verify_sha256_key(channel_id, file_id, expiration_time, sha256_key):
    try:
        # Concatenate the components with the secret key
        data_to_hash = f"{channel_id}|{file_id}|{expiration_time}|{SECRET_KEY}".encode('utf-8')

        # Calculate the SHA-256 hash
        sha256_hash = hashlib.sha256(data_to_hash).hexdigest()

        # Compare the calculated hash with the received sha256_key
        return sha256_hash == sha256_key
    except Exception:
        return False

def decrypt(enc, key, iv):
    enc = base64.b64decode(enc)
    cipher = AES.new(key.encode('utf-8'), AES.MODE_CBC, iv)
    decrypted = unpad(cipher.decrypt(enc), 16)
    decrypted_str = decrypted.decode('utf-8')
    channel_id, message_id, expiration_time = decrypted_str.split('|')
    return channel_id, message_id, int(expiration_time)

routes = web.RouteTableDef()
@routes.get("/", allow_head=True)
async def root_route_handler(_):
    return web.json_response(
        {
            "server_status": "running",
            "uptime": utils.get_readable_time(time.time() - StartTime),
            "connected_bots": len(multi_clients),
            "loads": dict(
                ("bot" + str(c + 1), l)
                for c, (_, l) in enumerate(
                    sorted(work_loads.items(), key=lambda x: x[1], reverse=True)
                )
            ),
            "version": __version__,
        }
    )


@routes.get("/{path:.*}", allow_head=True)
async def stream_handler(request: web.Request):
    try:
        keybase = b"mkycctydbxdtlbqz"
        encrypted_code = urllib.parse.unquote(request.match_info['path'])
        logging.debug(f"Encrypted code Got: {encrypted_code}")

        # Splitting the received path into parts
        parts = encrypted_code.split("/")
        if len(parts) != 4:
            raise web.HTTPBadRequest(text="Invalid path format")

        channel_id, file_id, expiration_time, sha256_key = parts

        # Checking if the link has expired
        current_time = int(time.time())
        if int(expiration_time) < current_time:
            raise web.HTTPForbidden(text="Link is Expired")

        # Perform the integrity check using sha256_key (replace this with your own integrity check logic)
        if not verify_sha256_key(channel_id, file_id, expiration_time, sha256_key):
            raise web.HTTPForbidden(text="Integrity check failed")

        return await media_streamer(request, int(file_id), int(channel_id))
    except InvalidHash as e:
        raise web.HTTPForbidden(text=e.message)
    except FileNotFoundError as e:
        raise web.HTTPNotFound(text=e.message)
    except (AttributeError, BadStatusLine, ConnectionResetError):
        pass
    except Exception as e:
        logging.critical(e.with_traceback(None))
        error_message = str(e)
        logging.critical(error_message)
        raise web.HTTPInternalServerError(text=error_message)

class_cache = {}

async def media_streamer(request: web.Request, message_id: int, channel_id):
    range_header = request.headers.get("Range", 0)
    
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
