import discord
from discord.ext import commands
import wavelink
import asyncio
from player import CustomPlayer, safe_connect
from utils.checks import in_voice, same_voice
from utils.ratelimit import music_cooldown
from utils.formatters import format_duration
from config import Config


def _play_view(bot, title: str, body: str, *, error: bool = False) -> discord.ui.LayoutView:
    """Build a Components V2 view for play messages."""
    view = discord.ui.LayoutView()
    colour = discord.Colour(bot.config.ERROR_COLOR if error else bot.config.SUCCESS_COLOR)
    container = discord.ui.Container(accent_colour=colour)
    container.add_item(discord.ui.TextDisplay(f"### {title}"))
    container.add_item(discord.ui.Separator())
    container.add_item(discord.ui.TextDisplay(body))
    view.add_item(container)
    return view

class Play(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="play", aliases=["p"])
    @music_cooldown()
    @in_voice()
    async def play(self, ctx: commands.Context, *, query: str = None):
        """Play a song from YouTube, Spotify, etc."""
        
        if query is None:
            player: CustomPlayer = ctx.guild.voice_client
            if player and player.paused:
                await player.pause(False)
                view = _play_view(self.bot, "Resumed", "Resumed playback")
                return await ctx.send(view=view)
            elif player and player.playing:
                 view = _play_view(self.bot, "Already Playing", "Music is already playing. Queue a song with `,play <song>`", error=True)
                 return await ctx.send(view=view)
            else:
                 view = _play_view(self.bot, "Missing Query", "Please provide a song to play! Usage: `,play <song>`", error=True)
                 return await ctx.send(view=view)
        
        # Join voice channel if not connected
        if not ctx.guild.voice_client:
            try:
                vc = await safe_connect(ctx.author.voice.channel)
            except Exception as e:
                view = _play_view(self.bot, "Connection Failed", f"Failed to join voice channel: {str(e)}", error=True)
                return await ctx.send(view=view)
        
        vc: CustomPlayer = ctx.guild.voice_client
        vc.text_channel = ctx.channel
        
        # Check if user is in same channel (if bot was already connected)
        if vc.channel != ctx.author.voice.channel:
            view = _play_view(self.bot, "Wrong Channel", "You must be in the same voice channel as me!", error=True)
            return await ctx.send(view=view)

        # Search for tracks
        source = None
        if not query.startswith(("http:", "https:")):
            source = self.bot.search_source
            
            
        try:
            print(f"DEBUG: Searching for '{query}' source={'None' if not source else source}")
            # Wavelink 3.x handles source kwarg
            if source:
                tracks: wavelink.Search = await wavelink.Playable.search(query, source=source)
            else:
                tracks: wavelink.Search = await wavelink.Playable.search(query)
            
            print(f"DEBUG: Search result type: {type(tracks)}")
            if tracks:
                print(f"DEBUG: Found {len(tracks)} tracks")
            else:
                print("DEBUG: found 0 tracks")

        except Exception as e:
            print(f"DEBUG: Search Exception: {e}")
            view = _play_view(self.bot, "Search Error", f"Search error: {e}", error=True)
            return await ctx.send(view=view)
        
        if not tracks:
            view = _play_view(self.bot, "Not Found", "No tracks found.", error=True)
            return await ctx.send(view=view)

        # Handle playlist/tracks
        if isinstance(tracks, wavelink.Playlist):
            # Filter tracks < 30 seconds
            valid_tracks = []
            for track in tracks:
                if track.is_stream or track.length >= 30000:
                    track.requester = ctx.author
                    valid_tracks.append(track)
            
            if not valid_tracks:
                view = _play_view(self.bot, "Invalid Playlist", "All tracks in this playlist are shorter than 30 seconds!", error=True)
                return await ctx.send(view=view)
                
            for track in valid_tracks:
                await vc.queue.put_wait(track)
            
            added = len(valid_tracks)
            skipped = len(tracks) - added
            
            desc = f"{Config.EMOJI_TICK} Added playlist **{tracks.name}** ({added} tracks) to queue"
            if skipped > 0:
                desc += f"\n⚠️ Skipped {skipped} tracks (< 30s)"
            
            view = discord.ui.LayoutView(timeout=30)
            container = discord.ui.Container(accent_colour=discord.Colour(Config.EMBED_COLOR))
            container.add_item(discord.ui.TextDisplay(desc))
            view.add_item(container)
            await ctx.send(view=view)
            
            if not vc.playing:
                await vc.play(await vc.queue.get_wait())
                
        else:
            track = tracks[0]
            
            if not track.is_stream and track.length < 30000:
                 view = _play_view(self.bot, "Too Short", "Track must be longer than 30 seconds!", error=True)
                 return await ctx.send(view=view)

            track.requester = ctx.author
            
            await vc.queue.put_wait(track)
            
            # Components V2 Added to Queue
            view = discord.ui.LayoutView(timeout=30)
            container = discord.ui.Container(accent_colour=discord.Colour(Config.EMBED_COLOR))
            container.add_item(discord.ui.TextDisplay(f"{Config.EMOJI_ADDED} **Added to Queue**"))
            container.add_item(discord.ui.Separator())
            container.add_item(discord.ui.TextDisplay(f"**{track.title}** by {track.author}"))
            view.add_item(container)
            await ctx.send(view=view)
            
            if not vc.playing:
                try:
                    await vc.play(await vc.queue.get_wait())
                except wavelink.exceptions.LavalinkException as e:
                    # Handle 404 Session Not Found (Invalid Player)
                    if "404" in str(e):
                        print(f"DEBUG: Player 404 error. Attempting to reconnect session. Error: {e}")
                        try:
                            # Fully reconnect via safe_connect
                            channel = vc.channel
                            vc = await safe_connect(channel)
                            vc.text_channel = ctx.channel
                            # Re-add the track since queue was consumed
                            await vc.queue.put_wait(track)
                            await vc.play(await vc.queue.get_wait())
                        except Exception as reconnect_err:
                            print(f"DEBUG: Failed to recover player: {reconnect_err}")
                            view = _play_view(self.bot, "Connection Lost", "Lost connection to player. Please disconnect the bot and try again.", error=True)
                            await ctx.send(view=view)
                    else:
                        raise e

async def setup(bot):
    await bot.add_cog(Play(bot))
