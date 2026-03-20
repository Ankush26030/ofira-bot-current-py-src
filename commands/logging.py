import discord
from discord.ext import commands
from discord import Webhook
import aiohttp
import datetime

class Logging(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def send_webhook(self, url, embed):
        if not url:
            return
        
        try:
            async with aiohttp.ClientSession() as session:
                webhook = Webhook.from_url(url, session=session)
                await webhook.send(
                    embed=embed, 
                    username=f"{self.bot.user.name} Logs", 
                    avatar_url=self.bot.user.display_avatar.url
                )
        except Exception as e:
            print(f"Failed to send webhook log: {e}")

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        if not self.bot.config.JOIN_LOG_WEBHOOK:
            return

        embed = discord.Embed(
            title="📥 Joined a New Server!",
            description=f"**Server:** {guild.name}\n**ID:** {guild.id}\n**Members:** {guild.member_count}\n**Owner:** {guild.owner} ({guild.owner_id})",
            color=self.bot.config.SUCCESS_COLOR,
            timestamp=datetime.datetime.now()
        )
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        embed.set_footer(text=f"Server Count: {len(self.bot.guilds)}")
        
        await self.send_webhook(self.bot.config.JOIN_LOG_WEBHOOK, embed)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        if not self.bot.config.LEAVE_LOG_WEBHOOK:
            return

        embed = discord.Embed(
            title="📤 Left a Server",
            description=f"**Server:** {guild.name}\n**ID:** {guild.id}\n**Members:** {guild.member_count}\n**Owner:** {guild.owner} ({guild.owner_id})",
            color=self.bot.config.ERROR_COLOR,
            timestamp=datetime.datetime.now()
        )
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        embed.set_footer(text=f"Server Count: {len(self.bot.guilds)}")
        
        await self.send_webhook(self.bot.config.LEAVE_LOG_WEBHOOK, embed)

    @commands.Cog.listener()
    async def on_command_completion(self, ctx):
        if not self.bot.config.COMMAND_LOG_WEBHOOK:
            return
            
        # Ignore commands from owner/devs if desired? No, log everything for now.
        
        embed = discord.Embed(
            title="💻 Command Used",
            color=self.bot.config.EMBED_COLOR,
            timestamp=datetime.datetime.now()
        )
        embed.set_author(name=f"{ctx.author} ({ctx.author.id})", icon_url=ctx.author.display_avatar.url)
        
        # Command Info
        embed.add_field(name="Command", value=f"`{ctx.command.qualified_name}`", inline=True)
        embed.add_field(name="Channel", value=f"{ctx.channel.name} (`{ctx.channel.id}`)", inline=True)
        embed.add_field(name="Guild", value=f"{ctx.guild.name} (`{ctx.guild.id}`)", inline=False)
        
        # Message Content (Sanitized)
        content = ctx.message.content
        if len(content) > 1000:
            content = content[:1000] + "..."
        embed.add_field(name="Content", value=f"```{content}```", inline=False)
        
        await self.send_webhook(self.bot.config.COMMAND_LOG_WEBHOOK, embed)

async def setup(bot):
    await bot.add_cog(Logging(bot))
