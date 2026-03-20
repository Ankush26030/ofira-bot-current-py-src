import discord
from discord.ext import commands
import wavelink
from player import CustomPlayer
from utils.checks import same_voice, is_playing
from utils.formatters import format_duration
from utils.ratelimit import music_cooldown


def _advanced_view(bot, title: str, body: str, *, error: bool = False) -> discord.ui.LayoutView:
    """Build a Components V2 view for advanced command messages."""
    view = discord.ui.LayoutView()
    colour = discord.Colour(bot.config.ERROR_COLOR if error else bot.config.SUCCESS_COLOR)
    container = discord.ui.Container(accent_colour=colour)
    container.add_item(discord.ui.TextDisplay(f"### {title}"))
    container.add_item(discord.ui.Separator())
    container.add_item(discord.ui.TextDisplay(body))
    view.add_item(container)
    return view


class Advanced(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="volume", aliases=["vol", "v"])
    @music_cooldown()
    @same_voice()
    async def volume(self, ctx: commands.Context, value: int = None):
        """Set or show the player volume"""
        player: CustomPlayer = ctx.guild.voice_client
        
        if value is None:
            volume_emoji = self.bot.config.EMOJI_VOLUME_LOW if player.volume < 50 else self.bot.config.EMOJI_VOLUME_HIGH
            view = _advanced_view(self.bot, "Volume", f"{volume_emoji} Current volume: **{player.volume}%**")
            return await ctx.send(view=view)
            
        if value < 1 or value > 200:
            view = _advanced_view(self.bot, "Invalid Volume", "Volume must be between 1 and 200!", error=True)
            return await ctx.send(view=view)
             
        await player.set_volume(value)
        volume_emoji = self.bot.config.EMOJI_VOLUME_LOW if value < 50 else self.bot.config.EMOJI_VOLUME_HIGH
        view = _advanced_view(self.bot, "Volume", f"{volume_emoji} Volume set to **{value}%**")
        await ctx.send(view=view)

    @commands.command(name="seek")
    @music_cooldown()
    @same_voice()
    @is_playing()
    async def seek(self, ctx: commands.Context, position: str):
        """Seek to a specific position (e.g., 1:30 or 90)"""
        player: CustomPlayer = ctx.guild.voice_client
        
        # Parse position
        try:
            if ":" in position:
                parts = position.split(":")
                seconds = 0
                for part in parts:
                    seconds = seconds * 60 + int(part)
                ms = seconds * 1000
            else:
                ms = int(position) * 1000
        except ValueError:
            view = _advanced_view(self.bot, "Invalid Format", "Invalid format! Use `mm:ss` or seconds.", error=True)
            return await ctx.send(view=view)
             
        if ms > player.current.length:
            view = _advanced_view(self.bot, "Invalid Position", "Cannot seek beyond track duration!", error=True)
            return await ctx.send(view=view)
             
        await player.seek(ms)
        view = _advanced_view(self.bot, "Seeked", f"Seeked to **{format_duration(ms)}**")
        await ctx.send(view=view)

    @commands.command(name="loop", aliases=["repeat"])
    @music_cooldown()
    @same_voice()
    async def loop(self, ctx: commands.Context):
        """Toggle loop mode (Off -> Track -> Queue)"""
        player: CustomPlayer = ctx.guild.voice_client
        
        mode = player.toggle_loop()
        
        msg = {
            "off": "Loop **disabled**",
            "track": "Looping **current track** 🔂",
            "queue": "Looping **queue** 🔁"
        }
        
        view = _advanced_view(self.bot, "Loop", msg[mode])
        await ctx.send(view=view)

    @commands.command(name="autoplay", aliases=["auto"])
    @music_cooldown()
    @same_voice()
    async def autoplay(self, ctx: commands.Context):
        """Toggle autoplay"""
        player: CustomPlayer = ctx.guild.voice_client
        
        enabled = player.toggle_autoplay()
        
        if enabled:
            view = _advanced_view(self.bot, "Autoplay", "Autoplay **enabled** 🎲")
        else:
            view = _advanced_view(self.bot, "Autoplay", "Autoplay **disabled**")
        await ctx.send(view=view)

    @commands.command(name="grab", aliases=["save", "yoink"])
    @music_cooldown()
    @is_playing()
    async def grab(self, ctx: commands.Context):
        """Save the current song to your DMs"""
        player: CustomPlayer = ctx.guild.voice_client
        track = player.current
        
        from utils.embeds import create_track_embed
        embed = create_track_embed(track, title="Song Saved 📩")
        embed.set_footer(text=f"Saved from {ctx.guild.name}")
        
        try:
            await ctx.author.send(embed=embed)
            view = _advanced_view(self.bot, "Song Saved", "Sent the song to your DMs! 📩")
            await ctx.send(view=view)
        except discord.Forbidden:
            view = _advanced_view(self.bot, "DMs Closed", "I can't DM you! Please enable DMs.", error=True)
            await ctx.send(view=view)

async def setup(bot):
    await bot.add_cog(Advanced(bot))

