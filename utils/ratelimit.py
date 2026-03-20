from discord.ext import commands

# Rate limit decorators for different command types

def music_cooldown():
    """Cooldown for music commands (play, skip, etc.) - 3 seconds per user"""
    return commands.cooldown(1, 3.0, commands.BucketType.user)

def utility_cooldown():
    """Cooldown for utility commands (ping, stats, etc.) - 5 seconds per user"""
    return commands.cooldown(1, 5.0, commands.BucketType.user)

def moderation_cooldown():
    """Cooldown for moderation commands - 5 seconds per user"""
    return commands.cooldown(1, 5.0, commands.BucketType.user)

def filter_cooldown():
    """Cooldown for filter commands - 4 seconds per user"""
    return commands.cooldown(1, 4.0, commands.BucketType.user)

def afk_cooldown():
    """Cooldown for AFK command - 10 seconds per user"""
    return commands.cooldown(1, 10.0, commands.BucketType.user)

def spotify_cooldown():
    """Cooldown for Spotify commands - 5 seconds per user"""
    return commands.cooldown(1, 5.0, commands.BucketType.user)

def search_cooldown():
    """Cooldown for search commands - 5 seconds per user"""
    return commands.cooldown(1, 5.0, commands.BucketType.user)

def playlist_cooldown():
    """Cooldown for playlist commands - 3 seconds per user"""
    return commands.cooldown(1, 3.0, commands.BucketType.user)

def settings_cooldown():
    """Cooldown for settings commands - 10 seconds per user"""
    return commands.cooldown(1, 10.0, commands.BucketType.user)

def giveaway_cooldown():
    """Cooldown for giveaway commands - 5 seconds per user"""
    return commands.cooldown(1, 5.0, commands.BucketType.user)
