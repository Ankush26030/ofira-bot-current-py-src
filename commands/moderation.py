import discord
from discord.ext import commands
import asyncio
from datetime import timedelta
from utils.ratelimit import moderation_cooldown


def _mod_view(bot, title: str, body: str, *, error: bool = False) -> discord.ui.LayoutView:
    """Build a Components V2 view for moderation messages."""
    view = discord.ui.LayoutView()
    colour = discord.Colour(bot.config.ERROR_COLOR if error else bot.config.SUCCESS_COLOR)
    container = discord.ui.Container(accent_colour=colour)
    container.add_item(discord.ui.TextDisplay(f"### {title}"))
    container.add_item(discord.ui.Separator())
    container.add_item(discord.ui.TextDisplay(body))
    view.add_item(container)
    return view


class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def check_permissions(self, ctx, member: discord.Member):
        if ctx.author.top_role <= member.top_role and ctx.author.id != ctx.guild.owner_id:
            view = _mod_view(self.bot, "Permission Denied", "You cannot moderate someone with a higher or equal role!", error=True)
            await ctx.send(view=view)
            return False
        if ctx.guild.me.top_role <= member.top_role:
            view = _mod_view(self.bot, "Permission Denied", "I cannot moderate someone with a higher or equal role!", error=True)
            await ctx.send(view=view)
            return False
        return True



    @commands.command(name="mute", aliases=["timeout"])
    @moderation_cooldown()
    @commands.has_permissions(moderate_members=True)
    async def mute(self, ctx: commands.Context, member: discord.Member, duration_str: str, *, reason: str = "No reason provided"):
        """Timeout a member (e.g. 1m, 1h, 1d)"""
        if not await self.check_permissions(ctx, member): return
        
        # Check if already muted
        if member.is_timed_out():
            view = _mod_view(self.bot, "Already Muted", f"**{member}** is already muted!", error=True)
            return await ctx.send(view=view)
        
        # Parse duration
        seconds = 0
        if duration_str.endswith("s"): seconds = int(duration_str[:-1])
        elif duration_str.endswith("m"): seconds = int(duration_str[:-1]) * 60
        elif duration_str.endswith("h"): seconds = int(duration_str[:-1]) * 3600
        elif duration_str.endswith("d"): seconds = int(duration_str[:-1]) * 86400
        else:
            try:
                seconds = int(duration_str) # Assume seconds
            except:
                view = _mod_view(self.bot, "Invalid Duration", "Invalid duration! Use 60s, 5m, 1h etc.", error=True)
                return await ctx.send(view=view)
        
        duration = timedelta(seconds=seconds)
        await member.timeout(duration, reason=reason)
        view = _mod_view(self.bot, "Muted", f"Muted **{member}** for {duration_str} | Reason: {reason}")
        await ctx.send(view=view)

    @commands.command(name="unmute", aliases=["untimeout"])
    @moderation_cooldown()
    @commands.has_permissions(moderate_members=True)
    async def unmute(self, ctx: commands.Context, member: discord.Member):
        """Remove timeout from a member"""
        if not await self.check_permissions(ctx, member): return
        
        # Check if already unmuted
        if not member.is_timed_out():
            view = _mod_view(self.bot, "Not Muted", f"**{member}** is not muted!", error=True)
            return await ctx.send(view=view)
        
        await member.timeout(None, reason="Unmute command")
        view = _mod_view(self.bot, "Unmuted", f"Unmuted **{member}**")
        await ctx.send(view=view)

    @commands.group(name="purge", aliases=["clean", "clear"], invoke_without_command=True)
    @moderation_cooldown()
    @commands.has_permissions(manage_messages=True)
    async def purge(self, ctx: commands.Context, amount: int):
        """Purge messages (default: all)"""
        if amount < 1 or amount > 999:
            view = _mod_view(self.bot, "Invalid Amount", "Amount must be between 1 and 999!", error=True)
            return await ctx.send(view=view)
        try:
            deleted = await ctx.channel.purge(limit=amount + 1) # +1 to include command
            view = _mod_view(self.bot, "Purged", f"Purged {len(deleted)-1} messages")
            await ctx.send(view=view, delete_after=3)
        except discord.Forbidden:
            view = _mod_view(self.bot, "No Permission", "I don't have permission to Manage Messages!", error=True)
            await ctx.send(view=view)
        except discord.HTTPException as e:
            view = _mod_view(self.bot, "Purge Failed", f"Failed to purge messages: {e}", error=True)
            await ctx.send(view=view)

    @purge.command(name="humans")
    async def purge_humans(self, ctx: commands.Context, amount: int):
        """Purge messages from humans only"""
        try:
            # Delete the command message first
            await ctx.message.delete()
            
            def check(m): return not m.author.bot
            deleted = await ctx.channel.purge(limit=amount, check=check)
            view = _mod_view(self.bot, "Purged", f"Purged {len(deleted)} human messages")
            await ctx.send(view=view, delete_after=3)
        except discord.Forbidden:
            view = _mod_view(self.bot, "No Permission", "I don't have permission to Manage Messages!", error=True)
            await ctx.send(view=view)
        except discord.HTTPException as e:
            view = _mod_view(self.bot, "Purge Failed", f"Failed to purge messages: {e}", error=True)
            await ctx.send(view=view)

    @purge.command(name="bots")
    async def purge_bots(self, ctx: commands.Context, amount: int):
        """Purge messages from bots only"""
        try:
            # Delete the command message first
            await ctx.message.delete()
            
            def check(m): return m.author.bot
            deleted = await ctx.channel.purge(limit=amount, check=check)
            view = _mod_view(self.bot, "Purged", f"Purged {len(deleted)} bot messages")
            await ctx.send(view=view, delete_after=3)
        except discord.Forbidden:
            view = _mod_view(self.bot, "No Permission", "I don't have permission to Manage Messages!", error=True)
            await ctx.send(view=view)
        except discord.HTTPException as e:
            view = _mod_view(self.bot, "Purge Failed", f"Failed to purge messages: {e}", error=True)
            await ctx.send(view=view)


async def setup(bot):
    await bot.add_cog(Moderation(bot))

