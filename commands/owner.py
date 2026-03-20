import discord
from discord.ext import commands
import asyncio
import re
import time as _time
import zipfile
import io
import os
import datetime


# ────────────────────────────── Helpers ──────────────────────────────

def _owner_view(bot, title: str, body: str, *, error: bool = False) -> discord.ui.LayoutView:
    """Build a Components V2 view for owner command responses."""
    colour = bot.config.ERROR_COLOR if error else bot.config.EMBED_COLOR
    view = discord.ui.LayoutView()
    container = discord.ui.Container(accent_colour=discord.Colour(colour))
    container.add_item(discord.ui.TextDisplay(f"### {title}"))
    container.add_item(discord.ui.Separator())
    container.add_item(discord.ui.TextDisplay(body))
    view.add_item(container)
    return view


_DURATION_RE = re.compile(
    r"(?:(\d+)\s*d(?:ays?)?)?\s*"
    r"(?:(\d+)\s*h(?:ours?)?)?\s*"
    r"(?:(\d+)\s*m(?:in(?:utes?)?)?)?\s*"
    r"(?:(\d+)\s*s(?:ec(?:onds?)?)?)?",
    re.IGNORECASE,
)


def parse_duration(text: str) -> int | None:
    """Parse a human duration string (e.g. ``1d12h``, ``30m``, ``90s``) into seconds.

    Returns ``None`` when the string cannot be parsed.
    """
    m = _DURATION_RE.fullmatch(text.strip())
    if not m or not any(m.groups()):
        return None
    days = int(m.group(1) or 0)
    hours = int(m.group(2) or 0)
    minutes = int(m.group(3) or 0)
    seconds = int(m.group(4) or 0)
    total = days * 86400 + hours * 3600 + minutes * 60 + seconds
    return total if total > 0 else None


def _format_seconds(secs: int) -> str:
    """Pretty-print seconds into ``1d 2h 30m``."""
    parts = []
    if secs >= 86400:
        parts.append(f"{secs // 86400}d")
        secs %= 86400
    if secs >= 3600:
        parts.append(f"{secs // 3600}h")
        secs %= 3600
    if secs >= 60:
        parts.append(f"{secs // 60}m")
        secs %= 60
    if secs > 0 or not parts:
        parts.append(f"{secs}s")
    return " ".join(parts)


# ────────────────── Paginated V2 List ──────────────────


class PaginatedV2ListView(discord.ui.LayoutView):
    """Components V2 paginated list with Prev / Next / Delete buttons."""

    def __init__(self, *, bot, items: list[str], title: str,
                 items_per_page: int = 10, footer: str | None = None,
                 author_id: int, error: bool = False):
        super().__init__(timeout=180)
        self.bot = bot
        self.items = items
        self.title = title
        self.items_per_page = items_per_page
        self.footer = footer
        self.author_id = author_id
        self.error = error
        self.current_page = 0
        self.max_pages = max(1, (len(items) + items_per_page - 1) // items_per_page)
        self._build()

    # ── build ──
    def _build(self):
        # Clear children so we can rebuild
        self.clear_items()

        colour = self.bot.config.ERROR_COLOR if self.error else self.bot.config.EMBED_COLOR
        container = discord.ui.Container(accent_colour=discord.Colour(colour))
        container.add_item(discord.ui.TextDisplay(f"### {self.title}"))
        container.add_item(discord.ui.Separator())

        # Page items
        start = self.current_page * self.items_per_page
        end = start + self.items_per_page
        page_items = self.items[start:end]
        numbered = [f"{start + i + 1}. {item}" for i, item in enumerate(page_items)]
        body = "\n".join(numbered) if numbered else "No items found."
        container.add_item(discord.ui.TextDisplay(body))

        # Footer
        footer_text = f"-# Page {self.current_page + 1}/{self.max_pages}"
        if self.footer:
            footer_text += f" · {self.footer}"
        container.add_item(discord.ui.Separator())
        container.add_item(discord.ui.TextDisplay(footer_text))

        # Buttons
        row = discord.ui.ActionRow()

        btn_prev = discord.ui.Button(label="Previous", style=discord.ButtonStyle.blurple,
                                     custom_id="pv2_prev", disabled=self.current_page == 0)
        btn_prev.callback = self._on_prev
        row.add_item(btn_prev)

        btn_next = discord.ui.Button(label="Next", style=discord.ButtonStyle.blurple,
                                     custom_id="pv2_next", disabled=self.current_page >= self.max_pages - 1)
        btn_next.callback = self._on_next
        row.add_item(btn_next)

        btn_del = discord.ui.Button(label="Delete", style=discord.ButtonStyle.red, custom_id="pv2_del")
        btn_del.callback = self._on_delete
        row.add_item(btn_del)

        container.add_item(row)
        self.add_item(container)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("This is not your list!", ephemeral=True)
            return False
        return True

    async def _on_prev(self, interaction: discord.Interaction):
        self.current_page = max(0, self.current_page - 1)
        self._build()
        await interaction.response.edit_message(view=self)

    async def _on_next(self, interaction: discord.Interaction):
        self.current_page = min(self.max_pages - 1, self.current_page + 1)
        self._build()
        await interaction.response.edit_message(view=self)

    async def _on_delete(self, interaction: discord.Interaction):
        await interaction.message.delete()


# ────────────────── Restart Confirm V2 ──────────────────


class RestartConfirmView(discord.ui.LayoutView):
    def __init__(self, ctx):
        super().__init__(timeout=30)
        self.ctx = ctx
        self.message = None

        container = discord.ui.Container(accent_colour=discord.Colour(ctx.bot.config.EMBED_COLOR))
        container.add_item(discord.ui.TextDisplay("### Restart Confirmation"))
        container.add_item(discord.ui.Separator())
        container.add_item(discord.ui.TextDisplay("Are you sure you want to **restart** the bot?"))

        row = discord.ui.ActionRow()
        btn_yes = discord.ui.Button(label="Yes", style=discord.ButtonStyle.green, custom_id="restart_yes")
        btn_yes.callback = self._confirm
        row.add_item(btn_yes)

        btn_no = discord.ui.Button(label="No", style=discord.ButtonStyle.red, custom_id="restart_no")
        btn_no.callback = self._cancel
        row.add_item(btn_no)

        container.add_item(row)
        self.add_item(container)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("You cannot use this button!", ephemeral=True)
            return False
        return True

    async def _confirm(self, interaction: discord.Interaction):
        view = _owner_view(self.ctx.bot, "Restarting", "Bot is restarting...")
        await interaction.response.send_message(view=view)

        import sys
        await self.ctx.bot.close()
        os.execv(sys.executable, ['python'] + sys.argv)

    async def _cancel(self, interaction: discord.Interaction):
        await interaction.message.delete()

    async def on_timeout(self):
        if self.message:
            try:
                await self.message.edit(content="Restart timed out.", view=None, delete_after=5)
            except:
                pass


# ────────────────── Owner Cog ──────────────────


class Owner(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.noprefix_tasks: dict[int, asyncio.Task] = {}

    async def cog_load(self):
        """Re-schedule any unexpired timed noprefix entries on cog load / reload."""
        now = datetime.datetime.now(datetime.timezone.utc)
        async for doc in self.bot.noprefix_col.find({"expires_at": {"$exists": True}}):
            user_id = doc["user_id"]
            expires_at = doc["expires_at"]
            # Make sure it's timezone-aware
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=datetime.timezone.utc)
            remaining = (expires_at - now).total_seconds()
            if remaining <= 0:
                # Already expired — clean up
                await self.bot.noprefix_col.delete_one({"user_id": user_id})
            else:
                self._schedule_removal(user_id, remaining)

    def cog_unload(self):
        """Cancel all pending removal tasks when the cog unloads."""
        for task in self.noprefix_tasks.values():
            task.cancel()
        self.noprefix_tasks.clear()

    def _schedule_removal(self, user_id: int, delay: float):
        """Schedule auto-removal of a noprefix user after *delay* seconds."""
        async def _remove():
            await asyncio.sleep(delay)
            await self.bot.noprefix_col.delete_one({"user_id": user_id})
            self.noprefix_tasks.pop(user_id, None)

            # DM the user about expiration
            try:
                user = self.bot.get_user(user_id)
                if not user:
                    user = await self.bot.fetch_user(user_id)
                if user:
                    now_ts = int(datetime.datetime.now(datetime.timezone.utc).timestamp())
                    view = discord.ui.LayoutView()
                    container = discord.ui.Container(
                        accent_colour=discord.Colour(self.bot.config.ERROR_COLOR)
                    )
                    container.add_item(discord.ui.TextDisplay("### Noprefix Access Expired"))
                    container.add_item(discord.ui.Separator())

                    # User info with thumbnail avatar
                    section = discord.ui.Section(
                        accessory=discord.ui.Thumbnail(media=user.display_avatar.url)
                    )
                    section.add_item(discord.ui.TextDisplay(
                        f"**User:** {user.mention} (`{user.name}`)"
                        f"\n**User ID:** `{user.id}`"
                        f"\n\n**Status:** Your noprefix access has expired"
                        f"\n**Expired At:** <t:{now_ts}:F>"
                    ))
                    container.add_item(section)
                    container.add_item(discord.ui.Separator())
                    container.add_item(discord.ui.TextDisplay(
                        f"-# You now need to use the bot prefix to run commands"
                    ))

                    view.add_item(container)
                    await user.send(view=view)
            except Exception:
                pass  # DMs may be closed

        # Cancel any existing task for this user
        existing = self.noprefix_tasks.pop(user_id, None)
        if existing:
            existing.cancel()
        self.noprefix_tasks[user_id] = asyncio.create_task(_remove())

    async def cog_check(self, ctx):
        is_main_owner = await self.bot.is_owner(ctx.author)
        is_extra = await self.bot.is_extra_owner(ctx.author.id)
        is_team = await self.bot.is_team_member(ctx.author.id)

        ctx.is_main_owner = is_main_owner
        ctx.is_extra_owner = is_extra
        ctx.is_team_member = is_team

        if not (is_main_owner or is_extra or is_team):
            raise commands.CheckFailure("__SILENT_BLACKLIST__")
        return True

    # ═══════════════════ NOPREFIX ═══════════════════

    @commands.command(name="addnoprefix", aliases=["anp"], hidden=True)
    async def add_noprefix(self, ctx: commands.Context, user: discord.User, duration: str = None):
        """Add a user to noprefix list. Usage: anp <user> [duration]
        Duration examples: 1h, 30m, 2d, 1d12h, 90s
        """
        if await self.bot.is_noprefix(user.id):
            return await ctx.send(
                view=_owner_view(self.bot, "Error", f"**{user.name}** already has noprefix access!", error=True)
            )

        doc = {"user_id": user.id, "added_by": ctx.author.id}
        now_ts = int(datetime.datetime.now(datetime.timezone.utc).timestamp())

        if duration:
            seconds = parse_duration(duration)
            if seconds is None:
                return await ctx.send(
                    view=_owner_view(self.bot, "Invalid Duration",
                                     "Use formats like `1h`, `30m`, `2d`, `1d12h`, `90s`.", error=True)
                )
            expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=seconds)
            doc["expires_at"] = expires_at
            self._schedule_removal(user.id, seconds)
        else:
            expires_at = None

        await self.bot.noprefix_col.insert_one(doc)

        # ── Build rich V2 card ──
        view = discord.ui.LayoutView()
        container = discord.ui.Container(accent_colour=discord.Colour(self.bot.config.EMBED_COLOR))

        # Title
        container.add_item(discord.ui.TextDisplay("### Noprefix Access Granted"))
        container.add_item(discord.ui.Separator())

        # User info with thumbnail avatar
        created_ts = int(user.created_at.timestamp())
        section = discord.ui.Section(
            accessory=discord.ui.Thumbnail(media=user.display_avatar.url)
        )
        section.add_item(discord.ui.TextDisplay(
            f"**User:** {user.mention} (`{user.name}`)"
            f"\n**User ID:** `{user.id}`"
            f"\n**Account Created:** <t:{created_ts}:R>"
        ))
        container.add_item(section)
        container.add_item(discord.ui.Separator())

        # Noprefix details
        if expires_at:
            exp_ts = int(expires_at.timestamp())
            np_details = (
                f"**Type:** Temporary"
                f"\n**Duration:** {_format_seconds(seconds)}"
                f"\n**Expires:** <t:{exp_ts}:F> (<t:{exp_ts}:R>)"
            )
        else:
            np_details = "**Type:** Permanent\n**Expires:** Never"

        np_details += (
            f"\n**Added By:** {ctx.author.mention}"
            f"\n**Granted At:** <t:{now_ts}:F>"
        )
        container.add_item(discord.ui.TextDisplay(np_details))

        container.add_item(discord.ui.Separator())
        container.add_item(discord.ui.TextDisplay(
            f"-# Noprefix allows {user.name} to use bot commands without a prefix"
        ))

        view.add_item(container)
        await ctx.send(view=view)

    @commands.command(name="removenoprefix", aliases=["rnp"], hidden=True)
    async def remove_noprefix(self, ctx: commands.Context, user: discord.User):
        """Remove a user from noprefix list"""
        if not await self.bot.is_noprefix(user.id):
            return await ctx.send(
                view=_owner_view(self.bot, "Error", f"**{user.name}** is not in the noprefix list!", error=True)
            )

        await self.bot.noprefix_col.delete_one({"user_id": user.id})
        # Cancel scheduled task if one exists
        task = self.noprefix_tasks.pop(user.id, None)
        if task:
            task.cancel()

        # Build rich V2 card
        now_ts = int(datetime.datetime.now(datetime.timezone.utc).timestamp())
        view = discord.ui.LayoutView()
        container = discord.ui.Container(accent_colour=discord.Colour(self.bot.config.ERROR_COLOR))

        container.add_item(discord.ui.TextDisplay("### Noprefix Access Revoked"))
        container.add_item(discord.ui.Separator())

        # User info with thumbnail avatar
        created_ts = int(user.created_at.timestamp())
        section = discord.ui.Section(
            accessory=discord.ui.Thumbnail(media=user.display_avatar.url)
        )
        section.add_item(discord.ui.TextDisplay(
            f"**User:** {user.mention} (`{user.name}`)"
            f"\n**User ID:** `{user.id}`"
            f"\n**Account Created:** <t:{created_ts}:R>"
        ))
        container.add_item(section)
        container.add_item(discord.ui.Separator())

        # Removal details
        removal_details = (
            f"**Status:** Noprefix access removed"
            f"\n**Removed By:** {ctx.author.mention}"
            f"\n**Removed At:** <t:{now_ts}:F>"
        )
        container.add_item(discord.ui.TextDisplay(removal_details))

        container.add_item(discord.ui.Separator())
        container.add_item(discord.ui.TextDisplay(
            f"-# {user.name} will now need to use the bot prefix to run commands"
        ))

        view.add_item(container)
        await ctx.send(view=view)

    @commands.group(name="noprefix", aliases=["npfx"], invoke_without_command=True, hidden=True)
    async def noprefix_group(self, ctx: commands.Context):
        """Manage noprefix users"""
        if ctx.invoked_subcommand is None:
            await ctx.invoke(self.noprefix_list)

    @noprefix_group.command(name="add")
    async def noprefix_add_sub(self, ctx: commands.Context, user: discord.User, duration: str = None):
        await ctx.invoke(self.add_noprefix, user=user, duration=duration)

    @noprefix_group.command(name="remove")
    async def noprefix_remove_sub(self, ctx: commands.Context, user: discord.User):
        await ctx.invoke(self.remove_noprefix, user=user)

    @noprefix_group.command(name="list")
    async def noprefix_list_sub(self, ctx: commands.Context):
        await ctx.invoke(self.noprefix_list)

    @commands.command(name="noprefixlist", aliases=["npl"], hidden=True)
    async def noprefix_list(self, ctx: commands.Context):
        """List all users with noprefix access"""
        try:
            cursor = self.bot.noprefix_col.find({})
            users = []
            now = datetime.datetime.now(datetime.timezone.utc)
            async for doc in cursor:
                user_id = doc["user_id"]
                user = self.bot.get_user(user_id)
                if not user:
                    try:
                        user = await self.bot.fetch_user(user_id)
                    except:
                        pass
                name = user.name if user else "Unknown User"

                # Build entry with type and duration info
                expires_at = doc.get("expires_at")
                added_by_id = doc.get("added_by")
                added_by_str = ""
                if added_by_id:
                    adder = self.bot.get_user(added_by_id)
                    added_by_str = f" · by **{adder.name}**" if adder else f" · by `{added_by_id}`"

                if expires_at:
                    if expires_at.tzinfo is None:
                        expires_at = expires_at.replace(tzinfo=datetime.timezone.utc)
                    if expires_at > now:
                        ts = int(expires_at.timestamp())
                        remaining = expires_at - now
                        remaining_str = _format_seconds(int(remaining.total_seconds()))
                        entry = (f"**{name}** (`{user_id}`)\n"
                                 f"-# Temporary · {remaining_str} left · expires <t:{ts}:R>{added_by_str}")
                    else:
                        entry = (f"**{name}** (`{user_id}`)\n"
                                 f"-# ~~Expired~~{added_by_str}")
                else:
                    entry = (f"**{name}** (`{user_id}`)\n"
                             f"-# Permanent{added_by_str}")
                users.append(entry)

            if not users:
                return await ctx.send(
                    view=_owner_view(self.bot, "No Prefix Users", "No users have noprefix access.", error=True)
                )

            list_view = PaginatedV2ListView(
                bot=self.bot, items=users, title="No Prefix Users",
                items_per_page=10, footer=f"Total: {len(users)}",
                author_id=ctx.author.id
            )
            await ctx.send(view=list_view)
        except Exception as e:
            await ctx.send(view=_owner_view(self.bot, "Error", f"An error occurred: {e}", error=True))

    # ═══════════════════ DEBUG ═══════════════════

    @commands.command(name="debug", hidden=True)
    async def debug_cmd(self, ctx: commands.Context):
        """Debug command to check bot state"""
        if not ctx.is_main_owner:
            return

        noprefix_count = await self.bot.noprefix_col.count_documents({})
        body = (f"Bot is responsive.\n"
                f"**Noprefix Count:** {noprefix_count}\n"
                f"**Guilds:** {len(self.bot.guilds)}")
        await ctx.send(view=_owner_view(self.bot, "Debug", body))

    # ═══════════════════ BLACKLIST ═══════════════════

    @commands.command(name="addblacklist", aliases=["abl", "block"], hidden=True)
    async def add_blacklist(self, ctx: commands.Context, user: discord.User):
        """Blacklist a user from passing commands (Main Owner and Extra Owners only)"""
        if ctx.is_team_member and not (ctx.is_main_owner or ctx.is_extra_owner):
            return await ctx.send(
                view=_owner_view(self.bot, "Error", "Team members cannot manage blacklist!", error=True)
            )

        if await self.bot.is_blacklisted(user.id):
            return await ctx.send(
                view=_owner_view(self.bot, "Error", f"**{user.name}** is already blacklisted!", error=True)
            )

        if await self.bot.is_owner(user):
            return await ctx.send(
                view=_owner_view(self.bot, "Error", "You cannot blacklist the owner!", error=True)
            )

        await self.bot.blacklist_col.insert_one({"user_id": user.id})

        # Try to send DM
        try:
            dm_view = _owner_view(self.bot, "You have been blacklisted",
                                  f"You have been blacklisted from using **{self.bot.user.name}**.\n\n"
                                  "You will no longer be able to use any commands until you are unblacklisted.",
                                  error=True)
            await user.send(view=dm_view)
            await ctx.send(view=_owner_view(self.bot, "Blacklisted", f"Blacklisted **{user.name}** and sent them a DM!"))
        except:
            await ctx.send(view=_owner_view(self.bot, "Blacklisted", f"Blacklisted **{user.name}** (couldn't send DM)!"))

    @commands.command(name="removeblacklist", aliases=["rbl", "unblock"], hidden=True)
    async def remove_blacklist(self, ctx: commands.Context, user: discord.User):
        """Remove a user from blacklist (Main Owner and Extra Owners only)"""
        if ctx.is_team_member and not (ctx.is_main_owner or ctx.is_extra_owner):
            return await ctx.send(
                view=_owner_view(self.bot, "Error", "Team members cannot manage blacklist!", error=True)
            )

        if not await self.bot.is_blacklisted(user.id):
            return await ctx.send(
                view=_owner_view(self.bot, "Error", f"**{user.name}** is not blacklisted!", error=True)
            )

        await self.bot.blacklist_col.delete_one({"user_id": user.id})

        # Try to send DM
        try:
            dm_view = _owner_view(self.bot, "You have been unblacklisted",
                                  f"You have been unblacklisted from **{self.bot.user.name}**.\n\n"
                                  "You can now use commands again!",)
            await user.send(view=dm_view)
            await ctx.send(view=_owner_view(self.bot, "Unblocked", f"Unblocked **{user.name}** and sent them a DM!"))
        except:
            await ctx.send(view=_owner_view(self.bot, "Unblocked", f"Unblocked **{user.name}** (couldn't send DM)!"))

    @commands.command(name="blacklistlist", aliases=["bll"], hidden=True)
    async def blacklist_list(self, ctx: commands.Context):
        """List all blacklisted users"""
        cursor = self.bot.blacklist_col.find({})
        users = []
        async for doc in cursor:
            user_id = doc["user_id"]
            user = self.bot.get_user(user_id)
            name = user.name if user else "Unknown User"
            users.append(f"**{name}** (`{user_id}`)")

        if not users:
            return await ctx.send(
                view=_owner_view(self.bot, "Blacklisted Users", "No users are blacklisted.", error=True)
            )

        list_view = PaginatedV2ListView(
            bot=self.bot, items=users, title="Blacklisted Users",
            items_per_page=10, author_id=ctx.author.id, error=True
        )
        await ctx.send(view=list_view)

    # ═══════════════════ RELOAD ═══════════════════

    @commands.command(name="reload", aliases=["rl"], hidden=True)
    async def reload_extension(self, ctx: commands.Context, extension: str = None):
        """Reload one or all extensions"""
        if extension:
            try:
                await self.bot.reload_extension(extension)
                await ctx.send(view=_owner_view(self.bot, "Reloaded", f"Reloaded **{extension}**"))
            except Exception as e:
                await ctx.send(view=_owner_view(self.bot, "Reload Failed", f"Failed to reload `{extension}`: {e}", error=True))
        else:
            extensions = [
                'jishaku',
                'commands.play',
                'commands.queue',
                'commands.control',
                'commands.voice',
                'commands.filters',
                'commands.advanced',
                'commands.search',
                'commands.events',
                'commands.owner',
                'commands.settings',
                'commands.help',
                'commands.afk',
                'commands.moderation',
                'commands.playlist',
                'commands.utility',
                'commands.spotify',
                'commands.customize',
                'commands.badges',
            ]
            failed = []
            for ext in extensions:
                try:
                    await self.bot.reload_extension(ext)
                except Exception as e:
                    failed.append(f"`{ext}`: {e}")

            if failed:
                await ctx.send(view=_owner_view(self.bot, "Reload Errors", "Reloaded with errors:\n" + "\n".join(failed), error=True))
            else:
                await ctx.send(view=_owner_view(self.bot, "Reloaded", "Reloaded all extensions!"))

    # ═══════════════════ SAY ═══════════════════

    @commands.command(name="say", aliases=["echo"], hidden=True)
    async def say(self, ctx: commands.Context, *, message: str):
        """Make the bot say something."""
        await ctx.message.delete()
        await ctx.send(message)

    # ═══════════════════ SERVER LIST ═══════════════════

    @commands.command(name="serverlist", aliases=["servers", "sl"], hidden=True)
    async def server_list(self, ctx: commands.Context):
        """List all servers the bot is in"""
        if ctx.is_team_member and not (ctx.is_main_owner or ctx.is_extra_owner):
            return await ctx.send(
                view=_owner_view(self.bot, "Error", "Team members cannot view server list!", error=True)
            )

        servers = [f"**{g.name}** (`{g.id}`) - {g.member_count} members" for g in self.bot.guilds]

        list_view = PaginatedV2ListView(
            bot=self.bot, items=servers,
            title=f"Server List ({len(self.bot.guilds)})",
            items_per_page=10, author_id=ctx.author.id
        )
        await ctx.send(view=list_view)

    # ═══════════════════ LEAVE SERVER ═══════════════════

    @commands.command(name="leaveserver", aliases=["leaveguild"], hidden=True)
    async def leave_server(self, ctx: commands.Context, guild_id: int = None):
        """Make the bot leave a server"""
        if guild_id:
            guild = self.bot.get_guild(guild_id)
            if not guild:
                return await ctx.send(view=_owner_view(self.bot, "Error", "I am not in that server!", error=True))
        else:
            guild = ctx.guild

        try:
            await guild.leave()
            if guild_id:
                await ctx.send(view=_owner_view(self.bot, "Left Server", f"Left **{guild.name}**"))
        except Exception as e:
            await ctx.send(view=_owner_view(self.bot, "Error", f"Failed to leave: {e}", error=True))

    # ═══════════════════ RESTART ═══════════════════

    @commands.command(name="restart", aliases=["reboot"], hidden=True)
    async def restart_bot(self, ctx: commands.Context):
        """Restart the bot"""
        if not ctx.is_main_owner:
            return await ctx.send(
                view=_owner_view(self.bot, "Error", "Only the main owner can restart the bot!", error=True)
            )

        confirm_view = RestartConfirmView(ctx)
        msg = await ctx.send(view=confirm_view)
        confirm_view.message = msg

    # ═══════════════════ MAINTENANCE ═══════════════════

    @commands.command(name="maintenance", aliases=["maint"], hidden=True)
    async def maintenance_mode(self, ctx: commands.Context):
        """Toggle maintenance mode"""
        current = getattr(self.bot, 'maintenance_mode', False)
        self.bot.maintenance_mode = not current

        if self.bot.maintenance_mode:
            await self.bot.change_presence(
                status=discord.Status.dnd,
                activity=discord.Activity(type=discord.ActivityType.watching, name="🔧 Maintenance Mode")
            )
            await ctx.send(view=_owner_view(self.bot, "Maintenance", "Maintenance mode **ENABLED**\n\nOnly owners can use commands now."))
        else:
            await self.bot.change_presence(
                status=discord.Status.dnd,
                activity=discord.Activity(type=discord.ActivityType.listening, name=",help | ,play")
            )
            await ctx.send(view=_owner_view(self.bot, "Maintenance", "Maintenance mode **DISABLED**\n\nBot is back to normal operation."))

    # ═══════════════════ TEAM MANAGEMENT ═══════════════════

    @commands.command(name="teamadd", aliases=["ta"], hidden=True)
    async def team_add(self, ctx: commands.Context, user: discord.User):
        """Add a user to the team (Main Owner only)"""
        if not ctx.is_main_owner:
            return await ctx.send(
                view=_owner_view(self.bot, "Error", "Only the main owner can manage team members!", error=True)
            )

        if await self.bot.is_team_member(user.id):
            return await ctx.send(
                view=_owner_view(self.bot, "Error", f"**{user.name}** is already a team member!", error=True)
            )

        if await self.bot.is_owner(user):
            return await ctx.send(
                view=_owner_view(self.bot, "Error", "The main owner doesn't need to be added to the team!", error=True)
            )

        await self.bot.team_col.insert_one({"user_id": user.id})
        await ctx.send(view=_owner_view(self.bot, "Team Added",
                                        f"Added **{user.name}** to the team!\n\nThey can now manage noprefix users."))

    @commands.command(name="teamremove", aliases=["tr"], hidden=True)
    async def team_remove(self, ctx: commands.Context, user: discord.User):
        """Remove a user from the team (Main Owner only)"""
        if not ctx.is_main_owner:
            return await ctx.send(
                view=_owner_view(self.bot, "Error", "Only the main owner can manage team members!", error=True)
            )

        if not await self.bot.is_team_member(user.id):
            return await ctx.send(
                view=_owner_view(self.bot, "Error", f"**{user.name}** is not a team member!", error=True)
            )

        await self.bot.team_col.delete_one({"user_id": user.id})
        await ctx.send(view=_owner_view(self.bot, "Team Removed", f"Removed **{user.name}** from the team!"))

    @commands.command(name="teamlist", aliases=["tl"], hidden=True)
    async def team_list(self, ctx: commands.Context):
        """List all team members (Main Owner only)"""
        if not ctx.is_main_owner:
            return await ctx.send(
                view=_owner_view(self.bot, "Error", "Only the main owner can view team members!", error=True)
            )

        cursor = self.bot.team_col.find({})
        users = []
        async for doc in cursor:
            user_id = doc["user_id"]
            user = self.bot.get_user(user_id)
            name = user.name if user else "Unknown User"
            users.append(f"**{name}** (`{user_id}`)")

        if not users:
            return await ctx.send(
                view=_owner_view(self.bot, "Team Members", "No team members found.", error=True)
            )

        list_view = PaginatedV2ListView(
            bot=self.bot, items=users, title="Team Members",
            items_per_page=10, footer="Team members can manage noprefix users",
            author_id=ctx.author.id
        )
        await ctx.send(view=list_view)

    # ═══════════════════ EXTRA OWNER MANAGEMENT ═══════════════════

    @commands.command(name="owneradd", aliases=["oa"], hidden=True)
    async def owner_add(self, ctx: commands.Context, user: discord.User):
        """Add an extra owner (Main Owner only)"""
        if not ctx.is_main_owner:
            return await ctx.send(
                view=_owner_view(self.bot, "Error", "Only the main owner can add extra owners!", error=True)
            )

        if await self.bot.is_extra_owner(user.id):
            return await ctx.send(
                view=_owner_view(self.bot, "Error", f"**{user.name}** is already an extra owner!", error=True)
            )

        if await self.bot.is_owner(user):
            return await ctx.send(
                view=_owner_view(self.bot, "Error", "The main owner doesn't need to be added as an extra owner!", error=True)
            )

        await self.bot.extra_owners_col.insert_one({"user_id": user.id})
        await ctx.send(view=_owner_view(self.bot, "Owner Added",
                                        f"Added **{user.name}** as an extra owner!\n\n"
                                        "They now have full owner access (except eval command)."))

    @commands.command(name="ownerremove", aliases=["or"], hidden=True)
    async def owner_remove(self, ctx: commands.Context, user: discord.User):
        """Remove an extra owner (Main Owner only)"""
        if not ctx.is_main_owner:
            return await ctx.send(
                view=_owner_view(self.bot, "Error", "Only the main owner can remove extra owners!", error=True)
            )

        if not await self.bot.is_extra_owner(user.id):
            return await ctx.send(
                view=_owner_view(self.bot, "Error", f"**{user.name}** is not an extra owner!", error=True)
            )

        await self.bot.extra_owners_col.delete_one({"user_id": user.id})
        await ctx.send(view=_owner_view(self.bot, "Owner Removed", f"Removed **{user.name}** from extra owners!"))

    @commands.command(name="ownerlist", aliases=["ol"], hidden=True)
    async def owner_list(self, ctx: commands.Context):
        """List all extra owners (Main Owner only)"""
        if not ctx.is_main_owner:
            return await ctx.send(
                view=_owner_view(self.bot, "Error", "Only the main owner can view extra owners!", error=True)
            )

        cursor = self.bot.extra_owners_col.find({})
        users = []
        async for doc in cursor:
            user_id = doc["user_id"]
            user = self.bot.get_user(user_id)
            name = user.name if user else "Unknown User"
            users.append(f"**{name}** (`{user_id}`)")

        if not users:
            return await ctx.send(
                view=_owner_view(self.bot, "Extra Owners", "No extra owners found.", error=True)
            )

        list_view = PaginatedV2ListView(
            bot=self.bot, items=users, title="Extra Owners",
            items_per_page=10, footer="Extra owners have full access except eval command",
            author_id=ctx.author.id
        )
        await ctx.send(view=list_view)

    # ═══════════════════ DM ═══════════════════

    @commands.command(name="dm", aliases=["message"], hidden=True)
    async def dm_user(self, ctx: commands.Context, user: discord.User, *, message: str):
        """DM a user through the bot (Main Owner only)"""
        if not ctx.is_main_owner:
            return

        try:
            await ctx.message.delete()
        except:
            pass

        try:
            await user.send(message)
            await ctx.send(view=_owner_view(self.bot, "DM Sent", f"DM sent to **{user.display_name}**!"), delete_after=5)
        except discord.Forbidden:
            await ctx.send(
                view=_owner_view(self.bot, "DM Failed",
                                 f"Could not DM **{user.display_name}**. Their DMs may be closed.", error=True),
                delete_after=5
            )
        except Exception as e:
            await ctx.send(view=_owner_view(self.bot, "DM Failed", f"Failed to send DM: {e}", error=True), delete_after=5)

    # ═══════════════════ BACKUP ═══════════════════

    @commands.command(name="backup", aliases=["bk"], hidden=True)
    async def backup_code(self, ctx: commands.Context):
        """Send the bot's code as a zip file to the main owner's DM (Main Owner Only)"""
        if not ctx.is_main_owner:
            return await ctx.send(
                view=_owner_view(self.bot, "Error", "Only the main owner can request a backup!", error=True)
            )

        status_msg = await ctx.send(view=_owner_view(self.bot, "Backup", "Creating backup... Please wait."))

        try:
            zip_buffer = io.BytesIO()

            excluded_dirs = {
                '__pycache__', '.git', '.vscode', 'venv', 'env', '.gemini',
                'node_modules', '.idea', 'brain', 'artifacts', 'tmp'
            }
            excluded_files = {
                '.env', 'session.lock', 'poetry.lock', 'package-lock.json',
                'error.log', 'lavalink.log'
            }

            base_dir = os.getcwd()

            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                for root, dirs, files in os.walk(base_dir):
                    dirs[:] = [d for d in dirs if d not in excluded_dirs]
                    for file in files:
                        if file in excluded_files or file.endswith('.pyc') or file.endswith('.log'):
                            continue
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, base_dir)
                        zip_file.write(file_path, arcname)

            zip_buffer.seek(0)

            timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            filename = f"bot_backup_{timestamp}.zip"

            try:
                await ctx.author.send(
                    content=f"**Secure Backup Generated**\n{timestamp}",
                    file=discord.File(zip_buffer, filename=filename)
                )
                await status_msg.edit(view=_owner_view(self.bot, "Backup", "Backup sent to your DMs!"))
            except discord.Forbidden:
                await status_msg.edit(
                    view=_owner_view(self.bot, "Error", "Could not DM you! Please open your DMs.", error=True)
                )
            except Exception as e:
                await status_msg.edit(
                    view=_owner_view(self.bot, "Error", f"Failed to send DM: {e}", error=True)
                )

        except Exception as e:
            await status_msg.edit(view=_owner_view(self.bot, "Error", f"Backup failed: {e}", error=True))

    # ═══════════════════ SERVER LINK ═══════════════════

    @commands.command(name="serverlink", aliases=["slink"], hidden=True)
    async def server_link(self, ctx: commands.Context, guild_id: int):
        """Generate an invite link for a server (Main Owner only)"""
        if not ctx.is_main_owner:
            return await ctx.send(
                view=_owner_view(self.bot, "Error", "Only the main owner can use this command!", error=True)
            )

        guild = self.bot.get_guild(guild_id)
        if not guild:
            return await ctx.send(
                view=_owner_view(self.bot, "Error", f"I am not in a server with ID `{guild_id}`!", error=True)
            )

        # Find a channel the bot can create an invite for
        invite_channel = None
        for channel in guild.text_channels:
            perms = channel.permissions_for(guild.me)
            if perms.create_instant_invite:
                invite_channel = channel
                break

        if not invite_channel:
            return await ctx.send(
                view=_owner_view(self.bot, "Error",
                                 f"I don't have permission to create an invite in **{guild.name}**!",
                                 error=True)
            )

        try:
            invite = await invite_channel.create_invite(max_age=0, max_uses=1, unique=True,
                                                         reason=f"Invite generated by bot owner ({ctx.author})")

            view = discord.ui.LayoutView()
            container = discord.ui.Container(accent_colour=discord.Colour(self.bot.config.EMBED_COLOR))
            container.add_item(discord.ui.TextDisplay("### Server Invite Generated"))
            container.add_item(discord.ui.Separator())

            section = discord.ui.Section(
                accessory=discord.ui.Thumbnail(media=guild.icon.url if guild.icon else self.bot.user.display_avatar.url)
            )
            section.add_item(discord.ui.TextDisplay(
                f"**Server:** {guild.name}\n"
                f"**Server ID:** `{guild.id}`\n"
                f"**Members:** {guild.member_count}\n"
                f"**Owner:** {guild.owner}"
            ))
            container.add_item(section)
            container.add_item(discord.ui.Separator())
            container.add_item(discord.ui.TextDisplay(f"**Invite Link:** {invite.url}"))
            container.add_item(discord.ui.Separator())
            container.add_item(discord.ui.TextDisplay("-# This invite is single-use and does not expire"))
            view.add_item(container)

            await ctx.send(view=view)

        except discord.Forbidden:
            await ctx.send(
                view=_owner_view(self.bot, "Error",
                                 f"I don't have permission to create an invite in **{guild.name}**!",
                                 error=True)
            )
        except Exception as e:
            await ctx.send(
                view=_owner_view(self.bot, "Error", f"Failed to generate invite: {e}", error=True)
            )


async def setup(bot):
    await bot.add_cog(Owner(bot))
