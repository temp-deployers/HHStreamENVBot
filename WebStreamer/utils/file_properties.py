from pyrogram import Client
from typing import Any, Optional
from pyrogram.types import Message
from pyrogram.file_id import FileId
from pyrogram.raw.types.messages import Messages
from WebStreamer.server.exceptions import FIleNotFound
import logging


async def parse_file_id(message: "Message") -> Optional[FileId]:
    media = get_media_from_message(message)
    if media:
        return FileId.decode(media.file_id)

async def parse_file_unique_id(message: "Messages") -> Optional[str]:
    media = get_media_from_message(message)
    if media:
        return media.file_unique_id

async def get_file_ids(client: Client, chat_id: int, message_id: int) -> Optional[FileId]:
    try:
        message = await client.get_messages(chat_id, message_id)
    except Exception as e:
        error_str = str(e).lower()
        # If we get a "Peer id invalid" error, try to resolve the peer first
        if "peer id invalid" in error_str or "peer_id_invalid" in error_str:
            logging.info(f"Peer id invalid for chat {chat_id}, attempting to resolve peer...")
            try:
                # Try to resolve peer by getting chat info
                await client.get_chat(chat_id)
                logging.info(f"Successfully resolved peer by getting chat info for {chat_id}")
            except Exception as chat_error:
                logging.warning(f"Failed to get chat info for {chat_id}: {chat_error}")
                try:
                    # Alternative: Try to get chat members to interact with the chat
                    logging.info(f"Attempting to fetch chat members for {chat_id}")
                    async for _ in client.get_chat_members(chat_id, limit=1):
                        break
                    logging.info(f"Successfully resolved peer by fetching chat members for {chat_id}")
                except Exception as members_error:
                    logging.error(f"Failed to fetch chat members for {chat_id}: {members_error}")
            
            # Retry getting the message after resolving peer
            try:
                message = await client.get_messages(chat_id, message_id)
                logging.info(f"Successfully fetched message {message_id} from chat {chat_id} after peer resolution")
            except Exception as retry_error:
                logging.error(f"Failed to get message even after peer resolution: {retry_error}")
                raise
        else:
            # Re-raise if it's a different error
            raise
    
    if message.empty:
        raise FIleNotFound
    media = get_media_from_message(message)
    file_unique_id = await parse_file_unique_id(message)
    file_id = await parse_file_id(message)
    setattr(file_id, "file_size", getattr(media, "file_size", 0))
    setattr(file_id, "mime_type", getattr(media, "mime_type", ""))
    setattr(file_id, "file_name", getattr(media, "file_name", ""))
    setattr(file_id, "unique_id", file_unique_id)
    return file_id

def get_media_from_message(message: "Message") -> Any:
    media_types = (
        "audio",
        "document",
        "photo",
        "sticker",
        "animation",
        "video",
        "voice",
        "video_note",
    )
    for attr in media_types:
        media = getattr(message, attr, None)
        if media:
            return media


def get_hash(media_msg: Message) -> str:
    media = get_media_from_message(media_msg)
    return getattr(media, "file_unique_id", "")[:6]

def get_name(media_msg: Message) -> str:
    media = get_media_from_message(media_msg)
    return getattr(media, 'file_name', "")
