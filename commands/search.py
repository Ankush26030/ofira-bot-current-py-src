import discord
from discord.ext import commands
import wavelink
from player import CustomPlayer, safe_connect
from utils.embeds import create_error_embed
from utils.checks import in_voice, same_voice
from utils.ratelimit import search_cooldown
from utils.formatters import format_duration
from config import Config


class SearchView(discord.ui.LayoutView):
    """Components V2 search results view."""

    def __init__(self, tracks: list[wavelink.Playable], player: CustomPlayer, ctx: commands.Context):
        super().__init__(timeout=60)
        self.tracks = tracks
        self.player = player
        self.ctx = ctx
        self._message: discord.Message | None = None  # set after send

        container = discord.ui.Container(accent_colour=discord.Colour(Config.EMBED_COLOR))

        # Header
        container.add_item(discord.ui.TextDisplay(
            f"{Config.EMOJI_SEARCH} **Search Results**\nSelect a track below to play."
        ))

        container.add_item(discord.ui.Separator())

        # Build numbered results list
        lines = []
        for i, track in enumerate(tracks[:10], 1):
            dur = format_duration(track.length) if track.length else "LIVE"
            lines.append(f"`{i}.` **{track.title}** — {track.author} `[{dur}]`")
        container.add_item(discord.ui.TextDisplay("\n".join(lines)))

        container.add_item(discord.ui.Separator())

        # Select dropdown
        select_row = discord.ui.ActionRow()
        options = []
        for i, track in enumerate(tracks[:10]):
            label = track.title[:100]
            desc = f"{track.author[:50]} | {format_duration(track.length)}" if track.length else f"{track.author[:50]} | LIVE"
            options.append(discord.SelectOption(label=label, description=desc[:100], value=str(i)))

        select = discord.ui.Select(
            placeholder="🎵 Select a track to play...",
            custom_id="search_select",
            min_values=1,
            max_values=1,
            options=options,
        )
        select.callback = self._on_select
        select_row.add_item(select)
        container.add_item(select_row)

        self.add_item(container)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message(
                f"{Config.EMOJI_CROSS} This menu is not for you!",
                ephemeral=True,
            )
            return False
        return True

    async def _on_select(self, interaction: discord.Interaction):
        index = int(interaction.data.get("values", ["0"])[0])
        track = self.tracks[index]
        track.requester = self.ctx.author

        await self.player.queue.put_wait(track)

        if not self.player.playing:
            await self.player.play(await self.player.queue.get_wait())

        # Send confirmation
        confirm_view = discord.ui.LayoutView(timeout=15)
        confirm_container = discord.ui.Container(accent_colour=discord.Colour(Config.EMBED_COLOR))
        confirm_container.add_item(discord.ui.TextDisplay(
            f"{Config.EMOJI_TICK} Added **{track.title}** by {track.author} to queue"
        ))
        confirm_view.add_item(confirm_container)
        await interaction.response.send_message(view=confirm_view, delete_after=10)

        # Auto-delete the search results message
        self.stop()
        if self._message:
            try:
                await self._message.delete()
            except discord.HTTPException:
                pass

    async def on_timeout(self):
        # Auto-delete on timeout too
        if self._message:
            try:
                await self._message.delete()
            except discord.HTTPException:
                pass


class Search(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="search")
    @search_cooldown()
    @in_voice()
    async def search(self, ctx: commands.Context, *, query: str):
        """Search for a song and select from results"""

        # Connect if needed
        if not ctx.guild.voice_client:
            try:
                vc = await safe_connect(ctx.author.voice.channel)
            except Exception as e:
                return await ctx.send(embed=create_error_embed(f"Failed to join: {e}"))

        vc: CustomPlayer = ctx.guild.voice_client
        vc.text_channel = ctx.channel

        if vc.channel != ctx.author.voice.channel:
            return await ctx.send(embed=create_error_embed("You must be in the same voice channel as me!"))

        source = None
        if not query.startswith(("http:", "https:")):
            source = self.bot.search_source

        if source:
            tracks = await wavelink.Playable.search(query, source=source)
        else:
            tracks = await wavelink.Playable.search(query)

        if not tracks:
            return await ctx.send(embed=create_error_embed("No tracks found."))

        if isinstance(tracks, wavelink.Playlist):
            return await ctx.send(embed=create_error_embed("Found a playlist. Use `play` command for playlists."))

        # Show Components V2 search view
        view = SearchView(tracks[:10], vc, ctx)
        msg = await ctx.send(view=view)
        view._message = msg  # store ref for auto-delete


async def setup(bot):
    await bot.add_cog(Search(bot))
