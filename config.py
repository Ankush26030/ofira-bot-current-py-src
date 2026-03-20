import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    """Bot configuration class"""
    
    # Discord Configuration
    DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
    OWNER_IDS = {int(id) for id in os.getenv('OWNER_IDS', '').split(',') if id.strip()}
    
    # MongoDB Configuration
    MONGODB_URI = os.getenv('MONGODB_URI')
    
    # Lavalink Configuration
    LAVALINK_HOST = os.getenv('LAVALINK_HOST', 'orion.endercloud.in')
    LAVALINK_PORT = int(os.getenv('LAVALINK_PORT', 5086))
    LAVALINK_PASSWORD = os.getenv('LAVALINK_PASSWORD', 'https://dsc.gg/nothingbot')
    LAVALINK_IDENTIFIER = os.getenv('LAVALINK_IDENTIFIER', 'MAIN')
    LAVALINK_SECURE = os.getenv('LAVALINK_SECURE', 'False').lower() == 'true'
    
    # Bot Settings
    DEFAULT_PREFIX = ','
    EMBED_COLOR = 0x5865F2  # Discord blurple blue
    ERROR_COLOR = 0xed4245  # Discord red
    SUCCESS_COLOR = 0x57f287  # Discord green
    SUPPORT_SERVER = "https://dsc.gg/nothingbot"
    
    # Sharding Configuration
    SHARD_COUNT = int(os.getenv('SHARD_COUNT')) if os.getenv('SHARD_COUNT') and os.getenv('SHARD_COUNT').strip() else None
    CLUSTER_ID = int(os.getenv('CLUSTER_ID', '0'))
    CLUSTER_COUNT = int(os.getenv('CLUSTER_COUNT', '1'))
    
    # Spotify Configuration
    SPOTIFY_CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID', 'da9f4ec4a570497294834ef957cfced6')
    SPOTIFY_CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET', '7b352abdcfaf4a6a9e1fdbda816edd99')
    
    # Custom Emojis
    EMOJI_PLAYING = "<a:Playing:1285523769603133482>"
    EMOJI_TICK = "<:bluecheck:1475564639101386968>"
    EMOJI_CROSS = "<:bluecross:1475565027305197822>"
    EMOJI_ADDED = "<:add:1285564587995041812>"
    EMOJI_DURATION = "<:duration:1285682239014961183>"
    EMOJI_REQUESTER = "<:requester:1285683020484972545>"
    EMOJI_VOLUME_LOW = "<:low_dec:1285523560303038466>"
    EMOJI_VOLUME_HIGH = "<:volume_up:1285523427859365920>"
    EMOJI_DOT = "<:Dot:1285522787934535743>"
    EMOJI_SEARCH = "<:Search:1287024936606761074>"
    EMOJI_INFO = "<:Info:1278721750846406739>"
    
    # Logging Webhooks
    JOIN_LOG_WEBHOOK = os.getenv('JOIN_LOG_WEBHOOK')
    LEAVE_LOG_WEBHOOK = os.getenv('LEAVE_LOG_WEBHOOK')
    COMMAND_LOG_WEBHOOK = os.getenv('COMMAND_LOG_WEBHOOK')
    
    @classmethod
    def validate(cls):
        """Validate required configuration"""
        if not cls.DISCORD_TOKEN:
            raise ValueError("DISCORD_TOKEN is required in .env file")
        if not cls.MONGODB_URI:
            raise ValueError("MONGODB_URI is required in .env file")
        return True
