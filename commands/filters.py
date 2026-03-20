import discord
from discord.ext import commands
import wavelink
from utils.checks import same_voice, is_playing
from utils.ratelimit import filter_cooldown


def _filter_view(bot, title: str, body: str, *, error: bool = False) -> discord.ui.LayoutView:
    """Build a Components V2 view for filter messages."""
    view = discord.ui.LayoutView()
    colour = discord.Colour(bot.config.ERROR_COLOR if error else bot.config.SUCCESS_COLOR)
    container = discord.ui.Container(accent_colour=colour)
    container.add_item(discord.ui.TextDisplay(f"### {title}"))
    container.add_item(discord.ui.Separator())
    container.add_item(discord.ui.TextDisplay(body))
    view.add_item(container)
    return view


class Filters(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def set_filter(self, player: wavelink.Player, filter_config: wavelink.Filters):
        """Helper to set filters"""
        await player.set_filters(filter_config)

    @commands.command(name="bassboost", aliases=["bb"])
    @filter_cooldown()
    @same_voice()
    @is_playing()
    async def bassboost(self, ctx: commands.Context, level: str = "low"):
        """Apply bassboost (low, medium, high, extreme)"""
        player: wavelink.Player = ctx.guild.voice_client
        
        levels = {
            "low": 0.15,
            "medium": 0.35,
            "high": 0.55,
            "extreme": 0.85,
            "off": 0.0
        }
        
        if level.lower() not in levels:
            view = _filter_view(self.bot, "Invalid Level", "Invalid level! Use: low, medium, high, extreme, off", error=True)
            return await ctx.send(view=view)
        
        gain = levels[level.lower()]
        
        filters = player.filters
        filters.equalizer.reset()
        
        if gain > 0:
            # Simple bass boost: boost lower frequencies
            bands = [
                {"band": 0, "gain": gain},
                {"band": 1, "gain": gain * 0.80},
                {"band": 2, "gain": gain * 0.60},
                {"band": 3, "gain": gain * 0.40},
                {"band": 4, "gain": gain * 0.20},
            ]
            filters.equalizer.set(bands=bands)
            
        await player.set_filters(filters)
        view = _filter_view(self.bot, "Bass Boost", f"Bassboost set to **{level}**")
        await ctx.send(view=view)

    @commands.command(name="nightcore", aliases=["nc"])
    @filter_cooldown()
    @same_voice()
    @is_playing()
    async def nightcore(self, ctx: commands.Context):
        """Toggle nightcore effect"""
        player: wavelink.Player = ctx.guild.voice_client
        
        filters = player.filters
        
        # Check if nightcore is active (timescale pitch approx 1.2)
        if filters.timescale.pitch >= 1.2:
            filters.timescale.reset()
            view = _filter_view(self.bot, "Nightcore", "Nightcore **disabled**")
        else:
            filters.timescale.set(speed=1.2, pitch=1.2, rate=1.0)
            view = _filter_view(self.bot, "Nightcore", "Nightcore **enabled**")
            
        await player.set_filters(filters)
        await ctx.send(view=view)

    @commands.command(name="reset", aliases=["clearfilters"])
    @filter_cooldown()
    @same_voice()
    async def reset_filters(self, ctx: commands.Context):
        """Reset all audio filters"""
        player: wavelink.Player = ctx.guild.voice_client
        
        filters = player.filters
        filters.reset()
        await player.set_filters(filters)
        
        view = _filter_view(self.bot, "Filters Reset", "Reset all audio filters")
        await ctx.send(view=view)

    @commands.command(name="8d", aliases=["3d", "rotation"])
    @filter_cooldown()
    @same_voice()
    @is_playing()
    async def _8d(self, ctx: commands.Context):
        """Toggle 8D Audio effect"""
        player: wavelink.Player = ctx.guild.voice_client
        filters = player.filters
        
        if filters.rotation.rotation_hz > 0:
            filters.rotation.reset()
            view = _filter_view(self.bot, "8D Audio", "8D Audio **disabled**")
        else:
            filters.rotation.set(rotation_hz=0.2)
            view = _filter_view(self.bot, "8D Audio", "8D Audio **enabled**")
            
        await player.set_filters(filters)
        await ctx.send(view=view)

    @commands.command(name="vaporwave", aliases=["slowed"])
    @filter_cooldown()
    @same_voice()
    @is_playing()
    async def vaporwave(self, ctx: commands.Context):
        """Toggle Vaporwave (Slowed + Reverb feel)"""
        player: wavelink.Player = ctx.guild.voice_client
        filters = player.filters
        
        if filters.timescale.pitch < 1.0:
            filters.timescale.reset()
            view = _filter_view(self.bot, "Vaporwave", "Vaporwave **disabled**")
        else:
            filters.timescale.set(pitch=0.8, speed=0.8)
            view = _filter_view(self.bot, "Vaporwave", "Vaporwave **enabled**")
            
        await player.set_filters(filters)
        await ctx.send(view=view)

    @commands.command(name="tremolo")
    @filter_cooldown()
    @same_voice()
    @is_playing()
    async def tremolo(self, ctx: commands.Context):
        """Toggle Tremolo effect"""
        player: wavelink.Player = ctx.guild.voice_client
        filters = player.filters
        
        if filters.tremolo.depth > 0:
            filters.tremolo.reset()
            view = _filter_view(self.bot, "Tremolo", "Tremolo **disabled**")
        else:
            filters.tremolo.set(frequency=10.0, depth=0.5)
            view = _filter_view(self.bot, "Tremolo", "Tremolo **enabled**")
            
        await player.set_filters(filters)
        await ctx.send(view=view)

    @commands.command(name="karaoke")
    @filter_cooldown()
    @same_voice()
    @is_playing()
    async def karaoke(self, ctx: commands.Context):
        """Toggle Karaoke effect"""
        player: wavelink.Player = ctx.guild.voice_client
        filters = player.filters
        
        if filters.karaoke.level > 0:
            filters.karaoke.reset()
            view = _filter_view(self.bot, "Karaoke", "Karaoke **disabled**")
        else:
            filters.karaoke.set(level=1.0, mono_level=1.0, filter_band=220.0, filter_width=100.0)
            view = _filter_view(self.bot, "Karaoke", "Karaoke **enabled**")
            
        await player.set_filters(filters)
        await ctx.send(view=view)

async def setup(bot):
    await bot.add_cog(Filters(bot))

