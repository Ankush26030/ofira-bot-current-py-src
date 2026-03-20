import discord
from discord.ext import commands
from utils.embeds import create_error_embed
from utils.ratelimit import utility_cooldown
from config import Config


class HelpView(discord.ui.LayoutView):
    """Components V2 Help Menu using LayoutView."""

    def __init__(self, bot, author_id: int, prefix: str, total_commands: int):
        super().__init__(timeout=180)
        self.bot = bot
        self.author_id = author_id
        self.prefix = prefix
        self.total_commands = total_commands

        # ── Main Container ───────────────────────────────────────
        container = discord.ui.Container(accent_colour=discord.Colour(Config.EMBED_COLOR))

        # Header
        container.add_item(discord.ui.TextDisplay(
            f"### {bot.user.name} — Help Menu"
        ))

        # Bot overview
        overview = (
            f"<:Pencil:1475513048386240582> Server Prefix: `{prefix}`\n"
            f"<:commands:1475513135619117148> Total Commands: `{total_commands}`\n"
            f"<:linksx:1475513308445671658> [Get Support](https://dsc.gg/nothingbot)"
        )
        container.add_item(discord.ui.TextDisplay(overview))

        container.add_item(discord.ui.Separator())

        # Category list
        categories = (
            "**Select a category below**\n"
            "<:music:1475509142960603247> Music\n"
            "<:filterssetupglossyuibuttonwithpi:1475510101354746060> Filters\n"
            "<:utility:1475510261413843097> Utility\n"
            "<:playlist:1475510474605990008> Playlist\n"
            "<:spotify:1475510920489730243> Spotify\n"
            "<:Moderation:1475511231392776302> Moderation\n"
            "<:vcmod:1475511631403417692> VC Mod\n"
            "<:Giveaway:1479481613392937074> Giveaway"
        )
        container.add_item(discord.ui.TextDisplay(categories))

        container.add_item(discord.ui.Separator())

        # Category select
        select_row = discord.ui.ActionRow()
        select = discord.ui.Select(
            placeholder="📂 Select a category...",
            custom_id="help_select",
            min_values=1,
            max_values=1,
            options=[
                discord.SelectOption(label="Music",      value="Music",      emoji="<:music:1475509142960603247>",                                     description="Play, search, skip, queue, and volume"),
                discord.SelectOption(label="Filters",    value="Filters",    emoji="<:filterssetupglossyuibuttonwithpi:1475510101354746060>",           description="Bassboost, Nightcore, 8D, and more"),
                discord.SelectOption(label="Utility",    value="Utility",    emoji="<:utility:1475510261413843097>",                                   description="Settings and other tools"),
                discord.SelectOption(label="Playlist",   value="Playlist",   emoji="<:playlist:1475510474605990008>",                                  description="Manage custom playlists"),
                discord.SelectOption(label="Spotify",    value="Spotify",    emoji="<:spotify:1475510920489730243>",                                   description="Albums, artists, and playlists"),
                discord.SelectOption(label="Moderation", value="Moderation", emoji="<:Moderation:1475511231392776302>",                                description="Moderation tools"),
                discord.SelectOption(label="VC Mod",     value="VC Mod",     emoji="<:vcmod:1475511631403417692>",                                     description="Voice channel moderation"),
                discord.SelectOption(label="Giveaway",   value="Giveaway",   emoji="<:Giveaway:1479481613392937074>",                                  description="Host and manage giveaways"),
            ],
        )
        select.callback = self._on_category_select
        select_row.add_item(select)
        container.add_item(select_row)

        container.add_item(discord.ui.Separator())

        # Link buttons
        invite_url = f"https://discord.com/api/oauth2/authorize?client_id={bot.user.id}&permissions=8&scope=bot%20applications.commands"
        btn_row = discord.ui.ActionRow()

        btn_invite = discord.ui.Button(label="Invite Me", style=discord.ButtonStyle.link, url=invite_url)
        btn_row.add_item(btn_invite)

        btn_support = discord.ui.Button(label="Support", style=discord.ButtonStyle.link, url=Config.SUPPORT_SERVER)
        btn_row.add_item(btn_support)

        container.add_item(btn_row)

        self.add_item(container)

    # ── Category mapping ─────────────────────────────────────────
    CATEGORY_COGS = {
        "Music":      ["Play", "Control", "Queue", "Voice", "Advanced", "Search"],
        "Filters":    ["Filters"],
        "Utility":    ["Settings", "AFK", "Help", "Utility", "Customize", "Badges"],
        "Playlist":   ["Playlist"],
        "Spotify":    ["Spotify"],
        "Moderation": ["Moderation"],
        "VC Mod":     ["VCMod"],
        "Giveaway":   ["Giveaway"],
    }

    CATEGORY_EMOJIS = {
        "Music":      "<:music:1475509142960603247>",
        "Filters":    "<:filterssetupglossyuibuttonwithpi:1475510101354746060>",
        "Utility":    "<:utility:1475510261413843097>",
        "Playlist":   "<:playlist:1475510474605990008>",
        "Spotify":    "<:spotify:1475510920489730243>",
        "Moderation": "<:Moderation:1475511231392776302>",
        "VC Mod":     "<:vcmod:1475511631403417692>",
        "Giveaway":   "<:Giveaway:1479481613392937074>",
    }

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                f"{Config.EMOJI_CROSS} This help menu is not for you!",
                ephemeral=True,
            )
            return False
        return True

    async def _on_category_select(self, interaction: discord.Interaction):
        category = interaction.data.get("values", [None])[0]
        if not category:
            return

        cog_names = self.CATEGORY_COGS.get(category, [])
        emoji = self.CATEGORY_EMOJIS.get(category, "📂")

        cmds = []
        for cog_name in cog_names:
            cog = self.bot.get_cog(cog_name)
            if cog:
                cmds.extend(cog.get_commands())

        # Format command list
        if not cmds:
            cmd_text = "*No commands found in this category.*"
        else:
            lines = []
            for cmd in cmds:
                if cmd.hidden:
                    continue
                lines.append(f"{Config.EMOJI_DOT} **{self.prefix}{cmd.name}** — {cmd.short_doc or 'No description'}")
                if isinstance(cmd, commands.Group):
                    for sub in cmd.commands:
                        if sub.hidden:
                            continue
                        lines.append(f"  ╚ **{sub.name}** — {sub.short_doc or 'No description'}")
            cmd_text = "\n".join(lines) if lines else "*No commands found.*"

        # Build new view with the category content shown
        new_container = discord.ui.Container(accent_colour=discord.Colour(Config.EMBED_COLOR))

        # Category header
        new_container.add_item(discord.ui.TextDisplay(f"### {emoji} {category} Commands"))
        new_container.add_item(discord.ui.Separator())

        # Command list
        new_container.add_item(discord.ui.TextDisplay(cmd_text))

        new_container.add_item(discord.ui.Separator())

        # Re-add category select
        select_row = discord.ui.ActionRow()
        select = discord.ui.Select(
            placeholder="📂 Select a category...",
            custom_id="help_select",
            min_values=1,
            max_values=1,
            options=[
                discord.SelectOption(label="Music",      value="Music",      emoji="<:music:1475509142960603247>",                                     description="Play, search, skip, queue, and volume"),
                discord.SelectOption(label="Filters",    value="Filters",    emoji="<:filterssetupglossyuibuttonwithpi:1475510101354746060>",           description="Bassboost, Nightcore, 8D, and more"),
                discord.SelectOption(label="Utility",    value="Utility",    emoji="<:utility:1475510261413843097>",                                   description="Settings and other tools"),
                discord.SelectOption(label="Playlist",   value="Playlist",   emoji="<:playlist:1475510474605990008>",                                  description="Manage custom playlists"),
                discord.SelectOption(label="Spotify",    value="Spotify",    emoji="<:spotify:1475510920489730243>",                                   description="Albums, artists, and playlists"),
                discord.SelectOption(label="Moderation", value="Moderation", emoji="<:Moderation:1475511231392776302>",                                description="Moderation tools"),
                discord.SelectOption(label="VC Mod",     value="VC Mod",     emoji="<:vcmod:1475511631403417692>",                                     description="Voice channel moderation"),
                discord.SelectOption(label="Giveaway",   value="Giveaway",   emoji="<:Giveaway:1479481613392937074>",                                  description="Host and manage giveaways"),
            ],
        )
        select.callback = self._on_category_select
        select_row.add_item(select)
        new_container.add_item(select_row)

        new_container.add_item(discord.ui.Separator())

        # Link buttons
        invite_url = f"https://discord.com/api/oauth2/authorize?client_id={self.bot.user.id}&permissions=8&scope=bot%20applications.commands"
        btn_row = discord.ui.ActionRow()
        btn_row.add_item(discord.ui.Button(label="Invite Me", style=discord.ButtonStyle.link, url=invite_url))
        btn_row.add_item(discord.ui.Button(label="Support", style=discord.ButtonStyle.link, url=Config.SUPPORT_SERVER))
        new_container.add_item(btn_row)

        # Replace items in view
        new_view = discord.ui.LayoutView(timeout=180)
        new_view.add_item(new_container)

        # Copy interaction check
        original_author = self.author_id
        original_bot = self.bot

        async def check(inter):
            if inter.user.id != original_author:
                await inter.response.send_message(
                    f"{Config.EMOJI_CROSS} This help menu is not for you!",
                    ephemeral=True,
                )
                return False
            return True

        new_view.interaction_check = check

        # Re-bind callback on select so it keeps working 
        for child in new_view.walk_children():
            if isinstance(child, discord.ui.Select) and child.custom_id == "help_select":
                child.callback = self._on_category_select
                break

        await interaction.response.edit_message(view=new_view)


class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="help", aliases=["h", "commands"])
    @utility_cooldown()
    async def help_command(self, ctx: commands.Context):
        """Show this help message"""

        # Count all commands including subcommands of groups
        def count_commands(cmds):
            total = 0
            for cmd in cmds:
                if cmd.hidden:
                    continue
                total += 1
                if isinstance(cmd, commands.Group):
                    total += count_commands(cmd.commands)
            return total

        total_commands = count_commands(self.bot.commands)

        server_prefix = self.bot.config.DEFAULT_PREFIX
        if ctx.guild:
            config = await self.bot.prefixes_col.find_one({"guild_id": ctx.guild.id})
            if config:
                server_prefix = config["prefix"]

        view = HelpView(self.bot, ctx.author.id, server_prefix, total_commands)
        await ctx.send(view=view)

    @commands.command(name="invite")
    @utility_cooldown()
    async def invite_command(self, ctx: commands.Context):
        """Get the bot invite link"""
        invite_url = f"https://discord.com/api/oauth2/authorize?client_id={self.bot.user.id}&permissions=8&scope=bot%20applications.commands"

        container = discord.ui.Container(accent_colour=discord.Colour(Config.EMBED_COLOR))
        container.add_item(discord.ui.TextDisplay(
            f"### Invite Me!\n[Click here to invite me to your server!]({invite_url})"
        ))
        view = discord.ui.LayoutView(timeout=60)
        view.add_item(container)
        await ctx.send(view=view)

    @commands.command(name="support", aliases=["supportserver"])
    @utility_cooldown()
    async def support_command(self, ctx: commands.Context):
        """Get the support server link"""
        container = discord.ui.Container(accent_colour=discord.Colour(Config.EMBED_COLOR))
        container.add_item(discord.ui.TextDisplay(
            f"### Support Server\nNeed help? [Click here to join]({Config.SUPPORT_SERVER})!"
        ))
        view = discord.ui.LayoutView(timeout=60)
        view.add_item(container)
        await ctx.send(view=view)


async def setup(bot):
    await bot.add_cog(Help(bot))
