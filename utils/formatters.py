import wavelink
from typing import Optional


def format_duration(milliseconds: int) -> str:
    """Format duration from milliseconds to HH:MM:SS or MM:SS"""
    if milliseconds == 0:
        return "LIVE"
    
    seconds = milliseconds // 1000
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def format_position(position: int, duration: int, length: int = 20) -> str:
    """Create a progress bar for track position"""
    if duration == 0:
        return "🔴 LIVE"
    
    percentage = position / duration
    filled = int(length * percentage)
    bar = "━" * filled + "○" + "─" * (length - filled - 1)
    
    return f"`{format_duration(position)}` {bar} `{format_duration(duration)}`"


def format_queue_track(index: int, track: wavelink.Playable, is_current: bool = False) -> str:
    """Format a track for queue display"""
    prefix = "🎵 **Now Playing**" if is_current else f"`{index}.`"
    duration = format_duration(track.length)
    
    # Truncate title if too long
    title = track.title
    if len(title) > 50:
        title = title[:47] + "..."
    
    return f"{prefix} [{title}]({track.uri}) `[{duration}]`"


def format_source(track: wavelink.Playable) -> str:
    """Get emoji for track source"""
    source_map = {
        "youtube": "<:Youtube:1475566390160130171>",
        "spotify": "<:spotify:1475510920489730243>",
        "soundcloud": "<:SoundCloud:1475566685321822290>",
        "twitch": "📺",
        "bandcamp": "🎸",
        "vimeo": "📹",
    }
    
    source = track.source.lower() if hasattr(track, 'source') else "youtube"
    return source_map.get(source, "🎵")
