# This file is a part of TG
# Coding : Jyothis Jayanth [@EverythingSuckz]
# Enhanced by Hash Hackers & LiquidX Projects

from os import environ
from dotenv import load_dotenv

load_dotenv()


class Var(object):
    # Telegram Configuration
    MULTI_CLIENT = False
    API_ID = int(environ.get("API_ID"))
    API_HASH = str(environ.get("API_HASH"))
    BOT_TOKEN = str(environ.get("BOT_TOKEN"))
    SLEEP_THRESHOLD = int(environ.get("SLEEP_THRESHOLD", "60"))
    WORKERS = int(environ.get("WORKERS", "6"))
    
    # Channel Configuration
    BIN_CHANNEL = int(environ.get("BIN_CHANNEL", None))
    BIN_CHANNEL_WITHOUT_MINUS = int(environ.get("BIN_CHANNEL_WITHOUT_MINUS", None))
    
    # Server Configuration
    PORT = int(environ.get("BOT_PORT", environ.get("PORT", 8080)))
    BIND_ADDRESS = str(environ.get("BIND_ADDRESS", "0.0.0.0"))
    PING_INTERVAL = int(environ.get("PING_INTERVAL", "1200"))
    HAS_SSL = environ.get("HAS_SSL", False)
    HAS_SSL = True if str(HAS_SSL).lower() == "true" else False
    NO_PORT = environ.get("NO_PORT", False)
    NO_PORT = True if str(NO_PORT).lower() == "true" else False
    
    # Heroku Detection
    if "DYNO" in environ:
        ON_HEROKU = True
        APP_NAME = str(environ.get("APP_NAME"))
    else:
        ON_HEROKU = False
    
    # FQDN and URL Configuration
    FQDN = (
        str(environ.get("FQDN", BIND_ADDRESS))
        if not ON_HEROKU or environ.get("FQDN")
        else APP_NAME + ".herokuapp.com"
    )
    if ON_HEROKU:
        URL = f"https://{FQDN}/"
    else:
        URL = "http{}://{}{}/".format(
            "s" if HAS_SSL else "", FQDN, ""
        )
    
    # Database Configuration
    DATABASE_URL = str(environ.get("DATABASE_URL", ""))
    
    # Security Keys (moved from hardcoded)
    SECRET_KEY = str(environ.get("SECRET_KEY", ""))
    AES_KEY = str(environ.get("AES_KEY", "BHADOO9854752658"))
    AES_IV = str(environ.get("AES_IV", "CLOUD54158954721"))
    
    # GitHub Session Storage
    GITHUB_SESSION_KEY = str(environ.get("GITHUB_SESSION_KEY", ""))
    
    # Rate Limiting
    RATE_LIMIT_PER_5MIN = int(environ.get("RATE_LIMIT_PER_5MIN", "1"))
    RATE_LIMIT_PER_HOUR = int(environ.get("RATE_LIMIT_PER_HOUR", "5"))
    RATE_LIMIT_PER_DAY = int(environ.get("RATE_LIMIT_PER_DAY", "20"))
    
    # OTP Configuration
    OTP_EXPIRY_MINUTES = int(environ.get("OTP_EXPIRY_MINUTES", "5"))
    JWT_SECRET = str(environ.get("JWT_SECRET", ""))
    JWT_EXPIRY_HOURS = int(environ.get("JWT_EXPIRY_HOURS", "24"))
    
    # Feature Toggles
    ALLOW_PRIVATE_CHAT = environ.get("ALLOW_PRIVATE_CHAT", "True")
    ALLOW_PRIVATE_CHAT = True if str(ALLOW_PRIVATE_CHAT).lower() == "true" else False
    ENABLE_CHANNEL_TRACKING = environ.get("ENABLE_CHANNEL_TRACKING", "False")
    ENABLE_CHANNEL_TRACKING = True if str(ENABLE_CHANNEL_TRACKING).lower() == "true" else False
    COPY_FILES_TO_CHANNEL = environ.get("COPY_FILES_TO_CHANNEL", "False")
    COPY_FILES_TO_CHANNEL = True if str(COPY_FILES_TO_CHANNEL).lower() == "true" else False
