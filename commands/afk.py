import discord
from discord.ext import commands
import time
from utils.embeds import create_success_embed, create_error_embed
from utils.ratelimit import utility_cooldown


def _afk_view(bot, title: str, body: str) -> discord.ui.LayoutView:
    """Build a quick Components V2 view for AFK messages."""
    view = discord.ui.LayoutView()
    container = discord.ui.Container(accent_colour=discord.Colour(bot.config.EMBED_COLOR))
    container.add_item(discord.ui.TextDisplay(f"### {title}"))
    container.add_item(discord.ui.Separator())
    container.add_item(discord.ui.TextDisplay(body))
    view.add_item(container)
    return view


class AFK(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.afk_col = bot.db["afk"]

    @commands.command(name="afk")
    @utility_cooldown()
    async def afk(self, ctx: commands.Context, *, reason: str = "AFK"):
        """Set your AFK status"""
        # Sanitize reason to prevent @everyone/@here/role pings
        reason = discord.utils.escape_mentions(reason)
        await self.afk_col.update_one(
            {"user_id": ctx.author.id},
            {"$set": {
                "reason": reason,
                "timestamp": time.time(),
                "guild_id": ctx.guild.id
            }},
            upsert=True
        )
        
        # Try to change nickname
        try:
            new_nick = f"[AFK] {ctx.author.display_name}"
            # Discord limit 32 chars
            if len(new_nick) <= 32:
                await ctx.author.edit(nick=new_nick)
        except:
            pass

        view = _afk_view(self.bot, "AFK Set", f"I've set your AFK: **{reason}**")
        await ctx.send(view=view, allowed_mentions=discord.AllowedMentions.none())

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        # Check if author is AFK (Remove AFK)
        afk_data = await self.afk_col.find_one({"user_id": message.author.id})
        if afk_data:
            # If now - timestamp < 5 seconds, ignore (user just set it)
            if time.time() - afk_data["timestamp"] > 5:
                await self.afk_col.delete_one({"user_id": message.author.id})
                
                # Restore nickname
                try:
                    name = message.author.display_name
                    if name.startswith("[AFK] "):
                        await message.author.edit(nick=name[6:])
                except:
                    pass

                view = _afk_view(self.bot, "Welcome Back", f"{message.author.mention}, I removed your AFK")
                await message.channel.send(view=view, delete_after=5)

        # Check members mentioned
        if message.mentions:
            for user in message.mentions:
                if user.bot: continue
                
                afk_user = await self.afk_col.find_one({"user_id": user.id})
                if afk_user:
                    reason = afk_user["reason"]
                    ts = afk_user["timestamp"]
                    relative = f"<t:{int(ts)}:R>"
                    
                    view = _afk_view(
                        self.bot,
                        f"{user.display_name} is AFK",
                        f"> {reason}\n"
                        f"-# Gone since {relative}"
                    )
                    await message.channel.send(view=view, delete_after=10, allowed_mentions=discord.AllowedMentions.none())

async def setup(bot):
    await bot.add_cog(AFK(bot))
