import discord
from discord.ext import commands
import wavelink
import asyncio
from player import CustomPlayer, safe_connect
from utils.checks import in_voice, same_voice
from utils.ratelimit import music_cooldown


def _voice_view(bot, title: str, body: str, *, error: bool = False) -> discord.ui.LayoutView:
    """Build a Components V2 view for voice messages."""
    view = discord.ui.LayoutView()
    colour = discord.Colour(bot.config.ERROR_COLOR if error else bot.config.SUCCESS_COLOR)
    container = discord.ui.Container(accent_colour=colour)
    container.add_item(discord.ui.TextDisplay(f"### {title}"))
    container.add_item(discord.ui.Separator())
    container.add_item(discord.ui.TextDisplay(body))
    view.add_item(container)
    return view


class Voice(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="join", aliases=["connect", "j"])
    @music_cooldown()
    @in_voice()
    async def join(self, ctx: commands.Context):
        """Join your voice channel"""
        try:
            player = await safe_connect(ctx.author.voice.channel)
            player.text_channel = ctx.channel
            view = _voice_view(self.bot, "Connected", f"Joined **{player.channel}**")
            await ctx.send(view=view)
        except discord.ClientException:
            view = _voice_view(self.bot, "Already Connected", "I am already connected to a voice channel!", error=True)
            await ctx.send(view=view)
        except Exception as e:
            view = _voice_view(self.bot, "Connection Failed", f"Failed to join: {e}", error=True)
            await ctx.send(view=view)

    @commands.command(name="leave", aliases=["l"])
    @music_cooldown()
    @same_voice()
    async def leave(self, ctx: commands.Context):
        """Leave the voice channel"""
        player: wavelink.Player = ctx.guild.voice_client
        
        if not player:
            view = _voice_view(self.bot, "Not Connected", "I am not connected.", error=True)
            return await ctx.send(view=view)
            
        # Check if 24/7 is enabled
        data = await self.bot.settings_col.find_one({"guild_id": ctx.guild.id})
        if data and data.get("247", False):
            view = _voice_view(
                self.bot,
                "24/7 Mode Active",
                "I cannot leave the voice channel while 24/7 mode is active.\n\n-# Disable it first using `,247 off`.",
                error=True
            )
            return await ctx.send(view=view)
            
        if hasattr(player, 'np_message') and player.np_message:
            try:
                await player.np_message.delete()
            except:
                pass
                
        await player.disconnect()
        view = _voice_view(self.bot, "Disconnected", "Disconnected from voice channel")
        await ctx.send(view=view)

async def setup(bot):
    await bot.add_cog(Voice(bot))

