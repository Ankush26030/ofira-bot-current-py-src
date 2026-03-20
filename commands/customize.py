import discord
from discord.ext import commands
import aiohttp
import base64
import asyncio
from utils.embeds import create_success_embed, create_error_embed
from utils.ratelimit import utility_cooldown


class CustomizeView(discord.ui.LayoutView):
    def __init__(self, bot, ctx):
        super().__init__(timeout=180)
        self.bot = bot
        self.ctx = ctx
        self._build()

    def _build(self):
        self.clear_items()

        guild = self.ctx.guild
        member = guild.get_member(self.bot.user.id)

        has_avatar = member.guild_avatar is not None
        has_banner = member.banner is not None

        avatar_status = "Set (Live)" if has_avatar else "Not Set"
        banner_status = "Set (Live)" if has_banner else "Not Set"

        container = discord.ui.Container(accent_colour=discord.Colour(self.bot.config.EMBED_COLOR))

        # ── Header ──
        container.add_item(discord.ui.TextDisplay(
            "### Server Customization\n"
            "-# Customize the bot's profile in your server"
        ))

        container.add_item(discord.ui.Separator())

        # ── Current Settings ──
        container.add_item(discord.ui.TextDisplay(
            "**Current Settings**\n"
            f"> **Status:** Enabled\n"
            f"> **Custom Avatar:** {avatar_status}\n"
            f"> **Custom Banner:** {banner_status}"
        ))

        container.add_item(discord.ui.Separator())

        # ── What gets customized ──
        container.add_item(discord.ui.TextDisplay(
            "**What gets customized?**\n"
            "> **Avatar** — The bot's profile picture in this server only\n"
            "> **Banner** — The bot's profile banner in this server only"
        ))

        container.add_item(discord.ui.Separator())

        # ── How to use ──
        container.add_item(discord.ui.TextDisplay(
            "**How to use**\n"
            "-# Click the buttons below to customize the bot's appearance in your server."
        ))

        container.add_item(discord.ui.Separator())

        # ── Note ──
        container.add_item(discord.ui.TextDisplay(
            "-# All changes are **LIVE** and only visible in **this server**. "
            "Other servers see the default bot profile."
        ))

        container.add_item(discord.ui.Separator())

        # ── Buttons Row 1: Change ──
        btn_row1 = discord.ui.ActionRow()

        btn_avatar = discord.ui.Button(label="Change Avatar", style=discord.ButtonStyle.blurple, custom_id="customize_change_avatar")
        btn_avatar.callback = self._on_change_avatar
        btn_row1.add_item(btn_avatar)

        btn_banner = discord.ui.Button(label="Change Banner", style=discord.ButtonStyle.blurple, custom_id="customize_change_banner")
        btn_banner.callback = self._on_change_banner
        btn_row1.add_item(btn_banner)

        container.add_item(btn_row1)

        # ── Buttons Row 2: Reset ──
        btn_row2 = discord.ui.ActionRow()

        btn_reset_avatar = discord.ui.Button(label="Reset Avatar", style=discord.ButtonStyle.gray, custom_id="customize_reset_avatar")
        btn_reset_avatar.callback = self._on_reset_avatar
        btn_row2.add_item(btn_reset_avatar)

        btn_reset_banner = discord.ui.Button(label="Reset Banner", style=discord.ButtonStyle.gray, custom_id="customize_reset_banner")
        btn_reset_banner.callback = self._on_reset_banner
        btn_row2.add_item(btn_reset_banner)

        container.add_item(btn_row2)

        self.add_item(container)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("This is not your customization menu!", ephemeral=True)
            return False
        return True

    async def _on_change_avatar(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            embed=create_success_embed(
                "**Upload Avatar**\n\n"
                "Please upload an image for the bot's server avatar.\n"
                "You have **60 seconds** to upload the image."
            ),
            ephemeral=True
        )

        def check(m):
            return m.author.id == interaction.user.id and m.channel.id == interaction.channel.id and len(m.attachments) > 0

        try:
            msg = await self.bot.wait_for('message', timeout=60.0, check=check)
            attachment = msg.attachments[0]

            async with aiohttp.ClientSession() as session:
                async with session.get(attachment.url) as resp:
                    if resp.status != 200:
                        return await interaction.followup.send(embed=create_error_embed("Failed to download image!"), ephemeral=True)
                    image_data = await resp.read()

            base64_image = base64.b64encode(image_data).decode('utf-8')
            content_type = attachment.content_type or 'image/png'
            data_uri = f"data:{content_type};base64,{base64_image}"

            async with aiohttp.ClientSession() as session:
                url = f"https://discord.com/api/v10/guilds/{interaction.guild.id}/members/@me"
                headers = {
                    "Authorization": f"Bot {self.bot.config.DISCORD_TOKEN}",
                    "Content-Type": "application/json"
                }
                payload = {"avatar": data_uri}

                async with session.patch(url, headers=headers, json=payload) as resp:
                    if resp.status == 200:
                        await msg.delete()
                        await interaction.followup.send(embed=create_success_embed("Avatar updated successfully!"), ephemeral=True)
                        self._build()
                        await interaction.message.edit(view=self)
                    else:
                        error_text = await resp.text()
                        await interaction.followup.send(
                            embed=create_error_embed(f"Failed to update avatar: {resp.status}\n{error_text[:100]}"),
                            ephemeral=True
                        )

        except asyncio.TimeoutError:
            await interaction.followup.send(
                embed=create_error_embed("**Timeout!**\n\nYou didn't upload an image in time. Please use the command again."),
                ephemeral=True
            )

    async def _on_change_banner(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            embed=create_success_embed(
                "**Upload Banner**\n\n"
                "Please upload an image for the bot's server banner.\n"
                "You have **60 seconds** to upload the image."
            ),
            ephemeral=True
        )

        def check(m):
            return m.author.id == interaction.user.id and m.channel.id == interaction.channel.id and len(m.attachments) > 0

        try:
            msg = await self.bot.wait_for('message', timeout=60.0, check=check)
            attachment = msg.attachments[0]

            async with aiohttp.ClientSession() as session:
                async with session.get(attachment.url) as resp:
                    if resp.status != 200:
                        return await interaction.followup.send(embed=create_error_embed("Failed to download image!"), ephemeral=True)
                    image_data = await resp.read()

            base64_image = base64.b64encode(image_data).decode('utf-8')
            content_type = attachment.content_type or 'image/png'
            data_uri = f"data:{content_type};base64,{base64_image}"

            async with aiohttp.ClientSession() as session:
                url = f"https://discord.com/api/v10/guilds/{interaction.guild.id}/members/@me"
                headers = {
                    "Authorization": f"Bot {self.bot.config.DISCORD_TOKEN}",
                    "Content-Type": "application/json"
                }
                payload = {"banner": data_uri}

                async with session.patch(url, headers=headers, json=payload) as resp:
                    if resp.status == 200:
                        await msg.delete()
                        await interaction.followup.send(embed=create_success_embed("Banner updated successfully!"), ephemeral=True)
                        self._build()
                        await interaction.message.edit(view=self)
                    else:
                        error_text = await resp.text()
                        await interaction.followup.send(
                            embed=create_error_embed(f"Failed to update banner: {resp.status}\n{error_text[:100]}"),
                            ephemeral=True
                        )

        except asyncio.TimeoutError:
            await interaction.followup.send(
                embed=create_error_embed("**Timeout!**\n\nYou didn't upload an image in time. Please use the command again."),
                ephemeral=True
            )

    async def _on_reset_avatar(self, interaction: discord.Interaction):
        async with aiohttp.ClientSession() as session:
            url = f"https://discord.com/api/v10/guilds/{interaction.guild.id}/members/@me"
            headers = {
                "Authorization": f"Bot {self.bot.config.DISCORD_TOKEN}",
                "Content-Type": "application/json"
            }
            payload = {"avatar": None}

            async with session.patch(url, headers=headers, json=payload) as resp:
                if resp.status == 200:
                    await interaction.response.send_message(embed=create_success_embed("Avatar reset successfully!"), ephemeral=True)
                    self._build()
                    await interaction.message.edit(view=self)
                else:
                    error_text = await resp.text()
                    await interaction.response.send_message(
                        embed=create_error_embed(f"Failed to reset avatar: {resp.status}\n{error_text[:100]}"),
                        ephemeral=True
                    )

    async def _on_reset_banner(self, interaction: discord.Interaction):
        async with aiohttp.ClientSession() as session:
            url = f"https://discord.com/api/v10/guilds/{interaction.guild.id}/members/@me"
            headers = {
                "Authorization": f"Bot {self.bot.config.DISCORD_TOKEN}",
                "Content-Type": "application/json"
            }
            payload = {"banner": None}

            print(f"[CUSTOMIZE] Reset Banner - URL: {url}")
            print(f"[CUSTOMIZE] Reset Banner - Payload: {payload}")

            async with session.patch(url, headers=headers, json=payload) as resp:
                response_text = await resp.text()
                print(f"[CUSTOMIZE] Reset Banner - Status: {resp.status}")
                print(f"[CUSTOMIZE] Reset Banner - Response: {response_text[:300]}")

                if resp.status == 200:
                    await interaction.response.send_message(embed=create_success_embed("Banner reset successfully!"), ephemeral=True)
                    self._build()
                    await interaction.message.edit(view=self)
                else:
                    await interaction.response.send_message(
                        embed=create_error_embed(f"Failed to reset banner: {resp.status}\n{response_text[:100]}"),
                        ephemeral=True
                    )


class Customize(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="customize", aliases=["serverprofile", "botprofile"])
    @utility_cooldown()
    @commands.has_permissions(administrator=True)
    async def customize(self, ctx: commands.Context):
        """Customize the bot's profile in your server (Admin only)"""
        view = CustomizeView(self.bot, ctx)
        await ctx.send(view=view)


async def setup(bot):
    await bot.add_cog(Customize(bot))
