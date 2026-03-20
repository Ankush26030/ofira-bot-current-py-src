import discord
import wavelink
from config import Config
from utils.formatters import format_duration, format_position, format_source


def create_track_embed(track: wavelink.Playable, title: str = "Now Playing") -> discord.Embed:
    """Create an embed for a track"""
    embed = discord.Embed(
        title=f"{format_source(track)} {title}",
        description=f"**[{track.title}]({track.uri})**",
        color=Config.EMBED_COLOR
    )
    
    # Add track info
    if track.author:
        embed.add_field(name=f"{Config.EMOJI_INFO} Artist", value=track.author, inline=True)
    
    embed.add_field(name=f"{Config.EMOJI_DURATION} Duration", value=format_duration(track.length), inline=True)
    
    # Add thumbnail if available
    if hasattr(track, 'artwork') and track.artwork:
        embed.set_thumbnail(url=track.artwork)
    elif hasattr(track, 'thumbnail') and track.thumbnail:
        embed.set_thumbnail(url=track.thumbnail)
    
    return embed


def create_nowplaying_embed(player: wavelink.Player) -> discord.Embed:
    """Create a detailed now playing embed"""
    track = player.current
    
    embed = discord.Embed(
        title=f"{Config.EMOJI_PLAYING} Now Playing",
        description=f"**[{track.title}]({track.uri})**",
        color=Config.EMBED_COLOR
    )
    
    # Add artist
    if track.author:
        embed.add_field(name=f"{Config.EMOJI_INFO} Artist", value=track.author, inline=True)
    
    # Add requester if available
    if hasattr(track, 'requester'):
        embed.add_field(name=f"{Config.EMOJI_REQUESTER} Requested by", value=track.requester.mention, inline=True)
    
    # Add player status
    status_parts = []
    if player.paused:
        status_parts.append("⏸️ Paused")
    
    # Get loop mode from custom player
    if hasattr(player, 'loop_mode'):
        if player.loop_mode == "track":
            status_parts.append("🔂 Loop Track")
        elif player.loop_mode == "queue":
            status_parts.append("🔁 Loop Queue")
    
    if hasattr(player, 'autoplay_enabled') and player.autoplay_enabled:
        status_parts.append("🎲 Autoplay")
    
    if status_parts:
        embed.add_field(name="Status", value=" | ".join(status_parts), inline=False)
    
    # Add volume with dynamic emoji
    volume_emoji = Config.EMOJI_VOLUME_LOW if player.volume < 50 else Config.EMOJI_VOLUME_HIGH
    embed.add_field(name=f"{volume_emoji} Volume", value=f"{player.volume}%", inline=True)
    
    # Add queue info
    if hasattr(player, 'queue') and not player.queue.is_empty:
        embed.add_field(name="In Queue", value=f"{player.queue.count} tracks", inline=True)
    
    # Add thumbnail
    if hasattr(track, 'artwork') and track.artwork:
        embed.set_thumbnail(url=track.artwork)
    elif hasattr(track, 'thumbnail') and track.thumbnail:
        embed.set_thumbnail(url=track.thumbnail)
    
    return embed


def create_queue_embed(player: wavelink.Player, page: int = 1, per_page: int = 10) -> discord.Embed:
    """Create a paginated queue embed"""
    embed = discord.Embed(
        title="🎵 Music Queue",
        color=Config.EMBED_COLOR
    )
    
    # Add current track
    if player.current:
        from utils.formatters import format_queue_track
        current_info = format_queue_track(0, player.current, is_current=True)
        embed.add_field(name="Current Track", value=current_info, inline=False)
    
    # Add queue tracks
    if hasattr(player, 'queue') and not player.queue.is_empty:
        queue_list = list(player.queue)
        total_pages = (len(queue_list) + per_page - 1) // per_page
        start = (page - 1) * per_page
        end = start + per_page
        
        queue_text = []
        for i, track in enumerate(queue_list[start:end], start=start+1):
            from utils.formatters import format_queue_track
            queue_text.append(format_queue_track(i, track))
        
        if queue_text:
            embed.add_field(
                name=f"Up Next (Page {page}/{total_pages})",
                value="\n".join(queue_text),
                inline=False
            )
        
        # Add total duration
        total_duration = sum(track.length for track in queue_list)
        embed.set_footer(text=f"Total: {len(queue_list)} tracks | Duration: {format_duration(total_duration)}")
    else:
        embed.add_field(name="Queue", value="*Queue is empty*", inline=False)
    
    return embed


def create_error_embed(message: str) -> discord.Embed:
    """Create an error embed"""
    return discord.Embed(
        description=f"{Config.EMOJI_CROSS} {message}",
        color=Config.ERROR_COLOR
    )


def create_success_embed(message: str) -> discord.Embed:
    """Create a success embed"""
    return discord.Embed(
        description=f"{Config.EMOJI_TICK} {message}",
        color=Config.SUCCESS_COLOR
    )
