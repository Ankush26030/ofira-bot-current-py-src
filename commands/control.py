import discord
from discord.ext import commands
import wavelink
from utils.checks import in_voice, same_voice, is_playing
from utils.ratelimit import music_cooldown


def _control_view(bot, title: str, body: str, *, error: bool = False) -> discord.ui.LayoutView:
    """Build a Components V2 view for control messages."""
    view = discord.ui.LayoutView()
    colour = discord.Colour(bot.config.ERROR_COLOR if error else bot.config.SUCCESS_COLOR)
    container = discord.ui.Container(accent_colour=colour)
    container.add_item(discord.ui.TextDisplay(f"### {title}"))
    container.add_item(discord.ui.Separator())
    container.add_item(discord.ui.TextDisplay(body))
    view.add_item(container)
    return view


class Control(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="pause")
    @music_cooldown()
    @same_voice()
    @is_playing()
    async def pause(self, ctx: commands.Context):
        """Pause playback"""
        player: wavelink.Player = ctx.guild.voice_client
        
        if player.paused:
            view = _control_view(self.bot, "Already Paused", "Player is already paused!", error=True)
            return await ctx.send(view=view)
            
        await player.pause(True)
        view = _control_view(self.bot, "Paused", "Paused playback")
        await ctx.send(view=view)

    @commands.command(name="resume", aliases=["unpause"])
    @music_cooldown()
    @same_voice()
    async def resume(self, ctx: commands.Context):
        """Resume playback"""
        player: wavelink.Player = ctx.guild.voice_client
        
        if not player:
            view = _control_view(self.bot, "Not Playing", "I am not playing anything.", error=True)
            return await ctx.send(view=view)

        if not player.paused:
            view = _control_view(self.bot, "Not Paused", "Player is not paused!", error=True)
            return await ctx.send(view=view)
            
        await player.pause(False)
        view = _control_view(self.bot, "Resumed", "Resumed playback")
        await ctx.send(view=view)

    @commands.command(name="skip", aliases=["s", "next"])
    @music_cooldown()
    @same_voice()
    @is_playing()
    async def skip(self, ctx: commands.Context):
        """Skip the current track"""
        player: wavelink.Player = ctx.guild.voice_client
        
        skipped = player.current
        await player.skip(force=True)
        
        view = _control_view(self.bot, "Skipped", f"Skipped **{skipped.title}**")
        await ctx.send(view=view)

    @commands.command(name="stop", aliases=["dc", "disconnect"])
    @music_cooldown()
    @same_voice()
    async def stop(self, ctx: commands.Context):
        """Stop playback and disconnect (or just stop if 24/7 is enabled)"""
        player: wavelink.Player = ctx.guild.voice_client
        
        if not player:
            view = _control_view(self.bot, "Not Connected", "I am not connected.", error=True)
            return await ctx.send(view=view)

        # Check if 24/7 mode is enabled
        settings = await self.bot.settings_col.find_one({"guild_id": ctx.guild.id})
        is_247_enabled = settings and settings.get("247", False)

        if hasattr(player, 'np_message') and player.np_message:
            try:
                await player.np_message.delete()
            except:
                pass
        
        # Clear the queue
        if hasattr(player, 'queue'):
            player.queue.clear()
        
        # Stop current track
        await player.stop()
        
        # Clear voice channel status
        if player.channel:
            try:
                await player.channel.edit(status=None)
            except:
                pass
        
        if is_247_enabled:
            # Stay in VC but stop playback
            view = _control_view(self.bot, "Stopped", "Stopped playback and cleared queue\n\n-# 24/7 mode is enabled — staying in voice channel")
            await ctx.send(view=view)
        else:
            # Disconnect from VC
            await player.disconnect()
            view = _control_view(self.bot, "Disconnected", "Disconnected and cleared queue")
            await ctx.send(view=view)

    @commands.command(name="skipto")
    @music_cooldown()
    @same_voice()
    async def skipto(self, ctx: commands.Context, index: int):
        """Skip to a specific track in the queue"""
        player: wavelink.Player = ctx.guild.voice_client
        
        if not player or player.queue.is_empty:
            view = _control_view(self.bot, "Empty Queue", "Queue is empty!", error=True)
            return await ctx.send(view=view)
              
        if index < 1 or index > player.queue.count:
            view = _control_view(self.bot, "Invalid Index", "Invalid queue index!", error=True)
            return await ctx.send(view=view)
            
        # 1-based index to 0-based
        index -= 1
        
        # Remove items before the target index
        for _ in range(index):
            try:
                player.queue.get()
            except:
                pass
                
        await player.skip(force=True)
        view = _control_view(self.bot, "Skipped To", f"Skipped to track **#{index + 1}**")
        await ctx.send(view=view)

async def setup(bot):
    await bot.add_cog(Control(bot))

