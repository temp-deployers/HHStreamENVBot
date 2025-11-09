# This file is a part of TG-
# Coding : Jyothis Jayanth [@EverythingSuckz]

from ..vars import Var
from pyrogram import Client, utils
from os import getcwd

utils.MIN_CHANNEL_ID = -1002947483647

StreamBot = Client(
    name="WebStreamer",  # This will create a session file named "WebStreamer.session"
    api_id=Var.API_ID,
    api_hash=Var.API_HASH,
    workdir=getcwd(),  # Ensure the working directory is set correctly
    plugins={"root": "WebStreamer/bot/plugins"},
    bot_token=Var.BOT_TOKEN,
    sleep_threshold=Var.SLEEP_THRESHOLD,
    workers=Var.WORKERS,
    in_memory=False,  # Set this to False to create a session file
)

multi_clients = {}
work_loads = {}
