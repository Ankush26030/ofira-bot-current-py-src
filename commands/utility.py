import discord
import time
from discord.ext import commands
from utils.embeds import create_success_embed, create_error_embed
from utils.ratelimit import utility_cooldown


class DeveloperView(discord.ui.LayoutView):
    def __init__(self, bot):
        super().__init__(timeout=180)
        self.bot = bot
        self.current_tab = "home"
        self._build()

    def _build(self):
        self.clear_items()
        container = discord.ui.Container(accent_colour=discord.Colour(self.bot.config.EMBED_COLOR))

        if self.current_tab == "home":
            container.add_item(discord.ui.TextDisplay("### Developer Information"))
            container.add_item(discord.ui.Separator())
            container.add_item(discord.ui.TextDisplay(
                "**Meet the creator.**\n\n"
                "This bot was crafted with precision and care by **devthesuperior**.\n"
                "Click the buttons below to learn more about his work and expertise."
            ))

        elif self.current_tab == "about":
            container.add_item(discord.ui.TextDisplay("### 👑 About the Developer"))
            container.add_item(discord.ui.Separator())
            container.add_item(discord.ui.TextDisplay(
                "**devthesuperior** is a highly skilled software engineer and the visionary creator behind this bot.\n\n"
                "With a passion for **innovation** and **excellence**, he builds cutting-edge solutions "
                "that push the boundaries of what's possible on Discord.\n\n"
                "He strives for perfection in every line of code, delivering premium experiences "
                "through robust architecture and stunning design."
            ))
            container.add_item(discord.ui.Separator())
            container.add_item(discord.ui.TextDisplay(
                "-# DevTheSuperior — Professional Developer"
            ))

        elif self.current_tab == "skills":
            container.add_item(discord.ui.TextDisplay("### 💻 Technical Expertise"))
            container.add_item(discord.ui.Separator())
            container.add_item(discord.ui.TextDisplay(
                "**devthesuperior** possesses a wide arsenal of technical skills:\n\n"
                "🐍 **Python Expert** — Advanced Logic & Architecture\n"
                "🌐 **Full-Stack Web Development** — Modern Frameworks\n"
                "🎮 **Game Development** — Immersive Mechanics\n"
                "🤖 **Bot Development** — Scalable Discord Systems\n"
                "🔒 **Cybersecurity Expert**\n"
                "⚡ **System Optimization**"
            ))
            container.add_item(discord.ui.Separator())
            container.add_item(discord.ui.TextDisplay(
                "-# Mastery across multiple domains"
            ))

        container.add_item(discord.ui.Separator())

        # ── Buttons ──
        btn_row = discord.ui.ActionRow()

        about_style = discord.ButtonStyle.blurple if self.current_tab == "about" else discord.ButtonStyle.gray
        btn_about = discord.ui.Button(label="About Owner", style=about_style, emoji="👑", custom_id="dev_about")
        btn_about.callback = self._on_about
        btn_row.add_item(btn_about)

        skills_style = discord.ButtonStyle.blurple if self.current_tab == "skills" else discord.ButtonStyle.gray
        btn_skills = discord.ui.Button(label="Skills", style=skills_style, emoji="💻", custom_id="dev_skills")
        btn_skills.callback = self._on_skills
        btn_row.add_item(btn_skills)

        container.add_item(btn_row)
        self.add_item(container)

    async def _on_about(self, interaction: discord.Interaction):
        self.current_tab = "about"
        self._build()
        await interaction.response.edit_message(view=self)

    async def _on_skills(self, interaction: discord.Interaction):
        self.current_tab = "skills"
        self._build()
        await interaction.response.edit_message(view=self)


class SakshamView(discord.ui.LayoutView):
    def __init__(self, bot):
        super().__init__(timeout=180)
        self.bot = bot
        self.current_tab = "home"
        self._build()

    def _build(self):
        self.clear_items()
        container = discord.ui.Container(accent_colour=discord.Colour(self.bot.config.EMBED_COLOR))

        if self.current_tab == "home":
            container.add_item(discord.ui.TextDisplay("### Co-Owner Information"))
            container.add_item(discord.ui.Separator())
            container.add_item(discord.ui.TextDisplay(
                "**Meet the co-owner.**\n\n"
                "This bot is co-managed and supported by **saksham**.\n"
                "Click the buttons below to learn more about his work and expertise."
            ))

        elif self.current_tab == "about":
            container.add_item(discord.ui.TextDisplay("### 🤝 About the Co-Owner"))
            container.add_item(discord.ui.Separator())
            container.add_item(discord.ui.TextDisplay(
                "**saksham** is a talented developer and the dedicated co-owner of this bot.\n\n"
                "With a keen eye for **detail** and a drive for **quality**, he plays a vital role "
                "in shaping the bot's features and ensuring a seamless experience for users.\n\n"
                "His contributions are instrumental in keeping the bot running at its best "
                "and pushing it to new heights."
            ))
            container.add_item(discord.ui.Separator())
            container.add_item(discord.ui.TextDisplay(
                "-# Saksham — Co-Owner & Developer"
            ))

        elif self.current_tab == "skills":
            container.add_item(discord.ui.TextDisplay("### 💻 Technical Expertise"))
            container.add_item(discord.ui.Separator())
            container.add_item(discord.ui.TextDisplay(
                "**saksham** possesses a wide arsenal of technical skills:\n\n"
                "📜 **JavaScript Expert** — Advanced Logic & Architecture\n"
                "🌐 **Full-Stack Web Development** — Modern Frameworks\n"
                "🎮 **Game Development** — Immersive Mechanics\n"
                "🤖 **Bot Development** — Scalable Discord Systems\n"
                "📱 **App Development**\n"
                "⚡ **System Optimization**"
            ))
            container.add_item(discord.ui.Separator())
            container.add_item(discord.ui.TextDisplay(
                "-# Mastery across multiple domains"
            ))

        container.add_item(discord.ui.Separator())

        # ── Buttons ──
        btn_row = discord.ui.ActionRow()

        about_style = discord.ButtonStyle.blurple if self.current_tab == "about" else discord.ButtonStyle.gray
        btn_about = discord.ui.Button(label="About Co-Owner", style=about_style, emoji="🤝", custom_id="saksham_about")
        btn_about.callback = self._on_about
        btn_row.add_item(btn_about)

        skills_style = discord.ButtonStyle.blurple if self.current_tab == "skills" else discord.ButtonStyle.gray
        btn_skills = discord.ui.Button(label="Skills", style=skills_style, emoji="💻", custom_id="saksham_skills")
        btn_skills.callback = self._on_skills
        btn_row.add_item(btn_skills)

        container.add_item(btn_row)
        self.add_item(container)

    async def _on_about(self, interaction: discord.Interaction):
        self.current_tab = "about"
        self._build()
        await interaction.response.edit_message(view=self)

    async def _on_skills(self, interaction: discord.Interaction):
        self.current_tab = "skills"
        self._build()
        await interaction.response.edit_message(view=self)


class StatsView(discord.ui.LayoutView):
    """Components V2 Statistics view with Bot Info / System Info tabs."""

    def __init__(
        self, *, bot, author_id: int,
        total_guilds: int, total_users: int, total_channels: int,
        total_commands: int, voice_clients: int, lavalink_status: str,
        total_shards: int, cluster_id: int, cluster_count: int,
        cluster_shard_ids: list, guild_shard_id: int,
        cpu_usage: float, memory_usage: float,
        uptime: str, ping: float,
    ):
        super().__init__(timeout=120)
        self.bot = bot
        self.author_id = author_id
        self.data = {
            "guilds": total_guilds, "users": total_users,
            "channels": total_channels, "commands": total_commands,
            "voice": voice_clients, "lavalink": lavalink_status,
            "total_shards": total_shards, "cluster_id": cluster_id,
            "cluster_count": cluster_count, "cluster_shard_ids": cluster_shard_ids,
            "guild_shard_id": guild_shard_id, "cpu": cpu_usage,
            "memory": memory_usage, "uptime": uptime, "ping": ping,
        }
        self.current_tab = "bot"
        self._build()

    def _build(self):
        self.clear_items()
        from config import Config

        container = discord.ui.Container(accent_colour=discord.Colour(Config.EMBED_COLOR))

        # Title
        container.add_item(discord.ui.TextDisplay(
            f"**{self.bot.user.name} Statistics**"
        ))
        container.add_item(discord.ui.Separator())

        # Content based on current tab
        if self.current_tab == "bot":
            content = (
                f"**Servers** — {self.data['guilds']:,}\n"
                f"**Total Members** — {self.data['users']:,}\n"
                f"**Channels** — {self.data['channels']:,}\n"
                f"**Commands** — {self.data['commands']}\n"
                f"**Active Players** — {self.data['voice']}\n"
                f"**Lavalink** — {self.data['lavalink']}"
            )
            container.add_item(discord.ui.TextDisplay(content))
            container.add_item(discord.ui.Separator())

            # Shard details section
            shard_ids_str = ", ".join(str(s) for s in self.data['cluster_shard_ids'])
            shard_content = (
                f"**Sharding**\n"
                f"Total Shards — {self.data['total_shards']}\n"
                f"Cluster — {self.data['cluster_id'] + 1}/{self.data['cluster_count']}\n"
                f"Cluster Shards — [{shard_ids_str}]\n"
                f"This Server — Shard {self.data['guild_shard_id']}"
            )
            container.add_item(discord.ui.TextDisplay(shard_content))
        else:
            content = (
                f"**CPU Usage** — {self.data['cpu']}%\n"
                f"**Memory** — {self.data['memory']:.2f} MB\n"
                f"**Uptime** — {self.data['uptime']}\n"
                f"**Ping** — {self.data['ping']:.0f}ms\n"
                f"**Lavalink** — {self.data['lavalink']}\n"
                f"**Total Shards** — {self.data['total_shards']}\n"
                f"**Cluster** — {self.data['cluster_id'] + 1}/{self.data['cluster_count']}"
            )
            container.add_item(discord.ui.TextDisplay(content))
        container.add_item(discord.ui.Separator())

        # ── Link buttons: Invite + Support ───────────────────────
        link_row = discord.ui.ActionRow()
        invite_url = f"https://discord.com/api/oauth2/authorize?client_id={self.bot.user.id}&permissions=8&scope=bot%20applications.commands"
        link_row.add_item(discord.ui.Button(
            label="Invite Me", style=discord.ButtonStyle.link, url=invite_url
        ))
        link_row.add_item(discord.ui.Button(
            label="Support Server", style=discord.ButtonStyle.link, url=Config.SUPPORT_SERVER
        ))
        container.add_item(link_row)

        container.add_item(discord.ui.Separator())

        # ── Tab buttons: Bot Info / System Info ───────────────────
        tab_row = discord.ui.ActionRow()

        bot_style = discord.ButtonStyle.blurple if self.current_tab == "bot" else discord.ButtonStyle.gray
        sys_style = discord.ButtonStyle.blurple if self.current_tab == "system" else discord.ButtonStyle.gray

        btn_bot = discord.ui.Button(label="Bot Info", style=bot_style, custom_id="stats_bot_info")
        btn_bot.callback = self._on_bot_info
        tab_row.add_item(btn_bot)

        btn_sys = discord.ui.Button(label="System Info", style=sys_style, custom_id="stats_sys_info")
        btn_sys.callback = self._on_system_info
        tab_row.add_item(btn_sys)

        container.add_item(tab_row)
        self.add_item(container)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("This is not your stats panel!", ephemeral=True)
            return False
        return True

    async def _on_bot_info(self, interaction: discord.Interaction):
        self.current_tab = "bot"
        self._build()
        await interaction.response.edit_message(view=self)

    async def _on_system_info(self, interaction: discord.Interaction):
        self.current_tab = "system"
        self._build()
        await interaction.response.edit_message(view=self)


class Utility(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="ping", aliases=["latency"])
    @utility_cooldown()
    async def ping(self, ctx: commands.Context):
        """Check the bot's latency"""
        start = time.time()
        msg = await ctx.send("Pinging...")
        end = time.time()
        
        latency = (end - start) * 1000
        websocket = self.bot.latency * 1000
        
        embed = discord.Embed(
            title="Pong!",
            color=self.bot.config.EMBED_COLOR
        )
        embed.add_field(name="Websocket", value=f"{websocket:.0f}ms", inline=True)
        embed.add_field(name="API", value=f"{latency:.0f}ms", inline=True)
        
        await msg.edit(content=None, embed=embed)

    @commands.command(name="stats", aliases=["statistics", "botinfo"])
    @utility_cooldown()
    async def stats(self, ctx: commands.Context):
        """Check the bot's statistics"""
        import psutil
        import os
        from datetime import timedelta
        import wavelink
        from config import Config

        # ── Loading state ────────────────────────────────────────
        loading_view = discord.ui.LayoutView()
        loading_container = discord.ui.Container(accent_colour=discord.Colour(Config.EMBED_COLOR))
        loading_container.add_item(discord.ui.TextDisplay("**Loading Statistics...**\nPlease wait while data is being fetched."))
        loading_view.add_item(loading_container)
        msg = await ctx.send(view=loading_view)

        # ── Gather data ──────────────────────────────────────────
        process = psutil.Process(os.getpid())
        memory_usage = process.memory_info().rss / 1024 / 1024
        cpu_usage = process.cpu_percent(interval=0.1)

        uptime_seconds = time.time() - process.create_time()
        uptime = str(timedelta(seconds=int(uptime_seconds)))

        # Aggregate stats across ALL clusters from MongoDB
        total_guilds = 0
        total_users = 0
        total_channels = 0
        voice_clients = 0

        try:
            async for doc in self.bot.cluster_stats_col.find():
                total_guilds += doc.get("guilds", 0)
                total_users += doc.get("users", 0)
                total_channels += doc.get("channels", 0)
                voice_clients += doc.get("voice_clients", 0)
        except Exception:
            pass

        # Fallback to local data if DB is empty (e.g. first start before sync runs)
        if total_guilds == 0:
            total_guilds = len(self.bot.guilds)
            total_users = sum(g.member_count or 0 for g in self.bot.guilds)
            total_channels = sum(len(g.channels) for g in self.bot.guilds)
            voice_clients = len(self.bot.voice_clients)

        total_commands = len(self.bot.commands)

        nodes = wavelink.Pool.nodes
        lavalink_status = "Connected" if nodes else "Disconnected"

        # Shard details
        total_shards = self.bot.shard_count or 1
        cluster_id = getattr(self.bot, 'cluster_id', 0)
        cluster_count = getattr(self.bot, 'cluster_count', 1)
        cluster_shard_ids = self.bot.shard_ids or [0]
        guild_shard_id = ctx.guild.shard_id if ctx.guild else 0

        # ── Build the view ───────────────────────────────────────
        view = StatsView(
            bot=self.bot,
            author_id=ctx.author.id,
            total_guilds=total_guilds,
            total_users=total_users,
            total_channels=total_channels,
            total_commands=total_commands,
            voice_clients=voice_clients,
            lavalink_status=lavalink_status,
            total_shards=total_shards,
            cluster_id=cluster_id,
            cluster_count=cluster_count,
            cluster_shard_ids=cluster_shard_ids,
            guild_shard_id=guild_shard_id,
            cpu_usage=cpu_usage,
            memory_usage=memory_usage,
            uptime=uptime,
            ping=self.bot.latency * 1000,
        )
        await msg.edit(view=view)

    @commands.command(name="avatar", aliases=["av", "pfp"])
    @utility_cooldown()
    async def avatar(self, ctx: commands.Context, user: discord.User = None):
        """View a user's avatar"""
        user = user or ctx.author
        
        embed = discord.Embed(
            title=f"Avatar of {user.display_name}",
            color=self.bot.config.EMBED_COLOR
        )
        embed.set_image(url=user.display_avatar.url)
        embed.set_footer(text=f"Requested by {ctx.author.display_name}")
        
        view = discord.ui.View()
        view.add_item(discord.ui.Button(label="Download", style=discord.ButtonStyle.link, url=user.display_avatar.url))
        
        await ctx.send(embed=embed, view=view)

    @commands.command(name="banner", aliases=["bn"])
    @utility_cooldown()
    async def banner(self, ctx: commands.Context, user: discord.User = None):
        """View a user's banner"""
        user = user or ctx.author
        
        user = await self.bot.fetch_user(user.id)
        
        if not user.banner:
            return await ctx.send(embed=create_error_embed(f"**{user.display_name}** does not have a banner!"))
            
        embed = discord.Embed(
            title=f"Banner of {user.display_name}",
            color=self.bot.config.EMBED_COLOR
        )
        embed.set_image(url=user.banner.url)
        embed.set_footer(text=f"Requested by {ctx.author.display_name}")
        
        view = discord.ui.View()
        view.add_item(discord.ui.Button(label="Download", style=discord.ButtonStyle.link, url=user.banner.url))
        
        await ctx.send(embed=embed, view=view)

    @commands.command(name="userinfo", aliases=["ui", "whois"])
    @utility_cooldown()
    async def userinfo(self, ctx: commands.Context, member: discord.Member = None):
        """Show user information"""
        member = member or ctx.author
        
        roles = [role.mention for role in member.roles if role.name != "@everyone"]
        roles.reverse()
        
        embed = discord.Embed(
            title=f"User Info - {member.display_name}",
            color=member.color if member.color != discord.Color.default() else self.bot.config.EMBED_COLOR
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        
        embed.add_field(name="ID", value=member.id, inline=True)
        embed.add_field(name="Created At", value=f"<t:{int(member.created_at.timestamp())}:R>", inline=True)
        embed.add_field(name="Joined At", value=f"<t:{int(member.joined_at.timestamp())}:R>", inline=True)
        
        if roles:
            embed.add_field(name=f"Roles ({len(roles)})", value=" ".join(roles[:20]) + ("..." if len(roles) > 20 else ""), inline=False)
            
        embed.set_footer(text=f"Requested by {ctx.author.display_name}")
        await ctx.send(embed=embed)

    @commands.command(name="serverinfo", aliases=["si", "server"])
    @utility_cooldown()
    async def serverinfo(self, ctx: commands.Context):
        """Show server information"""
        guild = ctx.guild
        
        embed = discord.Embed(
            title=f"Server Info - {guild.name}",
            color=self.bot.config.EMBED_COLOR
        )
        
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
            
        embed.add_field(name="ID", value=guild.id, inline=True)
        embed.add_field(name="Owner", value=guild.owner.mention, inline=True)
        embed.add_field(name="Created At", value=f"<t:{int(guild.created_at.timestamp())}:R>", inline=True)
        
        embed.add_field(name="Members", value=f"Total: {guild.member_count}", inline=True)
        embed.add_field(name="Channels", value=f"Text: {len(guild.text_channels)}\nVoice: {len(guild.voice_channels)}", inline=True)
        embed.add_field(name="Roles", value=len(guild.roles), inline=True)
        
        embed.set_footer(text=f"Requested by {ctx.author.display_name}")
        await ctx.send(embed=embed)

    @commands.command(name="roleinfo", aliases=["ri", "role"])
    @utility_cooldown()
    async def roleinfo(self, ctx: commands.Context, role: discord.Role):
        """Show role information"""
        embed = discord.Embed(
            title=f"Role Info - {role.name}",
            color=role.color if role.color != discord.Color.default() else self.bot.config.EMBED_COLOR
        )
        
        embed.add_field(name="ID", value=role.id, inline=True)
        embed.add_field(name="Color", value=str(role.color), inline=True)
        embed.add_field(name="Created At", value=f"<t:{int(role.created_at.timestamp())}:R>", inline=True)
        
        embed.add_field(name="Hoisted", value="Yes" if role.hoist else "No", inline=True)
        embed.add_field(name="Managed", value="Yes" if role.managed else "No", inline=True)
        embed.add_field(name="Mentionable", value="Yes" if role.mentionable else "No", inline=True)
        
        embed.add_field(name="Members", value=len(role.members), inline=True)
        embed.add_field(name="Position", value=role.position, inline=True)
        
        permissions = [perm[0].replace("_", " ").title() for perm in role.permissions if perm[1]]
        if permissions:
             perm_list = ", ".join(permissions[:15]) + ("..." if len(permissions) > 15 else "")
             embed.add_field(name="Key Permissions", value=perm_list, inline=False)
        
        embed.set_footer(text=f"Requested by {ctx.author.display_name}")
        await ctx.send(embed=embed)

    @commands.command(name="uptime")
    @utility_cooldown()
    async def uptime(self, ctx: commands.Context):
        """Show bot uptime"""
        import psutil
        import os
        from datetime import timedelta
        
        process = psutil.Process(os.getpid())
        uptime_seconds = time.time() - process.create_time()
        uptime = str(timedelta(seconds=int(uptime_seconds)))
        
        embed = discord.Embed(
            title="Uptime",
            description=f"**{uptime}**",
            color=self.bot.config.EMBED_COLOR
        )
        await ctx.send(embed=embed)

    @commands.command(name="developer", aliases=["dev"])
    @utility_cooldown()
    async def developer(self, ctx: commands.Context):
        """View information about the bot's developer"""
        view = DeveloperView(self.bot)
        await ctx.send(view=view)

    @commands.command(name="iamsaksham")
    @utility_cooldown()
    async def iamsaksham(self, ctx: commands.Context):
        """View information about the bot's co-owner"""
        view = SakshamView(self.bot)
        await ctx.send(view=view)


async def setup(bot):
    await bot.add_cog(Utility(bot))
