import discord
from discord.ext import commands
import wavelink
from utils.embeds import create_queue_embed, create_nowplaying_embed, create_success_embed, create_error_embed
from utils.checks import in_voice, same_voice, is_playing
from player import CustomPlayer
import random
from utils.ratelimit import music_cooldown
from utils.views import PaginatedListView

class Queue(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="queue", aliases=["q"])
    @music_cooldown()
    async def queue(self, ctx: commands.Context):
        """Display the current queue"""
        player: CustomPlayer = ctx.guild.voice_client
        
        if not player or (not player.current and player.queue.is_empty):
            return await ctx.send(embed=create_error_embed("Queue is empty!"))
            
        # Prepare queue items
        queue_items = []
        for track in player.queue:
             duration = f"{int(track.length//60000)}:{int((track.length/1000)%60):02}"
             queue_items.append(f"[{track.title}]({track.uri}) | `{duration}`")
             
        # Prepare Now Playing prefix
        description_prefix = None
        if player.current:
            duration = f"{int(player.current.length//60000)}:{int((player.current.length/1000)%60):02}"
            description_prefix = f"**Now Playing:**\n[{player.current.title}]({player.current.uri}) | `{duration}`\n\n**Up Next:**"
            
        if not queue_items:
             # Only now playing (queue empty)
             embed = discord.Embed(title=f"Queue for {ctx.guild.name}", color=self.bot.config.EMBED_COLOR)
             if description_prefix:
                 embed.description = f"{description_prefix}\n*Queue is empty*"
             else:
                 embed.description = "*Queue is empty*"
             return await ctx.send(embed=embed)

        view = PaginatedListView(
            items=queue_items,
            title=f"Queue for {ctx.guild.name}",
            items_per_page=10,
            color=self.bot.config.EMBED_COLOR,
            footer_text=f"Total tracks: {len(queue_items)}",
            author_id=ctx.author.id,
            description_prefix=description_prefix
        )
        await ctx.send(embed=view.get_embed(), view=view)


    @commands.command(name="nowplaying", aliases=["np", "current"])
    @music_cooldown()
    async def nowplaying(self, ctx: commands.Context):
        """Show currently playing song"""
        player: CustomPlayer = ctx.guild.voice_client
        
        if not player or not player.current:
            return await ctx.send(embed=create_error_embed("Nothing is playing!"))
            
        embed = create_nowplaying_embed(player)
        await ctx.send(embed=embed)

    @commands.command(name="clearqueue", aliases=["cq", "clq"])
    @music_cooldown()
    @same_voice()
    async def clearqueue(self, ctx: commands.Context):
        """Clear the queue"""
        player: CustomPlayer = ctx.guild.voice_client
        
        if not player:
            return await ctx.send(embed=create_error_embed("I am not connected."))
            
        player.queue.clear()
        await ctx.send(embed=create_success_embed("Cleared the queue!"))

    @commands.command(name="remove", aliases=["rm"])
    @music_cooldown()
    @same_voice()
    async def remove(self, ctx: commands.Context, index: int):
        """Remove a track from the queue"""
        player: CustomPlayer = ctx.guild.voice_client
        
        if not player or player.queue.is_empty:
             return await ctx.send(embed=create_error_embed("Queue is empty!"))
             
        if index < 1 or index > player.queue.count:
            return await ctx.send(embed=create_error_embed("Invalid queue index!"))
            
        # Wavelink queue is a bit tricky to edit in middle
        # We can convert to list, remove, and recreate queue
        
        queue_list = list(player.queue)
        removed_track = queue_list.pop(index - 1)
        
        player.queue.clear()
        for track in queue_list:
            await player.queue.put_wait(track)
            
        await ctx.send(embed=create_success_embed(f"Removed **{removed_track.title}** from queue"))

    @commands.command(name="shuffle", aliases=["sh"])
    @music_cooldown()
    @same_voice()
    async def shuffle(self, ctx: commands.Context):
        """Shuffle the queue"""
        player: CustomPlayer = ctx.guild.voice_client
        
        if not player or player.queue.is_empty:
             return await ctx.send(embed=create_error_embed("Queue is empty!"))
             
        player.queue.shuffle()
        await ctx.send(embed=create_success_embed("Shuffled the queue!"))

async def setup(bot):
    await bot.add_cog(Queue(bot))
