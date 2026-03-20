import discord
import wavelink
from player import CustomPlayer
from utils.embeds import create_success_embed, create_error_embed
from bson import ObjectId
from config import Config

import time

class PaginatedListView(discord.ui.View):
    """Reusable pagination view for list commands"""
    def __init__(self, items, title, items_per_page=10, color=0x2F3136, footer_text=None, author_id=None, description_prefix=None):
        super().__init__(timeout=180)
        self.items = items
        self.title = title
        self.items_per_page = items_per_page
        self.color = color
        self.footer_text = footer_text
        self.author_id = author_id
        self.description_prefix = description_prefix
        self.current_page = 0
        self.max_pages = max(1, (len(items) + items_per_page - 1) // items_per_page)
        
        # Update button states
        self.update_buttons()
    
    def update_buttons(self):
        """Update button states based on current page"""
        self.previous_button.disabled = self.current_page == 0
        self.next_button.disabled = self.current_page >= self.max_pages - 1
    
    def get_embed(self):
        """Generate embed for current page"""
        start = self.current_page * self.items_per_page
        end = start + self.items_per_page
        page_items = self.items[start:end]
        
        # Number the items
        numbered_items = [f"{start + i + 1}. {item}" for i, item in enumerate(page_items)]
        
        description = "\n".join(numbered_items) if numbered_items else "No items found."
        
        if self.description_prefix:
            description = f"{self.description_prefix}\n\n{description}"
            
        embed = discord.Embed(
            title=self.title,
            description=description,
            color=self.color
        )
        
        footer = f"Page {self.current_page + 1}/{self.max_pages}"
        if self.footer_text:
            footer += f" • {self.footer_text}"
        embed.set_footer(text=footer)
        
        return embed
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Only allow the command author to interact"""
        if self.author_id and interaction.user.id != self.author_id:
            await interaction.response.send_message(f"{Config.EMOJI_CROSS} This is not your list!", ephemeral=True)
            return False
        return True
    
    @discord.ui.button(emoji="⬅️", label="Previous", style=discord.ButtonStyle.blurple, row=0)
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page = max(0, self.current_page - 1)
        self.update_buttons()
        await interaction.response.edit_message(embed=self.get_embed(), view=self)
    
    @discord.ui.button(emoji="➡️", label="Next", style=discord.ButtonStyle.blurple, row=0)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page = min(self.max_pages - 1, self.current_page + 1)
        self.update_buttons()
        await interaction.response.edit_message(embed=self.get_embed(), view=self)
    
    @discord.ui.button(emoji="🗑️", label="Delete", style=discord.ButtonStyle.red, row=0)
    async def delete_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.delete()


class PlaylistSelect(discord.ui.Select):
    def __init__(self, bot, playlists, track):
        self.bot = bot
        self.track = track
        options = [
            discord.SelectOption(label=p["name"], value=str(p["_id"]), description=f"{len(p.get('tracks', []))} tracks") 
            for p in playlists
        ]
        super().__init__(placeholder="Select a playlist...", options=options)

    async def callback(self, interaction: discord.Interaction):
        playlist_id = self.values[0]
        track_data = {
            "title": self.track.title,
            "uri": self.track.uri,
            "author": self.track.author,
            "length": self.track.length,
            "is_stream": self.track.is_stream
        }
        
        await self.bot.playlists_col.update_one(
            {"_id": ObjectId(playlist_id)},
            {"$push": {"tracks": track_data}}
        )
        
        await interaction.response.edit_message(content=f"{Config.EMOJI_TICK} Added **{self.track.title}** to playlist!", view=None)

class PlaylistSelectView(discord.ui.View):
    def __init__(self, bot, playlists, track):
        super().__init__(timeout=60)
        self.add_item(PlaylistSelect(bot, playlists, track))

class NowPlayingView(discord.ui.LayoutView):
    """Components V2 Now-Playing view.

    Structure
    ---------
    Container (accent_colour = blurple):
        TextDisplay  – "🎵 Now Playing"
        MediaGallery – canvas music card (attachment://music_card.png)
        TextDisplay  – status line
        Separator
        ActionRow    – Previous | Pause/Resume | Skip | Stop
        ActionRow    – Autoplay | Shuffle | Save | Filters (select)
    """

    def __init__(self, player: CustomPlayer, card_file: discord.File | None = None):
        super().__init__(timeout=None)
        self.player = player
        self._cooldowns: dict[int, float] = {}
        self._last_warn: dict[int, float] = {}
        self._active_filters: set[str] = set()
        self._card_file = card_file

        # ── Build the Container ──────────────────────────────────
        container = discord.ui.Container(accent_colour=discord.Colour(Config.EMBED_COLOR))

        # Title
        track = player.current
        title_text = f"{Config.EMOJI_PLAYING} **Now Playing**"
        container.add_item(discord.ui.TextDisplay(title_text))

        container.add_item(discord.ui.Separator())

        # Music card image (from attachment)
        if card_file:
            gallery = discord.ui.MediaGallery(
                discord.MediaGalleryItem(media="attachment://music_card.png")
            )
            container.add_item(gallery)

        # Status line
        status = self._build_status_text()
        if status:
            container.add_item(discord.ui.TextDisplay(status))

        # Separator
        container.add_item(discord.ui.Separator())

        # ── Filter Select (row 1) ────────────────────────────────
        filter_row = discord.ui.ActionRow()
        filter_select = discord.ui.Select(
            placeholder="🎛️ Select a filter...",
            custom_id="np_filter_select",
            min_values=1,
            max_values=1,
            options=[
                discord.SelectOption(label="Bass Boost",  value="bassboost",  emoji="🔊", description="Heavy bass enhancement"),
                discord.SelectOption(label="Nightcore",   value="nightcore",  emoji="👻", description="Speed + pitch up"),
                discord.SelectOption(label="8D Audio",    value="8d",         emoji="🎧", description="Rotating stereo effect"),
                discord.SelectOption(label="Vaporwave",   value="vaporwave",  emoji="📼", description="Slowed + lower pitch"),
                discord.SelectOption(label="Karaoke",     value="karaoke",    emoji="🎤", description="Remove vocals"),
                discord.SelectOption(label="Reset All",   value="reset",      emoji="❌", description="Remove all filters"),
            ],
        )
        filter_select.callback = self._on_filter_select
        filter_row.add_item(filter_select)
        container.add_item(filter_row)

        container.add_item(discord.ui.Separator())

        # ── Playback buttons (row 2) ─────────────────────────────
        row1 = discord.ui.ActionRow()

        btn_prev = discord.ui.Button(label="Previous", style=discord.ButtonStyle.blurple, custom_id="np_previous")
        btn_prev.callback = self._on_previous
        row1.add_item(btn_prev)

        pause_label = "Resume" if player.paused else "Pause"
        pause_style = discord.ButtonStyle.green if player.paused else discord.ButtonStyle.blurple
        btn_pause = discord.ui.Button(label=pause_label, style=pause_style, custom_id="np_pause_resume")
        btn_pause.callback = self._on_pause_resume
        row1.add_item(btn_pause)

        btn_skip = discord.ui.Button(label="Skip", style=discord.ButtonStyle.blurple, custom_id="np_skip")
        btn_skip.callback = self._on_skip
        row1.add_item(btn_skip)

        btn_stop = discord.ui.Button(label="Stop", style=discord.ButtonStyle.red, custom_id="np_stop")
        btn_stop.callback = self._on_stop
        row1.add_item(btn_stop)

        container.add_item(row1)

        # ── Utility buttons (row 3) ──────────────────────────────
        row2 = discord.ui.ActionRow()

        ap_style = discord.ButtonStyle.green if getattr(player, 'autoplay_enabled', False) else discord.ButtonStyle.gray
        btn_ap = discord.ui.Button(label="Autoplay", style=ap_style, custom_id="np_autoplay")
        btn_ap.callback = self._on_autoplay
        row2.add_item(btn_ap)

        btn_shuf = discord.ui.Button(label="Shuffle", style=discord.ButtonStyle.gray, custom_id="np_shuffle")
        btn_shuf.callback = self._on_shuffle
        row2.add_item(btn_shuf)

        btn_save = discord.ui.Button(label="Save", style=discord.ButtonStyle.gray, custom_id="np_save")
        btn_save.callback = self._on_save
        row2.add_item(btn_save)

        container.add_item(row2)

        self.add_item(container)

    # ── Helpers ───────────────────────────────────────────────────

    def _build_status_text(self) -> str:
        """Build the status line shown under the music card."""
        parts: list[str] = []
        player = self.player
        track = player.current

        if player.paused:
            parts.append("⏸️ Paused")

        if hasattr(player, 'loop_mode'):
            if player.loop_mode == "track":
                parts.append("🔂 Loop Track")
            elif player.loop_mode == "queue":
                parts.append("🔁 Loop Queue")

        if getattr(player, 'autoplay_enabled', False):
            parts.append("🎲 Autoplay")

        vol = player.volume
        vol_emoji = Config.EMOJI_VOLUME_LOW if vol < 50 else Config.EMOJI_VOLUME_HIGH
        parts.append(f"{vol_emoji} {vol}%")

        if hasattr(player, 'queue') and not player.queue.is_empty:
            parts.append(f"📋 {player.queue.count} in queue")

        return " **·** ".join(parts)

    async def _voice_check(self, interaction: discord.Interaction) -> bool:
        """Common voice-channel & cooldown checks. Returns True if OK."""
        # Blacklist
        if await self.player.client.is_blacklisted(interaction.user.id):
            try:
                await interaction.response.defer()
            except Exception:
                pass
            return False

        if not interaction.user.voice or not interaction.guild.voice_client:
            await interaction.response.send_message(
                f"{Config.EMOJI_CROSS} You aren't connected to voice!", ephemeral=True
            )
            return False

        if interaction.user.voice.channel != interaction.guild.voice_client.channel:
            await interaction.response.send_message(
                f"{Config.EMOJI_CROSS} You must be in the same voice channel!", ephemeral=True
            )
            return False

        # Cooldown (2.0s)
        user_id = interaction.user.id
        now = time.time()
        if user_id in self._cooldowns:
            end_time = self._cooldowns[user_id]
            if now < end_time:
                retry_after = end_time - now
                last_warn = self._last_warn.get(user_id, 0)
                if now - last_warn > 3.0:
                    self._last_warn[user_id] = now
                    await interaction.response.send_message(
                        f"⏰ Please wait {retry_after:.1f}s!", ephemeral=True, delete_after=3
                    )
                else:
                    try:
                        await interaction.response.defer()
                    except Exception:
                        pass
                return False

        self._cooldowns[user_id] = now + 2.0
        return True

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return await self._voice_check(interaction)

    # ── Previous ────
    async def _on_previous(self, interaction: discord.Interaction):
        if len(self.player.history) < 2:
            return await interaction.response.send_message(
                embed=create_error_embed("No previous track in history!"), ephemeral=True
            )
        track = self.player.history[-2]
        await self.player.play(track)
        await interaction.response.send_message(
            embed=create_success_embed(f"Playing previous: **{track.title}**"),
            ephemeral=True, delete_after=3,
        )

    # ── Pause / Resume ────
    async def _on_pause_resume(self, interaction: discord.Interaction):
        should_pause = not self.player.paused
        await self.player.pause(should_pause)

        # Rebuild view with updated state
        from utils.music_card import generate_music_card
        card_file = await generate_music_card(
            self.player.current,
            position=self.player.position,
            requester=getattr(self.player.current, 'requester', None),
        )
        new_view = NowPlayingView(self.player, card_file)
        await interaction.response.edit_message(attachments=[card_file], view=new_view)

    # ── Skip ────
    async def _on_skip(self, interaction: discord.Interaction):
        if not self.player.current:
            return await interaction.response.send_message(
                embed=create_error_embed("Nothing is playing!"), ephemeral=True
            )
        await self.player.skip(force=True)
        await interaction.response.send_message(
            embed=create_success_embed("Skipped track"),
            ephemeral=True, delete_after=3,
        )

    # ── Stop ────
    async def _on_stop(self, interaction: discord.Interaction):
        settings = await self.player.client.settings_col.find_one({"guild_id": interaction.guild.id})
        is_247 = settings and settings.get("247", False)

        if hasattr(self.player, 'np_message') and self.player.np_message:
            try:
                await self.player.np_message.delete()
            except Exception:
                pass

        if hasattr(self.player, 'queue'):
            self.player.queue.clear()

        await self.player.stop()

        if self.player.channel:
            try:
                await self.player.channel.edit(status=None)
            except Exception:
                pass

        if is_247:
            await interaction.response.send_message(
                embed=create_success_embed(
                    "⏹️ Stopped playback and cleared queue\n\n*24/7 mode is enabled - staying in voice channel*"
                ),
                ephemeral=True, delete_after=5,
            )
        else:
            await self.player.disconnect()
            await interaction.response.send_message(
                embed=create_success_embed("Stopped player and disconnected"),
                ephemeral=True, delete_after=3,
            )

    # ── Autoplay ────
    async def _on_autoplay(self, interaction: discord.Interaction):
        state = self.player.toggle_autoplay()
        msg = "Autoplay enabled" if state else "Autoplay disabled"

        from utils.music_card import generate_music_card
        card_file = await generate_music_card(
            self.player.current,
            position=self.player.position,
            requester=getattr(self.player.current, 'requester', None),
        )
        new_view = NowPlayingView(self.player, card_file)
        await interaction.response.edit_message(attachments=[card_file], view=new_view)
        await interaction.followup.send(embed=create_success_embed(msg), ephemeral=True)

    # ── Shuffle ────
    async def _on_shuffle(self, interaction: discord.Interaction):
        if self.player.queue.is_empty:
            return await interaction.response.send_message(
                embed=create_error_embed("Queue is empty!"), ephemeral=True
            )
        self.player.queue.shuffle()
        await interaction.response.send_message(
            embed=create_success_embed("Queue shuffled! 🔀"),
            ephemeral=True, delete_after=3,
        )

    # ── Save ────
    async def _on_save(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        cursor = self.player.client.playlists_col.find({"user_id": user_id})
        playlists = await cursor.to_list(length=25)

        if not playlists:
            return await interaction.response.send_message(
                "You don't have any playlists! Create one with `,playlist create`.",
                ephemeral=True,
            )

        track = self.player.current
        if not track:
            return await interaction.response.send_message("No track is playing!", ephemeral=True)

        if len(playlists) == 1:
            p = playlists[0]
            track_data = {
                "title": track.title,
                "uri": track.uri,
                "author": track.author,
                "length": track.length,
                "is_stream": track.is_stream,
            }
            await self.player.client.playlists_col.update_one(
                {"_id": p["_id"]}, {"$push": {"tracks": track_data}}
            )
            await interaction.response.send_message(
                f"{Config.EMOJI_TICK} Saved **{track.title}** to **{p['name']}**!",
                ephemeral=True,
            )
        else:
            view = PlaylistSelectView(self.player.client, playlists, track)
            await interaction.response.send_message(
                "Select a playlist to save to:", view=view, ephemeral=True
            )

    # ── Filter select ────
    async def _on_filter_select(self, interaction: discord.Interaction):
        selected = interaction.data.get("values", [None])[0]
        if not selected:
            return

        filters = self.player.filters
        msg = ""

        if selected == "reset":
            filters.reset()
            self._active_filters.clear()
            msg = "All filters reset"
        elif selected == "bassboost":
            if "bassboost" in self._active_filters:
                filters.equalizer.reset()
                self._active_filters.discard("bassboost")
                msg = "Bass Boost disabled"
            else:
                gain = 0.35
                bands = [{"band": i, "gain": gain * (1.0 - (i * 0.2))} for i in range(5)]
                filters.equalizer.set(bands=bands)
                self._active_filters.add("bassboost")
                msg = "Bass Boost enabled"
        elif selected == "nightcore":
            if "nightcore" in self._active_filters:
                filters.timescale.reset()
                self._active_filters.discard("nightcore")
                msg = "Nightcore disabled"
            else:
                filters.timescale.set(speed=1.2, pitch=1.2, rate=1.0)
                self._active_filters.add("nightcore")
                self._active_filters.discard("vaporwave")
                msg = "Nightcore enabled"
        elif selected == "8d":
            if "8d" in self._active_filters:
                filters.rotation.reset()
                self._active_filters.discard("8d")
                msg = "8D Audio disabled"
            else:
                filters.rotation.set(rotation_hz=0.2)
                self._active_filters.add("8d")
                msg = "8D Audio enabled"
        elif selected == "vaporwave":
            if "vaporwave" in self._active_filters:
                filters.timescale.reset()
                self._active_filters.discard("vaporwave")
                msg = "Vaporwave disabled"
            else:
                filters.timescale.set(pitch=0.8, speed=0.8)
                self._active_filters.add("vaporwave")
                self._active_filters.discard("nightcore")
                msg = "Vaporwave enabled"
        elif selected == "karaoke":
            if "karaoke" in self._active_filters:
                filters.karaoke.reset()
                self._active_filters.discard("karaoke")
                msg = "Karaoke disabled"
            else:
                filters.karaoke.set(level=1.0, mono_level=1.0, filter_band=220.0, filter_width=100.0)
                self._active_filters.add("karaoke")
                msg = "Karaoke enabled"

        await self.player.set_filters(filters)

        # Update the select options to show active filters with ✅
        from utils.music_card import generate_music_card
        card_file = await generate_music_card(
            self.player.current,
            position=self.player.position,
            requester=getattr(self.player.current, 'requester', None),
        )
        new_view = NowPlayingView(self.player, card_file)
        new_view._active_filters = self._active_filters.copy()
        # Update select labels
        self._update_filter_labels(new_view)

        await interaction.response.edit_message(attachments=[card_file], view=new_view)
        await interaction.followup.send(embed=create_success_embed(msg), ephemeral=True)

    def _update_filter_labels(self, view: 'NowPlayingView'):
        """Add ✅ prefix to active filter option labels."""
        for child in view.walk_children():
            if isinstance(child, discord.ui.Select) and child.custom_id == "np_filter_select":
                for opt in child.options:
                    if opt.value in self._active_filters:
                        if not opt.label.startswith("✅"):
                            opt.label = f"✅ {opt.label}"
                break


# Keep old names as aliases for backward compatibility (other cogs may import them)
PlayerControls = NowPlayingView
FilterView = None  # No longer used
