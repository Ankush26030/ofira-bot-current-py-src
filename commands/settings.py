import discord
from discord.ext import commands
from utils.ratelimit import settings_cooldown
from player import CustomPlayer, safe_connect


def _settings_view(bot, title: str, body: str, *, error: bool = False) -> discord.ui.LayoutView:
    """Build a Components V2 view for settings messages."""
    view = discord.ui.LayoutView()
    colour = discord.Colour(bot.config.ERROR_COLOR if error else bot.config.SUCCESS_COLOR)
    container = discord.ui.Container(accent_colour=colour)
    container.add_item(discord.ui.TextDisplay(f"### {title}"))
    container.add_item(discord.ui.Separator())
    container.add_item(discord.ui.TextDisplay(body))
    view.add_item(container)
    return view


class Settings(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="setprefix", aliases=["prefix"])
    @settings_cooldown()
    @commands.has_permissions(manage_guild=True)
    async def set_prefix(self, ctx: commands.Context, new_prefix: str):
        """Change the bot prefix for this server"""
        if len(new_prefix) > 5:
            view = _settings_view(self.bot, "Invalid Prefix", "Prefix cannot be longer than 5 characters!", error=True)
            return await ctx.send(view=view)
            
        await self.bot.prefixes_col.update_one(
            {"guild_id": ctx.guild.id},
            {"$set": {"prefix": new_prefix}},
            upsert=True
        )
        
        view = _settings_view(self.bot, "Prefix Updated", f"Prefix set to **{new_prefix}**")
        await ctx.send(view=view)
        
    @commands.command(name="247", aliases=["24/7", "stay"])
    @settings_cooldown()
    @commands.has_permissions(manage_guild=True)
    async def twenty_four_seven(self, ctx: commands.Context):
        """Toggle 24/7 mode. If enabled, the bot will stay in the voice channel indefinitely."""
        # Get current status
        data = await self.bot.settings_col.find_one({"guild_id": ctx.guild.id})
        current_status = data.get("247", False) if data else False
        
        new_status = not current_status
        
        if new_status:
            # Enabling 24/7 - user must be in a voice channel
            if not ctx.author.voice or not ctx.author.voice.channel:
                view = _settings_view(self.bot, "Not in Voice", "You must be in a voice channel to enable 24/7 mode!", error=True)
                return await ctx.send(view=view)
            
            voice_channel = ctx.author.voice.channel
            
            # Store 24/7 status and voice channel ID
            await self.bot.settings_col.update_one(
                {"guild_id": ctx.guild.id},
                {"$set": {"247": True, "voice_channel_id": voice_channel.id}},
                upsert=True
            )
            
            # Instantly join the voice channel if not already connected
            player = ctx.guild.voice_client
            if not player:
                try:
                    player = await safe_connect(voice_channel)
                    player.text_channel = ctx.channel
                    view = _settings_view(self.bot, "24/7 Enabled", f"24/7 Mode has been **Enabled**\nJoined {voice_channel.mention}")
                    await ctx.send(view=view)
                except Exception as e:
                    view = _settings_view(self.bot, "Connection Failed", f"Failed to join voice channel: {str(e)}", error=True)
                    await ctx.send(view=view)
            else:
                view = _settings_view(self.bot, "24/7 Enabled", "24/7 Mode has been **Enabled**")
                await ctx.send(view=view)
        else:
            # Disabling 24/7
            await self.bot.settings_col.update_one(
                {"guild_id": ctx.guild.id},
                {"$set": {"247": False}, "$unset": {"voice_channel_id": ""}},
                upsert=True
            )
            
            # Instantly leave if not playing music
            player = ctx.guild.voice_client
            if player:
                # Check if music is playing or queue has items
                if not player.playing and player.queue.is_empty:
                    await player.disconnect()
                    view = _settings_view(self.bot, "24/7 Disabled", "24/7 Mode has been **Disabled**\nLeft voice channel")
                    await ctx.send(view=view)
                else:
                    view = _settings_view(self.bot, "24/7 Disabled", "24/7 Mode has been **Disabled**\n\n-# I'll leave after the current session ends")
                    await ctx.send(view=view)
            else:
                view = _settings_view(self.bot, "24/7 Disabled", "24/7 Mode has been **Disabled**")
                await ctx.send(view=view)

async def setup(bot):
    await bot.add_cog(Settings(bot))

