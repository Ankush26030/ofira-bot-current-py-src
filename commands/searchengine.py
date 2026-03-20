import discord
from discord.ext import commands
from config import Config


# ── Available search sources ─────────────────────────────────────
SOURCES = {
    "ytsearch":  {"label": "YouTube",       "emoji": "🔴"},
    "ytmsearch": {"label": "YouTube Music", "emoji": "🎵"},
    "scsearch":  {"label": "SoundCloud",    "emoji": "☁️"},
    "spsearch":  {"label": "Spotify",       "emoji": "🟢"},
    "dzsearch":  {"label": "Deezer",        "emoji": "🎧"},
}


def _build_view(bot, author_id: int) -> discord.ui.LayoutView:
    """Build a Components V2 LayoutView for the search engine selector."""
    current = bot.search_source
    current_info = SOURCES.get(current, {})

    view = discord.ui.LayoutView(timeout=30)
    container = discord.ui.Container(accent_colour=discord.Colour(Config.EMBED_COLOR))

    # Header
    container.add_item(discord.ui.TextDisplay(
        "### 🔍 Search Engine Settings"
    ))

    container.add_item(discord.ui.Separator())

    # Current source
    container.add_item(discord.ui.TextDisplay(
        f"**Current Source:** {current_info.get('emoji', '')} **{current_info.get('label', current)}**\n\n"
        "Click a button below to switch the default search engine.\n"
        "This affects `,play`, `,search`, autoplay, and track refresh."
    ))

    container.add_item(discord.ui.Separator())

    # Available sources list
    lines = []
    for key, src in SOURCES.items():
        marker = "▸" if key == current else "▹"
        lines.append(f"{marker} {src['emoji']} **{src['label']}** — `{key}`")
    container.add_item(discord.ui.TextDisplay("\n".join(lines)))

    container.add_item(discord.ui.Separator())

    # Buttons row
    btn_row = discord.ui.ActionRow()
    for key, info in SOURCES.items():
        is_active = key == current
        btn = discord.ui.Button(
            label=f"{'✅ ' if is_active else ''}{info['label']}",
            style=discord.ButtonStyle.success if is_active else discord.ButtonStyle.secondary,
            custom_id=f"se_{key}",
            disabled=is_active,
        )
        btn_row.add_item(btn)
    container.add_item(btn_row)

    # Footer
    container.add_item(discord.ui.TextDisplay(
        "-# ⚠️ Some sources require the corresponding Lavalink plugin."
    ))

    view.add_item(container)
    return view


class SearchEngine(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        """Handle search engine button clicks."""
        if not interaction.data or interaction.data.get("component_type") != 2:
            return
        custom_id = interaction.data.get("custom_id", "")
        if not custom_id.startswith("se_"):
            return

        # Owner-only check
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message(
                f"{Config.EMOJI_CROSS} Only the bot owner can use this!",
                ephemeral=True,
            )
            return

        source_key = custom_id[3:]  # strip "se_"
        if source_key not in SOURCES:
            return

        # Update the source
        self.bot.search_source = source_key
        info = SOURCES[source_key]

        # Rebuild the view with the new active state
        new_view = _build_view(self.bot, interaction.user.id)
        await interaction.response.edit_message(view=new_view)

    @commands.command(name="searchengine", aliases=["se", "source"])
    @commands.is_owner()
    async def searchengine(self, ctx: commands.Context):
        """Change the bot's default search engine (Owner only)"""
        view = _build_view(self.bot, ctx.author.id)
        await ctx.send(view=view)


async def setup(bot):
    await bot.add_cog(SearchEngine(bot))
