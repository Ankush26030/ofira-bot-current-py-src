import discord
from discord.ext import commands
from utils.embeds import create_success_embed, create_error_embed
from utils.checks import in_voice

class ConfirmationView(discord.ui.View):
    def __init__(self, ctx, timeout=30):
        super().__init__(timeout=timeout)
        self.ctx = ctx
        self.value = None

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This confirmation is not for you!", ephemeral=True)
        self.value = True
        self.stop()
        await interaction.response.defer()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This confirmation is not for you!", ephemeral=True)
        self.value = False
        self.stop()
        await interaction.response.defer()

class VCMod(commands.Cog, name="VCMod"):
    """Voice Channel Moderation commands"""
    
    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx):
        if not ctx.guild:
            raise commands.NoPrivateMessage()
        return True

    @commands.command(name="vcdeafen")
    @commands.has_guild_permissions(deafen_members=True)
    @commands.bot_has_guild_permissions(deafen_members=True)
    async def vcdeafen(self, ctx, member: discord.Member):
        """Server deafen a member in voice channel"""
        if not member.voice:
            return await ctx.send(embed=create_error_embed(f"{member.mention} is not in a voice channel!"))
            
        try:
            await member.edit(deafen=True, reason=f"Action by {ctx.author}")
            await ctx.send(embed=create_success_embed(f"🔇 Server deafened **{member.display_name}**"))
        except Exception as e:
            await ctx.send(embed=create_error_embed(f"Failed to deafen member: {e}"))

    @commands.command(name="vcundeafen")
    @commands.has_guild_permissions(deafen_members=True)
    @commands.bot_has_guild_permissions(deafen_members=True)
    async def vcundeafen(self, ctx, member: discord.Member):
        """Server undeafen a member in voice channel"""
        if not member.voice:
            return await ctx.send(embed=create_error_embed(f"{member.mention} is not in a voice channel!"))
            
        try:
            await member.edit(deafen=False, reason=f"Action by {ctx.author}")
            await ctx.send(embed=create_success_embed(f"🔊 Server undeafened **{member.display_name}**"))
        except Exception as e:
            await ctx.send(embed=create_error_embed(f"Failed to undeafen member: {e}"))

    @commands.command(name="vcmute")
    @commands.has_guild_permissions(mute_members=True)
    @commands.bot_has_guild_permissions(mute_members=True)
    async def vcmute(self, ctx, member: discord.Member):
        """Server mute a member in voice channel"""
        if not member.voice:
            return await ctx.send(embed=create_error_embed(f"{member.mention} is not in a voice channel!"))
            
        try:
            await member.edit(mute=True, reason=f"Action by {ctx.author}")
            await ctx.send(embed=create_success_embed(f"🙊 Server muted **{member.display_name}**"))
        except Exception as e:
            await ctx.send(embed=create_error_embed(f"Failed to mute member: {e}"))

    @commands.command(name="vcunmute")
    @commands.has_guild_permissions(mute_members=True)
    @commands.bot_has_guild_permissions(mute_members=True)
    async def vcunmute(self, ctx, member: discord.Member):
        """Server unmute a member in voice channel"""
        if not member.voice:
            return await ctx.send(embed=create_error_embed(f"{member.mention} is not in a voice channel!"))
            
        try:
            await member.edit(mute=False, reason=f"Action by {ctx.author}")
            await ctx.send(embed=create_success_embed(f"🗣️ Server unmuted **{member.display_name}**"))
        except Exception as e:
            await ctx.send(embed=create_error_embed(f"Failed to unmute member: {e}"))

    @commands.command(name="vckick")
    @commands.has_guild_permissions(move_members=True)
    @commands.bot_has_guild_permissions(move_members=True)
    async def vckick(self, ctx, member: discord.Member):
        """Disconnect a member from voice channel"""
        if not member.voice:
            return await ctx.send(embed=create_error_embed(f"{member.mention} is not in a voice channel!"))
            
        try:
            await member.move_to(None, reason=f"Action by {ctx.author}")
            await ctx.send(embed=create_success_embed(f"👋 Disconnected **{member.display_name}** from voice"))
        except Exception as e:
            await ctx.send(embed=create_error_embed(f"Failed to disconnect member: {e}"))

    @commands.command(name="vcmove")
    @commands.has_guild_permissions(move_members=True)
    @commands.bot_has_guild_permissions(move_members=True)
    async def vcmove(self, ctx, member: discord.Member, channel: discord.VoiceChannel):
        """Move a member to another voice channel"""
        if not member.voice:
            return await ctx.send(embed=create_error_embed(f"{member.mention} is not in a voice channel!"))
            
        try:
            await member.move_to(channel, reason=f"Action by {ctx.author}")
            await ctx.send(embed=create_success_embed(f"➡ Moved **{member.display_name}** to **{channel.name}**"))
        except Exception as e:
            await ctx.send(embed=create_error_embed(f"Failed to move member: {e}"))

    @commands.command(name="vcdrag")
    @commands.has_guild_permissions(move_members=True)
    @commands.bot_has_guild_permissions(move_members=True)
    async def vcdrag(self, ctx, member: discord.Member):
        """Move a member to your current voice channel"""
        if not ctx.author.voice:
            return await ctx.send(embed=create_error_embed("You need to be in a voice channel to use this!"))
            
        if not member.voice:
            return await ctx.send(embed=create_error_embed(f"{member.mention} is not in a voice channel!"))
            
        target_channel = ctx.author.voice.channel
        
        if member.voice.channel == target_channel:
             return await ctx.send(embed=create_error_embed(f"{member.mention} is already in **{target_channel.name}**!"))

        try:
            await member.move_to(target_channel, reason=f"Drag by {ctx.author}")
            await ctx.send(embed=create_success_embed(f"⬅ Dragged **{member.display_name}** to **{target_channel.name}**"))
        except Exception as e:
            await ctx.send(embed=create_error_embed(f"Failed to drag member: {e}"))

    @commands.command(name="vclist")
    async def vclist(self, ctx):
        """List all members in your current voice channel"""
        if not ctx.author.voice:
            return await ctx.send(embed=create_error_embed("You need to be in a voice channel to list members!"))
            
        channel = ctx.author.voice.channel
        members = channel.members
        
        if not members:
            return await ctx.send(embed=create_error_embed(f"No members found in **{channel.name}**"))

        desc = ""
        for i, m in enumerate(members, 1):
            status = []
            if m.voice.self_mute: status.append("🔇 (Self)")
            if m.voice.mute: status.append("🙊 (Server)")
            if m.voice.self_deaf: status.append("🙉 (Self)")
            if m.voice.deaf: status.append("🔇 (Server)")
            
            status_str = f" - {' '.join(status)}" if status else ""
            desc += f"`{i}.` **{m.display_name}**{status_str}\n"

        embed = discord.Embed(
            title=f"👥 Members in {channel.name} ({len(members)})",
            description=desc[:4000], # Prevent overflow
            color=self.bot.config.EMBED_COLOR
        )
        await ctx.send(embed=embed)

    @commands.command(name="vckickall")
    @commands.has_guild_permissions(move_members=True)
    @commands.bot_has_guild_permissions(move_members=True)
    async def vckickall(self, ctx):
        """Disconnect ALL members from your voice channel"""
        if not ctx.author.voice:
            return await ctx.send(embed=create_error_embed("You need to be in a voice channel to use this!"))
            
        channel = ctx.author.voice.channel
        members = [m for m in channel.members if not m.bot and m.id != ctx.author.id] # Don't kick bot or self usually? Let's kick everyone except bot.
        # Actually user might want to clear the channel entirely.
        # Let's count targetable members.
        
        target_members = [m for m in channel.members if not m.bot] # Kick all non-bots
        
        if not target_members:
             return await ctx.send(embed=create_error_embed("No users to kick!"))

        view = ConfirmationView(ctx)
        msg = await ctx.send(
            embed=discord.Embed(
                description=f"⚠️ Are you sure you want to **DISCONNECT {len(target_members)} users** from **{channel.name}**?", 
                color=discord.Color.red()
            ),
            view=view
        )
        
        await view.wait()
        
        if view.value:
            count = 0
            for m in target_members:
                try:
                    await m.move_to(None, reason=f"Kickall by {ctx.author}")
                    count += 1
                except:
                    pass
            
            await msg.edit(embed=create_success_embed(f"👋 Disconnected **{count}** users from **{channel.name}**"), view=None)
        else:
            await msg.edit(embed=create_error_embed("Action cancelled."), view=None)

    @commands.command(name="vcmuteall")
    @commands.has_guild_permissions(mute_members=True)
    @commands.bot_has_guild_permissions(mute_members=True)
    async def vcmuteall(self, ctx):
        """Server mute ALL members in your voice channel"""
        if not ctx.author.voice:
            return await ctx.send(embed=create_error_embed("You need to be in a voice channel to use this!"))
            
        channel = ctx.author.voice.channel
        target_members = [m for m in channel.members if not m.bot and not m.voice.mute]
        
        if not target_members:
             return await ctx.send(embed=create_error_embed("No users to mute!"))

        view = ConfirmationView(ctx)
        msg = await ctx.send(
            embed=discord.Embed(
                description=f"⚠️ Are you sure you want to **MUTE {len(target_members)} users** in **{channel.name}**?", 
                color=discord.Color.red()
            ),
            view=view
        )
        
        await view.wait()
        
        if view.value:
            count = 0
            for m in target_members:
                try:
                    await m.edit(mute=True, reason=f"Muteall by {ctx.author}")
                    count += 1
                except:
                    pass
            
            await msg.edit(embed=create_success_embed(f"🙊 Server muted **{count}** users in **{channel.name}**"), view=None)
        else:
            await msg.edit(embed=create_error_embed("Action cancelled."), view=None)

    @commands.command(name="vcunmuteall")
    @commands.has_guild_permissions(mute_members=True)
    @commands.bot_has_guild_permissions(mute_members=True)
    async def vcunmuteall(self, ctx):
        """Server unmute ALL members in your voice channel"""
        if not ctx.author.voice:
            return await ctx.send(embed=create_error_embed("You need to be in a voice channel to use this!"))
            
        channel = ctx.author.voice.channel
        target_members = [m for m in channel.members if not m.bot and m.voice.mute]
        
        if not target_members:
             return await ctx.send(embed=create_error_embed("No users to unmute!"))

        view = ConfirmationView(ctx)
        msg = await ctx.send(
            embed=discord.Embed(
                description=f"⚠️ Are you sure you want to **UNMUTE {len(target_members)} users** in **{channel.name}**?", 
                color=discord.Color.red()
            ),
            view=view
        )
        
        await view.wait()
        
        if view.value:
            count = 0
            for m in target_members:
                try:
                    await m.edit(mute=False, reason=f"Unmuteall by {ctx.author}")
                    count += 1
                except:
                    pass
            
            await msg.edit(embed=create_success_embed(f"🗣️ Server unmuted **{count}** users in **{channel.name}**"), view=None)
        else:
            await msg.edit(embed=create_error_embed("Action cancelled."), view=None)

async def setup(bot):
    await bot.add_cog(VCMod(bot))
