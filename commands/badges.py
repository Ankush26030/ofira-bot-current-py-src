import discord
from discord.ext import commands
import time
import asyncio
from utils.embeds import create_success_embed, create_error_embed
from utils.ratelimit import utility_cooldown


# ─── Dropdown Views ───────────────────────────────────────────────

class BadgeSelectView(discord.ui.View):
    """Dropdown to select a badge from a list."""
    def __init__(self, badges: list, author_id: int, placeholder: str = "Select a badge..."):
        super().__init__(timeout=60)
        self.selected = None
        self.author_id = author_id

        options = []
        for b in badges[:25]:  # Discord max 25 options
            label = b["name"]
            emoji_str = b.get("emoji")
            # Try to parse custom emoji; fall back to None if invalid
            try:
                emoji = discord.PartialEmoji.from_str(emoji_str) if emoji_str else None
            except Exception:
                emoji = None
            options.append(discord.SelectOption(label=label, value=label, emoji=emoji))

        select = discord.ui.Select(placeholder=placeholder, options=options, min_values=1, max_values=1)
        select.callback = self._callback
        self.add_item(select)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("This menu is not for you!", ephemeral=True)
            return False
        return True

    async def _callback(self, interaction: discord.Interaction):
        self.selected = interaction.data["values"][0]
        await interaction.response.defer()
        self.stop()

    async def on_timeout(self):
        self.selected = None
        self.stop()


# ─── Bio Edit Modal ──────────────────────────────────────────────

class BioModal(discord.ui.Modal, title="Edit Bio"):
    bio_input = discord.ui.TextInput(
        label="Your Bio",
        placeholder="Tell us about yourself...",
        style=discord.TextStyle.paragraph,
        max_length=70,
        required=False,
    )

    def __init__(self, profiles_col, current_bio: str = ""):
        super().__init__()
        self.profiles_col = profiles_col
        self.bio_input.default = current_bio

    async def on_submit(self, interaction: discord.Interaction):
        bio = self.bio_input.value.strip()
        await self.profiles_col.update_one(
            {"user_id": interaction.user.id},
            {"$set": {"bio": bio}},
            upsert=True,
        )
        await interaction.response.send_message(
            embed=create_success_embed("Bio updated successfully!"),
            ephemeral=True,
        )


# ─── Profile View (own profile) — Components V2 ─────────────────

class OwnProfileView(discord.ui.LayoutView):
    """Shown when viewing your OWN profile — Components V2 layout."""
    def __init__(self, *, bot, user, ctx_author, badge_text, bio, likes, commands_used, profiles_col, current_bio):
        super().__init__(timeout=180)
        self.bot = bot
        self.author_id = ctx_author.id
        self.profiles_col = profiles_col
        self.current_bio = current_bio
        self._user = user
        self._ctx_author = ctx_author
        self._badge_text = badge_text
        self._bio = bio
        self._likes = likes
        self._commands_used = commands_used
        self._build()

    def _build(self):
        self.clear_items()
        user = self._user
        ctx_author = self._ctx_author

        container = discord.ui.Container(accent_colour=discord.Colour(self.bot.config.EMBED_COLOR))

        # ── Header + Avatar ──
        container.add_item(discord.ui.TextDisplay(
            f"### {user.display_name}'s Profile"
        ))

        container.add_item(discord.ui.MediaGallery(
            discord.MediaGalleryItem(media=user.display_avatar.url)
        ))

        container.add_item(discord.ui.Separator())

        # ── Bio ──
        container.add_item(discord.ui.TextDisplay(
            f"**__Bio__**\n"
            f"> {self._bio}"
        ))

        container.add_item(discord.ui.Separator())

        # ── Achievements ──
        container.add_item(discord.ui.TextDisplay(
            f"**__Achievements__**\n"
            f"{self._badge_text}"
        ))

        container.add_item(discord.ui.Separator())

        # ── Stats ──
        container.add_item(discord.ui.TextDisplay(
            f"**__Likes__** — `{self._likes}`\n"
            f"**__Commands Used__** — `{self._commands_used}`\n"
            f"**__ID__** — `{user.id}`\n"
            f"**__Account Created__** — <t:{int(user.created_at.timestamp())}:R>"
        ))

        container.add_item(discord.ui.Separator())

        # ── Buttons ──
        btn_row = discord.ui.ActionRow()

        btn_edit = discord.ui.Button(label="Edit Bio", style=discord.ButtonStyle.blurple, custom_id="profile_edit_bio")
        btn_edit.callback = self._on_edit_bio
        btn_row.add_item(btn_edit)

        invite_url = f"https://discord.com/api/oauth2/authorize?client_id={self.bot.user.id}&permissions=8&scope=bot%20applications.commands"
        btn_row.add_item(discord.ui.Button(label="Invite Me", style=discord.ButtonStyle.link, url=invite_url))
        btn_row.add_item(discord.ui.Button(label="Support Server", style=discord.ButtonStyle.link, url=self.bot.config.SUPPORT_SERVER))

        container.add_item(btn_row)

        # ── Footer ──
        container.add_item(discord.ui.TextDisplay(
            f"-# Requested by {ctx_author.display_name}"
        ))

        self.add_item(container)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("This is not your profile!", ephemeral=True)
            return False
        return True

    async def _on_edit_bio(self, interaction: discord.Interaction):
        modal = BioModal(self.profiles_col, self.current_bio)
        await interaction.response.send_modal(modal)


# ─── Profile View (other's profile) — Components V2 ─────────────

class OtherProfileView(discord.ui.LayoutView):
    """Shown when viewing SOMEONE ELSE's profile — Components V2 layout."""
    def __init__(self, *, bot, user, ctx_author, badge_text, bio, likes, commands_used, target_id):
        super().__init__(timeout=180)
        self.bot = bot
        self.author_id = ctx_author.id
        self.target_id = target_id
        self._build(user=user, ctx_author=ctx_author, badge_text=badge_text, bio=bio, likes=likes, commands_used=commands_used)

    def _build(self, *, user, ctx_author, badge_text, bio, likes, commands_used):
        self.clear_items()

        container = discord.ui.Container(accent_colour=discord.Colour(self.bot.config.EMBED_COLOR))

        # ── Header + Avatar ──
        container.add_item(discord.ui.TextDisplay(
            f"### {user.display_name}'s Profile"
        ))

        container.add_item(discord.ui.MediaGallery(
            discord.MediaGalleryItem(media=user.display_avatar.url)
        ))

        container.add_item(discord.ui.Separator())

        # ── Bio ──
        container.add_item(discord.ui.TextDisplay(
            f"**__Bio__**\n"
            f"> {bio}"
        ))

        container.add_item(discord.ui.Separator())

        # ── Achievements ──
        container.add_item(discord.ui.TextDisplay(
            f"**__Achievements__**\n"
            f"{badge_text}"
        ))

        container.add_item(discord.ui.Separator())

        # ── Stats ──
        container.add_item(discord.ui.TextDisplay(
            f"**__Likes__** — `{likes}`\n"
            f"**__Commands Used__** — `{commands_used}`\n"
            f"**__ID__** — `{user.id}`\n"
            f"**__Account Created__** — <t:{int(user.created_at.timestamp())}:R>"
        ))

        container.add_item(discord.ui.Separator())

        # ── Buttons ──
        btn_row = discord.ui.ActionRow()

        btn_like = discord.ui.Button(label="Like", style=discord.ButtonStyle.green, custom_id="profile_like")
        btn_like.callback = self._on_like
        btn_row.add_item(btn_like)

        btn_unlike = discord.ui.Button(label="Unlike", style=discord.ButtonStyle.red, custom_id="profile_unlike")
        btn_unlike.callback = self._on_unlike
        btn_row.add_item(btn_unlike)

        invite_url = f"https://discord.com/api/oauth2/authorize?client_id={self.bot.user.id}&permissions=8&scope=bot%20applications.commands"
        btn_row.add_item(discord.ui.Button(label="Invite Me", style=discord.ButtonStyle.link, url=invite_url))
        btn_row.add_item(discord.ui.Button(label="Support Server", style=discord.ButtonStyle.link, url=self.bot.config.SUPPORT_SERVER))

        container.add_item(btn_row)

        # ── Footer ──
        container.add_item(discord.ui.TextDisplay(
            f"-# Requested by {ctx_author.display_name}"
        ))

        self.add_item(container)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("You can't use these buttons!", ephemeral=True)
            return False
        return True

    async def _on_like(self, interaction: discord.Interaction):
        now = time.time()
        one_day_ago = now - 86400

        existing = await self.bot.user_likes_col.find_one({
            "user_id": self.author_id,
            "target_id": self.target_id,
            "timestamp": {"$gt": one_day_ago},
        })
        if existing:
            return await interaction.response.send_message(
                embed=create_error_embed("You already liked this person in the last 24 hours!"),
                ephemeral=True,
            )

        daily_count = await self.bot.user_likes_col.count_documents({
            "user_id": self.author_id,
            "timestamp": {"$gt": one_day_ago},
        })
        if daily_count >= 10:
            return await interaction.response.send_message(
                embed=create_error_embed("You've used all 10 likes for today! Try again later."),
                ephemeral=True,
            )

        await self.bot.user_likes_col.insert_one({
            "user_id": self.author_id,
            "target_id": self.target_id,
            "timestamp": now,
        })
        await self.bot.user_profiles_col.update_one(
            {"user_id": self.target_id},
            {"$inc": {"likes": 1}},
            upsert=True,
        )
        await interaction.response.send_message(
            embed=create_success_embed("You liked this user!"),
            ephemeral=True,
        )

    async def _on_unlike(self, interaction: discord.Interaction):
        now = time.time()
        one_day_ago = now - 86400

        existing = await self.bot.user_likes_col.find_one({
            "user_id": self.author_id,
            "target_id": self.target_id,
            "timestamp": {"$gt": one_day_ago},
        })
        if not existing:
            return await interaction.response.send_message(
                embed=create_error_embed("You haven't liked this person recently!"),
                ephemeral=True,
            )

        await self.bot.user_likes_col.delete_one({"_id": existing["_id"]})
        await self.bot.user_profiles_col.update_one(
            {"user_id": self.target_id},
            {"$inc": {"likes": -1}},
        )
        await interaction.response.send_message(
            embed=create_success_embed("You unliked this user!"),
            ephemeral=True,
        )


# ─── Badge List View — Components V2 ─────────────────────────────

class BadgeListView(discord.ui.LayoutView):
    """Components V2 badge list display."""
    def __init__(self, bot, badge_lines, total_count):
        super().__init__(timeout=120)

        container = discord.ui.Container(accent_colour=discord.Colour(bot.config.EMBED_COLOR))

        container.add_item(discord.ui.TextDisplay(
            "### Available Badges"
        ))

        container.add_item(discord.ui.Separator())

        container.add_item(discord.ui.TextDisplay(
            "\n".join(badge_lines)
        ))

        container.add_item(discord.ui.Separator())

        container.add_item(discord.ui.TextDisplay(
            f"-# Total: {total_count} badges (including default)"
        ))

        self.add_item(container)


# ─── Cog ──────────────────────────────────────────────────────────

class Badges(commands.Cog):
    """Badge system — profile, create, delete, give & remove badges."""

    MAIN_OWNER_ID = 1146074768504787015
    DEFAULT_BADGE = {"name": "Spotifix User", "emoji": "<:requester:1285683020484972545>"}
    OWNER_BADGE_LINE = "<:Crown:1277691846721798194> **devthesuperior — THE OWNER**"
    NOPREFIX_BADGE = {"name": "No Prefix User", "emoji": "<:add:1285564587995041812>"}

    def __init__(self, bot):
        self.bot = bot
        self.badges_col = bot.badges_col
        self.user_badges_col = bot.user_badges_col
        self.profiles_col = bot.user_profiles_col
        self.likes_col = bot.user_likes_col

    # ── helpers ────────────────────────────────────────────────────

    async def _get_all_badges(self) -> list:
        """Return all badge docs from DB."""
        return await self.badges_col.find({}).to_list(length=100)

    async def _get_user_badge_names(self, user_id: int) -> list:
        """Return badge name list for a user (may be empty)."""
        doc = await self.user_badges_col.find_one({"user_id": user_id})
        return doc["badge_names"] if doc else []

    async def _get_profile(self, user_id: int) -> dict:
        """Return user profile doc (bio, likes, commands_used)."""
        doc = await self.profiles_col.find_one({"user_id": user_id})
        return doc or {"user_id": user_id, "bio": "", "likes": 0, "commands_used": 0}

    # ── profile ────────────────────────────────────────────────────

    @commands.command(name="profile", aliases=["pr"])
    @utility_cooldown()
    async def profile(self, ctx: commands.Context, user: discord.User = None):
        """View your (or someone's) bot profile with badges"""
        import traceback
        try:
            user = user or ctx.author
            is_own = user.id == ctx.author.id

            # Fetch data
            badge_names = await self._get_user_badge_names(user.id)
            all_badges = {b["name"]: b for b in await self._get_all_badges()}
            has_noprefix = await self.bot.is_noprefix(user.id)
            profile_data = await self._get_profile(user.id)

            bio = profile_data.get("bio", "") or "No bio set."
            likes = profile_data.get("likes", 0)
            commands_used = profile_data.get("commands_used", 0)

            # Build badge lines — Order: Owner → Earned → No Prefix → Spotifix User (last)
            lines: list[str] = []

            # 1) Owner line (always first for main owner)
            if user.id == self.MAIN_OWNER_ID:
                lines.append(self.OWNER_BADGE_LINE)

            # 2) Earned badges (above noprefix and default)
            for name in badge_names:
                badge = all_badges.get(name)
                if badge:
                    lines.append(f"{badge['emoji']} **{name}**")

            # 3) No Prefix badge (above default, below earned)
            if has_noprefix:
                lines.append(f"{self.NOPREFIX_BADGE['emoji']} **{self.NOPREFIX_BADGE['name']}**")

            # 4) Default badge (always last)
            lines.append(f"{self.DEFAULT_BADGE['emoji']} **{self.DEFAULT_BADGE['name']}**")

            badge_text = "\n".join(lines)

            if is_own:
                view = OwnProfileView(
                    bot=self.bot,
                    user=user,
                    ctx_author=ctx.author,
                    badge_text=badge_text,
                    bio=bio,
                    likes=likes,
                    commands_used=commands_used,
                    profiles_col=self.profiles_col,
                    current_bio=profile_data.get("bio", ""),
                )
            else:
                view = OtherProfileView(
                    bot=self.bot,
                    user=user,
                    ctx_author=ctx.author,
                    badge_text=badge_text,
                    bio=bio,
                    likes=likes,
                    commands_used=commands_used,
                    target_id=user.id,
                )

            await ctx.send(view=view)
        except Exception as e:
            traceback.print_exc()
            await ctx.send(f"```\n{traceback.format_exc()[-500:]}\n```")

    # ── like command ───────────────────────────────────────────────

    @commands.command(name="like")
    @utility_cooldown()
    async def like_user(self, ctx: commands.Context, user: discord.User):
        """Like a user's profile"""
        if user.id == ctx.author.id:
            return await ctx.send(embed=create_error_embed("You can't like yourself!"))

        now = time.time()
        one_day_ago = now - 86400

        existing = await self.likes_col.find_one({
            "user_id": ctx.author.id,
            "target_id": user.id,
            "timestamp": {"$gt": one_day_ago},
        })
        if existing:
            return await ctx.send(embed=create_error_embed("You already liked this person in the last 24 hours!"))

        daily_count = await self.likes_col.count_documents({
            "user_id": ctx.author.id,
            "timestamp": {"$gt": one_day_ago},
        })
        if daily_count >= 10:
            return await ctx.send(embed=create_error_embed("You've used all 10 likes for today! Try again later."))

        await self.likes_col.insert_one({
            "user_id": ctx.author.id,
            "target_id": user.id,
            "timestamp": now,
        })
        await self.profiles_col.update_one(
            {"user_id": user.id},
            {"$inc": {"likes": 1}},
            upsert=True,
        )
        await ctx.send(embed=create_success_embed(f"You liked **{user.display_name}**!"))

    # ── unlike command ─────────────────────────────────────────────

    @commands.command(name="unlike")
    @utility_cooldown()
    async def unlike_user(self, ctx: commands.Context, user: discord.User):
        """Unlike a user's profile"""
        if user.id == ctx.author.id:
            return await ctx.send(embed=create_error_embed("You can't unlike yourself!"))

        now = time.time()
        one_day_ago = now - 86400

        existing = await self.likes_col.find_one({
            "user_id": ctx.author.id,
            "target_id": user.id,
            "timestamp": {"$gt": one_day_ago},
        })
        if not existing:
            return await ctx.send(embed=create_error_embed("You haven't liked this person recently!"))

        await self.likes_col.delete_one({"_id": existing["_id"]})
        await self.profiles_col.update_one(
            {"user_id": user.id},
            {"$inc": {"likes": -1}},
        )
        await ctx.send(embed=create_success_embed(f"You unliked **{user.display_name}**!"))

    # ── createbadge ────────────────────────────────────────────────

    @commands.command(name="createbadge", aliases=["cb"], hidden=True)
    @commands.is_owner()
    async def create_badge(self, ctx: commands.Context, *, name: str):
        """Create a new badge (Main Owner only)"""

        # Check duplicate
        existing = await self.badges_col.find_one({"name": name})
        if existing:
            return await ctx.send(embed=create_error_embed(f"A badge named **{name}** already exists!"))

        # Ask for emoji
        await ctx.send(embed=create_success_embed(f"Send the **emoji** you want for the badge **{name}**:"))

        def check(m):
            return m.author.id == ctx.author.id and m.channel.id == ctx.channel.id

        try:
            msg = await self.bot.wait_for("message", check=check, timeout=30)
        except asyncio.TimeoutError:
            return await ctx.send(embed=create_error_embed("Timed out waiting for emoji. Badge creation cancelled."))

        emoji_str = msg.content.strip()
        if not emoji_str:
            return await ctx.send(embed=create_error_embed("No emoji received. Badge creation cancelled."))

        await self.badges_col.insert_one({
            "name": name,
            "emoji": emoji_str,
            "created_at": time.time(),
        })
        await ctx.send(embed=create_success_embed(f"Badge **{name}** {emoji_str} created successfully!"))

    # ── deletebadge ────────────────────────────────────────────────

    @commands.command(name="deletebadge", aliases=["db"], hidden=True)
    @commands.is_owner()
    async def delete_badge(self, ctx: commands.Context):
        """Delete a badge via dropdown (Main Owner only)"""

        badges = await self._get_all_badges()
        if not badges:
            return await ctx.send(embed=create_error_embed("No badges exist yet!"))

        view = BadgeSelectView(badges, ctx.author.id, placeholder="Select a badge to delete...")
        msg = await ctx.send(embed=discord.Embed(
            description="Select the badge you want to **delete**:",
            color=self.bot.config.EMBED_COLOR
        ), view=view)

        await view.wait()
        if view.selected is None:
            return await msg.edit(embed=create_error_embed("Timed out. No badge deleted."), view=None)

        name = view.selected
        # Delete badge definition
        await self.badges_col.delete_one({"name": name})
        # Remove from all users
        await self.user_badges_col.update_many({}, {"$pull": {"badge_names": name}})

        await msg.edit(embed=create_success_embed(f"Badge **{name}** deleted and removed from all users!"), view=None)

    # ── badgelist ──────────────────────────────────────────────────

    @commands.command(name="badgelist", aliases=["bl", "badges"])
    @utility_cooldown()
    async def badge_list(self, ctx: commands.Context):
        """List all available badges"""
        badges = await self._get_all_badges()

        lines = [f"{self.DEFAULT_BADGE['emoji']} **{self.DEFAULT_BADGE['name']}** *(default)*"]
        for b in badges:
            lines.append(f"{b['emoji']} **{b['name']}**")

        view = BadgeListView(self.bot, lines, len(badges) + 1)
        await ctx.send(view=view)

    # ── givebadge ──────────────────────────────────────────────────

    @commands.command(name="givebadge", aliases=["gb"], hidden=True)
    @commands.is_owner()
    async def give_badge(self, ctx: commands.Context, user: discord.User):
        """Give a badge to a user via dropdown (Main Owner only)"""

        badges = await self._get_all_badges()
        if not badges:
            return await ctx.send(embed=create_error_embed("No badges exist yet! Create one first with `createbadge`."))

        # Filter out badges user already has
        current = await self._get_user_badge_names(user.id)
        available = [b for b in badges if b["name"] not in current]
        if not available:
            return await ctx.send(embed=create_error_embed(f"**{user.display_name}** already has all available badges!"))

        view = BadgeSelectView(available, ctx.author.id, placeholder="Select a badge to give...")
        msg = await ctx.send(embed=discord.Embed(
            description=f"Select a badge to give to **{user.display_name}**:",
            color=self.bot.config.EMBED_COLOR
        ), view=view)

        await view.wait()
        if view.selected is None:
            return await msg.edit(embed=create_error_embed("Timed out. No badge given."), view=None)

        name = view.selected
        await self.user_badges_col.update_one(
            {"user_id": user.id},
            {"$addToSet": {"badge_names": name}},
            upsert=True,
        )
        badge = next((b for b in available if b["name"] == name), None)
        emoji = badge["emoji"] if badge else ""
        await msg.edit(embed=create_success_embed(f"Gave badge **{name}** {emoji} to **{user.display_name}**!"), view=None)

    # ── removebadge ────────────────────────────────────────────────

    @commands.command(name="removebadge", aliases=["rb"], hidden=True)
    @commands.is_owner()
    async def remove_badge(self, ctx: commands.Context, user: discord.User):
        """Remove a badge from a user via dropdown (Main Owner only)"""

        current = await self._get_user_badge_names(user.id)
        if not current:
            return await ctx.send(embed=create_error_embed(f"**{user.display_name}** has no badges to remove!"))

        all_badges = {b["name"]: b for b in await self._get_all_badges()}
        # Build badge objects for dropdown (include emoji)
        user_badge_objs = []
        for name in current:
            badge = all_badges.get(name, {"name": name, "emoji": ""})
            user_badge_objs.append(badge)

        view = BadgeSelectView(user_badge_objs, ctx.author.id, placeholder="Select a badge to remove...")
        msg = await ctx.send(embed=discord.Embed(
            description=f"Select a badge to remove from **{user.display_name}**:",
            color=self.bot.config.EMBED_COLOR
        ), view=view)

        await view.wait()
        if view.selected is None:
            return await msg.edit(embed=create_error_embed("Timed out. No badge removed."), view=None)

        name = view.selected
        await self.user_badges_col.update_one(
            {"user_id": user.id},
            {"$pull": {"badge_names": name}},
        )
        await msg.edit(embed=create_success_embed(f"Removed badge **{name}** from **{user.display_name}**!"), view=None)


async def setup(bot):
    await bot.add_cog(Badges(bot))
