import discord
from discord.ext import commands, tasks
import random
import re
import datetime
import time
from config import Config
from utils.ratelimit import giveaway_cooldown
from utils.embeds import create_error_embed


# ── Unicode font helpers ──────────────────────────────────────
_BOLD_SERIF = str.maketrans(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789",
    "𝐀𝐁𝐂𝐃𝐄𝐅𝐆𝐇𝐈𝐉𝐊𝐋𝐌𝐍𝐎𝐏𝐐𝐑𝐒𝐓𝐔𝐕𝐖𝐗𝐘𝐙𝐚𝐛𝐜𝐝𝐞𝐟𝐠𝐡𝐢𝐣𝐤𝐥𝐦𝐧𝐨𝐩𝐪𝐫𝐬𝐭𝐮𝐯𝐰𝐱𝐲𝐳𝟎𝟏𝟐𝟑𝟒𝟓𝟔𝟕𝟖𝟗",
)
_BOLD_SANS = str.maketrans(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789",
    "𝗔𝗕𝗖𝗗𝗘𝗙𝗚𝗛𝗜𝗝𝗞𝗟𝗠𝗡𝗢𝗣𝗤𝗥𝗦𝗧𝗨𝗩𝗪𝗫𝗬𝗭𝗮𝗯𝗰𝗱𝗲𝗳𝗴𝗵𝗶𝗷𝗸𝗹𝗺𝗻𝗼𝗽𝗾𝗿𝘀𝘁𝘂𝘃𝘄𝘅𝘆𝘇𝟬𝟭𝟮𝟯𝟰𝟱𝟲𝟳𝟴𝟵",
)
_ITALIC_SERIF = str.maketrans(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz",
    "𝐴𝐵𝐶𝐷𝐸𝐹𝐺𝐻𝐼𝐽𝐾𝐿𝑀𝑁𝑂𝑃𝑄𝑅𝑆𝑇𝑈𝑉𝑊𝑋𝑌𝑍𝑎𝑏𝑐𝑑𝑒𝑓𝑔ℎ𝑖𝑗𝑘𝑙𝑚𝑛𝑜𝑝𝑞𝑟𝑠𝑡𝑢𝑣𝑤𝑥𝑦𝑧",
)

def bold_serif(text: str) -> str:
    return text.translate(_BOLD_SERIF)

def bold_sans(text: str) -> str:
    return text.translate(_BOLD_SANS)

def italic_serif(text: str) -> str:
    return text.translate(_ITALIC_SERIF)


# ── Time parsing ──────────────────────────────────────────────
_TIME_RE = re.compile(r"(\d+)\s*([smhdw])", re.IGNORECASE)

_UNIT_SECONDS = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}


def parse_time(text: str) -> int | None:
    """Parse a human time string like '1d12h30m' into total seconds. Returns None on failure."""
    matches = _TIME_RE.findall(text)
    if not matches:
        return None
    total = 0
    for amount, unit in matches:
        total += int(amount) * _UNIT_SECONDS[unit.lower()]
    return total


def format_relative_time(seconds: int) -> str:
    """Format seconds into a human-readable string like '1d 12h 30m'."""
    parts = []
    if seconds >= 86400:
        d = seconds // 86400
        seconds %= 86400
        parts.append(f"{d}d")
    if seconds >= 3600:
        h = seconds // 3600
        seconds %= 3600
        parts.append(f"{h}h")
    if seconds >= 60:
        m = seconds // 60
        seconds %= 60
        parts.append(f"{m}m")
    if seconds > 0 or not parts:
        parts.append(f"{seconds}s")
    return " ".join(parts)


# ── Emojis ────────────────────────────────────────────────────
EMOJI_GIVEAWAY = "<:Giveaway:1479481613392937074>"
EMOJI_JOIN = "<:giveaways:1479481944323526777>"
EMOJI_USERS = "<:users:1479482342257987705>"


# ── Helper to build a simple response view ───────────────────
def _gw_view(bot, title: str, body: str, *, error: bool = False) -> discord.ui.LayoutView:
    view = discord.ui.LayoutView()
    colour = discord.Colour(Config.ERROR_COLOR if error else Config.SUCCESS_COLOR)
    container = discord.ui.Container(accent_colour=colour)
    container.add_item(discord.ui.TextDisplay(f"### {title}"))
    container.add_item(discord.ui.Separator())
    container.add_item(discord.ui.TextDisplay(body))
    view.add_item(container)
    return view


# ── Build the giveaway embed view ────────────────────────────
def build_giveaway_view(
    *,
    prize: str,
    winners_count: int,
    end_time: datetime.datetime,
    host_id: int,
    participant_count: int,
    ended: bool = False,
    winner_ids: list[int] | None = None,
) -> discord.ui.LayoutView:
    """Build the Components V2 giveaway message."""

    view = discord.ui.LayoutView(timeout=None)
    colour = discord.Colour(Config.EMBED_COLOR) if not ended else discord.Colour(0x99aab5)
    container = discord.ui.Container(accent_colour=colour)

    # Header
    container.add_item(discord.ui.TextDisplay(
        f"### {bold_serif('GIVEAWAY')}"
    ))

    container.add_item(discord.ui.Separator())

    # Prize
    container.add_item(discord.ui.TextDisplay(
        f"{bold_sans('Prize')}: **{prize}**"
    ))

    # Info block
    end_ts = int(end_time.timestamp())
    info_lines = (
        f"{bold_sans('Hosted by')}: <@{host_id}>\n"
        f"{bold_sans('Winners')}: **{winners_count}**\n"
        f"{bold_sans('Ends')}: <t:{end_ts}:R> (<t:{end_ts}:f>)"
    )
    container.add_item(discord.ui.TextDisplay(info_lines))

    container.add_item(discord.ui.Separator())

    # Status / participants
    if ended:
        if winner_ids:
            winner_mentions = ", ".join(f"<@{uid}>" for uid in winner_ids)
            container.add_item(discord.ui.TextDisplay(
                f"{bold_serif('ENDED')}  —  {bold_sans('Winners')}: {winner_mentions}"
            ))
        elif participant_count == 0:
            container.add_item(discord.ui.TextDisplay(
                f"{bold_serif('ENDED')}  —  {italic_serif('No one joined the giveaway')}"
            ))
        else:
            container.add_item(discord.ui.TextDisplay(
                f"{bold_serif('ENDED')}  —  {italic_serif('Not enough valid participants')}"
            ))
    else:
        container.add_item(discord.ui.TextDisplay(
            f"{EMOJI_JOIN}  {bold_serif(str(participant_count))} {bold_sans('Participants')}"
        ))

    container.add_item(discord.ui.Separator())

    # Buttons
    btn_row = discord.ui.ActionRow()
    join_btn = discord.ui.Button(
        label="Join Giveaway" if not ended else "Giveaway Ended",
        style=discord.ButtonStyle.success if not ended else discord.ButtonStyle.secondary,
        custom_id="giveaway_join",
        emoji=EMOJI_JOIN,
        disabled=ended,
    )
    btn_row.add_item(join_btn)

    view_btn = discord.ui.Button(
        label="View Participants",
        style=discord.ButtonStyle.secondary,
        custom_id="giveaway_view",
        emoji=EMOJI_USERS,
    )
    btn_row.add_item(view_btn)

    container.add_item(btn_row)
    view.add_item(container)
    return view


# ── Leave confirmation view (ephemeral) ──────────────────────
class LeaveConfirmView(discord.ui.View):
    """Ephemeral confirmation view when an already-joined user clicks Join again."""

    def __init__(self, bot, message_id: int, prize: str):
        super().__init__(timeout=60)
        self.bot = bot
        self.gw_message_id = message_id
        self.prize = prize

    @discord.ui.button(
        label="Leave Giveaway",
        style=discord.ButtonStyle.danger,
        custom_id="giveaway_leave_confirm",
        emoji=EMOJI_JOIN,
    )
    async def leave_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        col = self.bot.giveaways_col
        data = await col.find_one({"message_id": self.gw_message_id})

        if not data:
            return await interaction.response.edit_message(
                content=f"{Config.EMOJI_CROSS} This giveaway no longer exists.",
                view=None,
            )

        user_id = interaction.user.id
        participants: list = data.get("participants", [])

        if user_id not in participants:
            return await interaction.response.edit_message(
                content=f"{Config.EMOJI_CROSS} You are not in this giveaway.",
                view=None,
            )

        # Remove the user
        await col.update_one(
            {"message_id": self.gw_message_id},
            {"$pull": {"participants": user_id}},
        )
        participants.remove(user_id)

        await interaction.response.edit_message(
            content=f"{Config.EMOJI_TICK} You have left the giveaway for **{self.prize}**.",
            view=None,
        )

        # Update the giveaway message participant count
        try:
            gw_channel = interaction.channel
            if gw_channel:
                gw_msg = await gw_channel.fetch_message(self.gw_message_id)
                new_view = build_giveaway_view(
                    prize=data["prize"],
                    winners_count=data["winners_count"],
                    end_time=data["end_time"],
                    host_id=data["host_id"],
                    participant_count=len(participants),
                )
                await gw_msg.edit(view=new_view)
        except discord.HTTPException:
            pass


# ── Cog ───────────────────────────────────────────────────────
class Giveaway(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Rate limit protection: debounce message edits (one edit per 5s per giveaway)
        self._edit_cooldowns: dict[int, float] = {}  # message_id -> last edit timestamp
        self._pending_edits: set[int] = set()  # message_ids with a scheduled edit
        # Per-user join cooldown (3s)
        self._user_cooldowns: dict[int, float] = {}  # user_id -> last join timestamp

    async def cog_load(self):
        # Start the auto-end checker
        self.check_giveaways.start()

    async def cog_unload(self):
        self.check_giveaways.cancel()

    async def _schedule_edit(self, message: discord.Message, data: dict, participant_count: int):
        """Debounce giveaway message edits — at most once per 5 seconds."""
        import asyncio
        msg_id = message.id
        now = time.time()
        last_edit = self._edit_cooldowns.get(msg_id, 0)
        cooldown_remaining = 5 - (now - last_edit)

        if cooldown_remaining > 0:
            # Already edited recently — schedule a delayed update if not already pending
            if msg_id in self._pending_edits:
                return  # An edit is already scheduled
            self._pending_edits.add(msg_id)
            await asyncio.sleep(cooldown_remaining)
            self._pending_edits.discard(msg_id)

            # Re-fetch the latest participant count from DB
            fresh = await self.bot.giveaways_col.find_one({"message_id": msg_id})
            if not fresh or fresh.get("ended"):
                return
            participant_count = len(fresh.get("participants", []))
            data = fresh

        # Perform the edit
        self._edit_cooldowns[msg_id] = time.time()
        new_view = build_giveaway_view(
            prize=data["prize"],
            winners_count=data["winners_count"],
            end_time=data["end_time"],
            host_id=data["host_id"],
            participant_count=participant_count,
        )
        try:
            await message.edit(view=new_view)
        except discord.HTTPException:
            pass

    # ── Button interaction handler (works with LayoutView) ────
    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.type != discord.InteractionType.component:
            return

        custom_id = interaction.data.get("custom_id", "")

        if custom_id == "giveaway_join":
            await self._handle_join(interaction)
        elif custom_id == "giveaway_view":
            await self._handle_view(interaction)

    async def _handle_join(self, interaction: discord.Interaction):
        """Handle the Join Giveaway button click."""
        # Per-user cooldown (3s)
        now = time.time()
        user_id = interaction.user.id
        last_use = self._user_cooldowns.get(user_id, 0)
        if (now - last_use) < 3:
            return await interaction.response.send_message(
                f"{Config.EMOJI_CROSS} Slow down! Try again in a few seconds.",
                ephemeral=True,
            )
        self._user_cooldowns[user_id] = now

        col = self.bot.giveaways_col
        data = await col.find_one({"message_id": interaction.message.id})

        if not data:
            return await interaction.response.send_message(
                f"{Config.EMOJI_CROSS} This giveaway no longer exists.", ephemeral=True,
            )

        if data.get("ended"):
            return await interaction.response.send_message(
                f"{Config.EMOJI_CROSS} This giveaway has already ended!", ephemeral=True,
            )

        participants: list = data.get("participants", [])

        if user_id in participants:
            # Already joined — show confirmation with Leave button
            confirm_view = LeaveConfirmView(self.bot, interaction.message.id, data["prize"])
            await interaction.response.send_message(
                f"You've already participated in the giveaway for **{data['prize']}**.\nDo you want to leave?",
                view=confirm_view,
                ephemeral=True,
            )
        else:
            # Join
            await col.update_one(
                {"message_id": interaction.message.id},
                {"$addToSet": {"participants": user_id}},
            )
            participants.append(user_id)
            await interaction.response.send_message(
                f"{Config.EMOJI_TICK} You have joined the giveaway for **{data['prize']}**! Good luck!",
                ephemeral=True,
            )

            # Debounced message edit for participant count
            self.bot.loop.create_task(
                self._schedule_edit(interaction.message, data, len(participants))
            )

    async def _handle_view(self, interaction: discord.Interaction):
        """Handle the View Participants button click."""
        # Per-user cooldown (3s)
        now = time.time()
        user_id = interaction.user.id
        view_key = f"view_{user_id}"
        last_use = self._user_cooldowns.get(view_key, 0)
        if (now - last_use) < 3:
            return await interaction.response.send_message(
                f"{Config.EMOJI_CROSS} Slow down! Try again in a few seconds.",
                ephemeral=True,
            )
        self._user_cooldowns[view_key] = now

        col = self.bot.giveaways_col
        data = await col.find_one({"message_id": interaction.message.id})

        if not data:
            return await interaction.response.send_message(
                f"{Config.EMOJI_CROSS} This giveaway no longer exists.", ephemeral=True,
            )

        participants: list = data.get("participants", [])
        count = len(participants)

        if count == 0:
            return await interaction.response.send_message(
                f"{EMOJI_USERS}  {bold_sans('Participants')} — **0**\n\n"
                f"{italic_serif('No one has joined yet. Be the first!')}",
                ephemeral=True,
            )

        # Show up to 30 participants
        display = participants[:30]
        lines = [f"<@{uid}>" for uid in display]
        text = "\n".join(lines)
        if count > 30:
            text += f"\n... and **{count - 30}** more"

        await interaction.response.send_message(
            f"{EMOJI_USERS}  {bold_sans('Participants')} — **{count}**\n\n{text}",
            ephemeral=True,
        )

    # ── Background task: auto-end expired giveaways ───────────
    @tasks.loop(seconds=15)
    async def check_giveaways(self):
        now = datetime.datetime.now(datetime.timezone.utc)
        col = self.bot.giveaways_col

        async for gw in col.find({"ended": False}):
            end_time = gw["end_time"]
            # Ensure timezone-aware
            if end_time.tzinfo is None:
                end_time = end_time.replace(tzinfo=datetime.timezone.utc)

            if now >= end_time:
                await self._end_giveaway(gw)

    @check_giveaways.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()

    # ── Core: end a giveaway and pick winners ─────────────────
    async def _end_giveaway(self, data: dict) -> list[int]:
        col = self.bot.giveaways_col
        guild = self.bot.get_guild(data["guild_id"])
        if not guild:
            await col.update_one({"_id": data["_id"]}, {"$set": {"ended": True}})
            return []

        channel = guild.get_channel(data["channel_id"])
        if not channel:
            await col.update_one({"_id": data["_id"]}, {"$set": {"ended": True}})
            return []

        participants = data.get("participants", [])
        winners_count = data.get("winners_count", 1)

        # Filter to members still in the server
        valid = []
        for uid in participants:
            member = guild.get_member(uid)
            if member:
                valid.append(uid)

        # Pick winners
        winner_ids = random.sample(valid, min(winners_count, len(valid))) if valid else []

        # Update database
        await col.update_one(
            {"_id": data["_id"]},
            {"$set": {"ended": True, "winner_ids": winner_ids}},
        )

        # Update the original message
        end_time = data["end_time"]
        if end_time.tzinfo is None:
            end_time = end_time.replace(tzinfo=datetime.timezone.utc)

        ended_view = build_giveaway_view(
            prize=data["prize"],
            winners_count=winners_count,
            end_time=end_time,
            host_id=data["host_id"],
            participant_count=len(participants),
            ended=True,
            winner_ids=winner_ids,
        )

        try:
            msg = await channel.fetch_message(data["message_id"])
            await msg.edit(view=ended_view)
        except discord.HTTPException:
            pass

        # Send congratulations message
        if winner_ids:
            winner_mentions = ", ".join(f"<@{uid}>" for uid in winner_ids)
            congrats_view = discord.ui.LayoutView()
            congrats_container = discord.ui.Container(accent_colour=discord.Colour(0x57f287))
            congrats_container.add_item(discord.ui.TextDisplay(
                f"### {bold_serif('GIVEAWAY ENDED')}\n\n"
                f"{bold_sans('Prize')}: **{data['prize']}**\n"
                f"{bold_sans('Winners')}: {winner_mentions}\n\n"
                f"-# Congratulations! Contact <@{data['host_id']}> to claim your prize."
            ))
            congrats_container.add_item(discord.ui.Separator())
            # Jump to giveaway message
            jump_row = discord.ui.ActionRow()
            jump_row.add_item(discord.ui.Button(
                label="Jump to Giveaway",
                style=discord.ButtonStyle.link,
                url=f"https://discord.com/channels/{data['guild_id']}/{data['channel_id']}/{data['message_id']}",
            ))
            congrats_container.add_item(jump_row)
            congrats_view.add_item(congrats_container)
            try:
                await channel.send(view=congrats_view)
            except discord.HTTPException:
                pass
        else:
            try:
                view = _gw_view(
                    self.bot,
                    f"{bold_serif('GIVEAWAY ENDED')}",
                    f"No valid participants for **{data['prize']}**.\nNo winners could be chosen.",
                    error=True,
                )
                await channel.send(view=view)
            except discord.HTTPException:
                pass

        return winner_ids

    # ── Commands ──────────────────────────────────────────────

    @commands.group(name="giveaway", aliases=["g", "gw"], invoke_without_command=True)
    @giveaway_cooldown()
    async def giveaway(self, ctx: commands.Context):
        """Giveaway management commands"""
        view = _gw_view(
            self.bot,
            f"{EMOJI_GIVEAWAY} Giveaway Commands",
            f"**{ctx.prefix}giveaway start `<time>` `<winners>` `<prize>`** — Create a giveaway\n"
            f"**{ctx.prefix}giveaway end `<message_id>`** — End a giveaway early\n"
            f"**{ctx.prefix}giveaway reroll `<message_id>`** — Reroll winners\n"
            f"**{ctx.prefix}giveaway cancel `<message_id>`** — Cancel a giveaway\n"
            f"**{ctx.prefix}giveaway list** — View active giveaways\n\n"
            f"-# Time format: `1m`, `1h`, `1d`, `2d12h`, `1w`",
        )
        await ctx.send(view=view)

    # ── giveaway start ────────────────────────────────────────
    @giveaway.command(name="start", aliases=["create"])
    @giveaway_cooldown()
    @commands.has_permissions(manage_guild=True)
    async def gw_start(self, ctx: commands.Context, time_str: str, winners: int, *, prize: str):
        """Create a giveaway"""
        # Parse time
        seconds = parse_time(time_str)
        if seconds is None or seconds < 10:
            view = _gw_view(self.bot, "Invalid Time", "Please provide a valid duration (minimum 10 seconds).\nExamples: `30s`, `5m`, `1h`, `1d`", error=True)
            return await ctx.send(view=view)

        if seconds > 2592000:  # 30 days
            view = _gw_view(self.bot, "Too Long", "Giveaway duration cannot exceed **30 days**!", error=True)
            return await ctx.send(view=view)

        if winners < 1 or winners > 20:
            view = _gw_view(self.bot, "Invalid Winners", "Winner count must be between **1** and **20**!", error=True)
            return await ctx.send(view=view)

        if len(prize) > 200:
            view = _gw_view(self.bot, "Prize Too Long", "Prize description cannot exceed **200** characters!", error=True)
            return await ctx.send(view=view)

        # Calculate end time
        now = datetime.datetime.now(datetime.timezone.utc)
        end_time = now + datetime.timedelta(seconds=seconds)

        # Build and send the giveaway message
        gw_msg_view = build_giveaway_view(
            prize=prize,
            winners_count=winners,
            end_time=end_time,
            host_id=ctx.author.id,
            participant_count=0,
        )

        gw_msg = await ctx.send(view=gw_msg_view)

        # Store in database
        await self.bot.giveaways_col.insert_one({
            "guild_id": ctx.guild.id,
            "channel_id": ctx.channel.id,
            "message_id": gw_msg.id,
            "host_id": ctx.author.id,
            "prize": prize,
            "winners_count": winners,
            "end_time": end_time,
            "participants": [],
            "ended": False,
            "winner_ids": [],
        })

        # Confirmation (delete original command message for cleanliness)
        try:
            await ctx.message.delete()
        except discord.HTTPException:
            pass

    # Standalone aliases
    @commands.command(name="gcreate", aliases=["gstart"], hidden=True)
    @giveaway_cooldown()
    @commands.has_permissions(manage_guild=True)
    async def gcreate_alias(self, ctx: commands.Context, time_str: str, winners: int, *, prize: str):
        """Create a giveaway (alias)"""
        await self.gw_start(ctx, time_str, winners, prize=prize)

    # ── giveaway end ──────────────────────────────────────────
    @giveaway.command(name="end")
    @giveaway_cooldown()
    @commands.has_permissions(manage_guild=True)
    async def gw_end(self, ctx: commands.Context, message_id: int):
        """End a giveaway early and pick winners"""
        data = await self.bot.giveaways_col.find_one({
            "guild_id": ctx.guild.id,
            "message_id": message_id,
        })
        # Fallback: try matching by message_id alone (in case of cluster/shard mismatch)
        if not data:
            data = await self.bot.giveaways_col.find_one({"message_id": message_id})

        if not data:
            view = _gw_view(self.bot, "Not Found", "No giveaway found with that message ID in this server.", error=True)
            return await ctx.send(view=view)

        if data.get("ended"):
            view = _gw_view(self.bot, "Already Ended", "That giveaway has already ended!", error=True)
            return await ctx.send(view=view)

        winner_ids = await self._end_giveaway(data)
        count = len(winner_ids)
        view = _gw_view(
            self.bot,
            f"{EMOJI_GIVEAWAY} Giveaway Ended",
            f"The giveaway for **{data['prize']}** has been ended.\n**{count}** winner(s) selected.",
        )
        await ctx.send(view=view)

    @commands.command(name="gend", hidden=True)
    @giveaway_cooldown()
    @commands.has_permissions(manage_guild=True)
    async def gend_alias(self, ctx: commands.Context, message_id: int):
        """End a giveaway early (alias)"""
        await self.gw_end(ctx, message_id)

    # ── giveaway reroll ───────────────────────────────────────
    @giveaway.command(name="reroll")
    @giveaway_cooldown()
    @commands.has_permissions(manage_guild=True)
    async def gw_reroll(self, ctx: commands.Context, message_id: int):
        """Reroll new winners for an ended giveaway"""
        data = await self.bot.giveaways_col.find_one({
            "guild_id": ctx.guild.id,
            "message_id": message_id,
        })
        # Fallback: try matching by message_id alone (in case of cluster/shard mismatch)
        if not data:
            data = await self.bot.giveaways_col.find_one({"message_id": message_id})

        if not data:
            view = _gw_view(self.bot, "Not Found", "No giveaway found with that message ID in this server.", error=True)
            return await ctx.send(view=view)

        if not data.get("ended"):
            view = _gw_view(self.bot, "Still Active", "That giveaway is still active! Use `giveaway end` first.", error=True)
            return await ctx.send(view=view)

        participants = data.get("participants", [])
        winners_count = data.get("winners_count", 1)

        # Filter to current server members
        guild = ctx.guild
        valid = [uid for uid in participants if guild.get_member(uid)]

        if not valid:
            view = _gw_view(self.bot, "No Participants", "There are no valid participants to reroll!", error=True)
            return await ctx.send(view=view)

        new_winners = random.sample(valid, min(winners_count, len(valid)))

        # Update database
        await self.bot.giveaways_col.update_one(
            {"_id": data["_id"]},
            {"$set": {"winner_ids": new_winners}},
        )

        # Update original message
        end_time = data["end_time"]
        if end_time.tzinfo is None:
            end_time = end_time.replace(tzinfo=datetime.timezone.utc)

        ended_view = build_giveaway_view(
            prize=data["prize"],
            winners_count=winners_count,
            end_time=end_time,
            host_id=data["host_id"],
            participant_count=len(participants),
            ended=True,
            winner_ids=new_winners,
        )
        try:
            channel = ctx.guild.get_channel(data["channel_id"])
            if channel:
                msg = await channel.fetch_message(data["message_id"])
                await msg.edit(view=ended_view)
        except discord.HTTPException:
            pass

        # Announce new winners
        winner_mentions = ", ".join(f"<@{uid}>" for uid in new_winners)
        view = _gw_view(
            self.bot,
            f"Rerolled!",
            f"New winner(s) for **{data['prize']}**: {winner_mentions}\n\n"
            f"-# Congratulations! Contact <@{data['host_id']}> to claim your prize.",
        )
        await ctx.send(view=view)

    @commands.command(name="greroll", hidden=True)
    @giveaway_cooldown()
    @commands.has_permissions(manage_guild=True)
    async def greroll_alias(self, ctx: commands.Context, message_id: int):
        """Reroll winners (alias)"""
        await self.gw_reroll(ctx, message_id)

    # ── giveaway cancel ───────────────────────────────────────
    @giveaway.command(name="cancel")
    @giveaway_cooldown()
    @commands.has_permissions(manage_guild=True)
    async def gw_cancel(self, ctx: commands.Context, message_id: int):
        """Cancel an active giveaway without picking winners"""
        data = await self.bot.giveaways_col.find_one({
            "guild_id": ctx.guild.id,
            "message_id": message_id,
        })
        # Fallback: try matching by message_id alone (in case of cluster/shard mismatch)
        if not data:
            data = await self.bot.giveaways_col.find_one({"message_id": message_id})

        if not data:
            view = _gw_view(self.bot, "Not Found", "No giveaway found with that message ID in this server.", error=True)
            return await ctx.send(view=view)

        if data.get("ended"):
            view = _gw_view(self.bot, "Already Ended", "That giveaway has already ended and cannot be cancelled.", error=True)
            return await ctx.send(view=view)

        # Mark as ended with no winners
        await self.bot.giveaways_col.update_one(
            {"_id": data["_id"]},
            {"$set": {"ended": True, "winner_ids": []}},
        )

        # Update original message to show cancelled state
        end_time = data["end_time"]
        if end_time.tzinfo is None:
            end_time = end_time.replace(tzinfo=datetime.timezone.utc)

        cancelled_view = discord.ui.LayoutView(timeout=None)
        container = discord.ui.Container(accent_colour=discord.Colour(Config.ERROR_COLOR))
        container.add_item(discord.ui.TextDisplay(
            f"### {bold_serif('GIVEAWAY CANCELLED')}"
        ))
        container.add_item(discord.ui.Separator())
        container.add_item(discord.ui.TextDisplay(
            f"{bold_sans('Prize')}: **{data['prize']}**\n"
            f"{bold_sans('Cancelled by')}: {ctx.author.mention}\n\n"
            f"-# This giveaway was cancelled. No winners were selected."
        ))
        container.add_item(discord.ui.Separator())
        # Disabled buttons
        btn_row = discord.ui.ActionRow()
        btn_row.add_item(discord.ui.Button(
            label="Giveaway Cancelled",
            style=discord.ButtonStyle.danger,
            custom_id="giveaway_join",
            emoji=EMOJI_JOIN,
            disabled=True,
        ))
        btn_row.add_item(discord.ui.Button(
            label="View Participants",
            style=discord.ButtonStyle.secondary,
            custom_id="giveaway_view",
            emoji=EMOJI_USERS,
            disabled=True,
        ))
        container.add_item(btn_row)
        cancelled_view.add_item(container)

        try:
            channel = ctx.guild.get_channel(data["channel_id"])
            if channel:
                msg = await channel.fetch_message(data["message_id"])
                await msg.edit(view=cancelled_view)
        except discord.HTTPException:
            pass

        view = _gw_view(
            self.bot,
            f"{EMOJI_GIVEAWAY} Giveaway Cancelled",
            f"The giveaway for **{data['prize']}** has been cancelled.",
        )
        await ctx.send(view=view)

    @commands.command(name="gcancel", hidden=True)
    @giveaway_cooldown()
    @commands.has_permissions(manage_guild=True)
    async def gcancel_alias(self, ctx: commands.Context, message_id: int):
        """Cancel a giveaway (alias)"""
        await self.gw_cancel(ctx, message_id)

    # ── giveaway list ─────────────────────────────────────────
    @giveaway.command(name="list")
    @giveaway_cooldown()
    async def gw_list(self, ctx: commands.Context):
        """Show all active giveaways in this server"""
        col = self.bot.giveaways_col
        active = []
        async for gw in col.find({"guild_id": ctx.guild.id, "ended": False}):
            active.append(gw)

        if not active:
            view = _gw_view(
                self.bot,
                f"{EMOJI_GIVEAWAY} Active Giveaways",
                f"{italic_serif('No active giveaways in this server.')}\n\n"
                f"Create one with `{ctx.prefix}giveaway start <time> <winners> <prize>`",
            )
            return await ctx.send(view=view)

        lines = []
        for i, gw in enumerate(active[:10], 1):
            end_ts = int(gw["end_time"].timestamp())
            pcount = len(gw.get("participants", []))
            lines.append(
                f"**{i}.** {gw['prize']}\n"
                f"   {EMOJI_JOIN} {pcount} participants · Ends <t:{end_ts}:R>\n"
                f"   {bold_sans('ID')}: `{gw['message_id']}`"
            )

        text = "\n\n".join(lines)
        if len(active) > 10:
            text += f"\n\n-# ... and {len(active) - 10} more"

        view = _gw_view(
            self.bot,
            f"{EMOJI_GIVEAWAY} Active Giveaways ({len(active)})",
            text,
        )
        await ctx.send(view=view)

    @commands.command(name="glist", hidden=True)
    @giveaway_cooldown()
    async def glist_alias(self, ctx: commands.Context):
        """List active giveaways (alias)"""
        await self.gw_list(ctx)


async def setup(bot):
    await bot.add_cog(Giveaway(bot))
