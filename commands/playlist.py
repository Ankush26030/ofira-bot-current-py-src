import discord
from discord.ext import commands
import wavelink
from utils.embeds import create_success_embed, create_error_embed
from bson import ObjectId
from utils.ratelimit import playlist_cooldown
from utils.views import PaginatedListView

class Playlist(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.playlists_col = bot.playlists_col

    @commands.group(name="playlist", aliases=["pl"], invoke_without_command=True)
    @playlist_cooldown()
    async def playlist(self, ctx: commands.Context):
        """Playlist commands"""
        await ctx.send_help(ctx.command)

    @playlist.command(name="create", aliases=["c", "add"])
    async def create(self, ctx: commands.Context, *, name: str):
        """Create a new playlist"""
        # Check if exists
        existing = await self.playlists_col.find_one({"user_id": ctx.author.id, "name": name})
        if existing:
            return await ctx.send(embed=create_error_embed(f"Playlist **{name}** already exists!"))
            
        data = {
            "user_id": ctx.author.id,
            "name": name,
            "tracks": [],
            "created_at": discord.utils.utcnow()
        }
        
        await self.playlists_col.insert_one(data)
        await ctx.send(embed=create_success_embed(f"Created playlist **{name}**"))

    @playlist.command(name="delete", aliases=["del", "remove_list", "removelist"])
    async def delete_playlist(self, ctx: commands.Context, *, name: str):
        """Delete a playlist"""
        result = await self.playlists_col.delete_one({"user_id": ctx.author.id, "name": name})
        
        if result.deleted_count == 0:
            return await ctx.send(embed=create_error_embed(f"Playlist **{name}** not found!"))
            
        await ctx.send(embed=create_success_embed(f"Deleted playlist **{name}**"))

    @playlist.command(name="list", aliases=["l", "showall"])
    async def list_playlists(self, ctx: commands.Context):
        """List your playlists"""
        cursor = self.playlists_col.find({"user_id": ctx.author.id})
        playlists = await cursor.to_list(length=None) # Get all playlists
        
        if not playlists:
            return await ctx.send(embed=create_error_embed("You don't have any playlists!"))
            
        items = []
        for p in playlists:
            items.append(f"**{p['name']}** - {len(p['tracks'])} tracks")
            
        view = PaginatedListView(
            items=items,
            title=f"📂 Playlists for {ctx.author.name}",
            items_per_page=10,
            color=self.bot.config.EMBED_COLOR,
            footer_text=f"Total playlists: {len(playlists)}",
            author_id=ctx.author.id
        )
        await ctx.send(embed=view.get_embed(), view=view)

    @playlist.command(name="view", aliases=["show", "info"])
    async def view_playlist(self, ctx: commands.Context, *, name: str):
        """View tracks in a playlist"""
        playlist = await self.playlists_col.find_one({"user_id": ctx.author.id, "name": name})
        
        if not playlist:
            return await ctx.send(embed=create_error_embed(f"Playlist **{name}** not found!"))
            
        tracks = playlist["tracks"]
        if not tracks:
             return await ctx.send(embed=create_error_embed(f"Playlist **{name}** is empty!"))
             
        items = []
        for t in tracks:
            items.append(f"[{t['title']}]({t['uri']})")
            
        view = PaginatedListView(
            items=items,
            title=f"💿 Playlist: {name}",
            items_per_page=10,
            color=self.bot.config.EMBED_COLOR,
            footer_text=f"Total tracks: {len(tracks)}",
            author_id=ctx.author.id
        )
        await ctx.send(embed=view.get_embed(), view=view)

    @playlist.command(name="play", aliases=["p", "load"])
    async def play_playlist(self, ctx: commands.Context, *, name: str):
        """Play a playlist"""
        playlist = await self.playlists_col.find_one({"user_id": ctx.author.id, "name": name})
        
        if not playlist:
            return await ctx.send(embed=create_error_embed(f"Playlist **{name}** not found!"))
            
        tracks_data = playlist["tracks"]
        if not tracks_data:
             return await ctx.send(embed=create_error_embed(f"Playlist **{name}** is empty!"))
             
        # Connect if needed
        if not ctx.guild.voice_client:
            try:
                from player import safe_connect
                await safe_connect(ctx.author.voice.channel)
            except Exception as e:
                return await ctx.send(embed=create_error_embed(f"Failed to join VC: {e}"))
                
        vc = ctx.guild.voice_client
        if vc.channel != ctx.author.voice.channel:
             return await ctx.send(embed=create_error_embed("You must be in the same VC!"))

        vc.text_channel = ctx.channel # Ensure text channel is set
        
        added = 0
        skipped = 0
        
        # Load tracks
        for data in tracks_data:
            # Reconstruct wavelink.Playable
            # Usually we need to search or reconstruct manually. 
            # Wavelink 3.0 Playable can't be easily instantiated from dict without URI search usually.
            # But we stored URI. We can search by URI.
            try:
                # We can try to just use the URI.
                # Or create a track object if possible. 
                # Searching URI is safest.
                results = await wavelink.Playable.search(data["uri"])
                if results:
                    track = results[0]
                    # Check duration again? Or assume playlist tracks are safe? 
                    # Let's enforce 30s rule again for safety.
                    if not track.is_stream and track.length < 30000:
                        skipped += 1
                        continue
                        
                    track.requester = ctx.author
                    await vc.queue.put_wait(track)
                    added += 1
            except Exception as e:
                print(f"Error loading track {data['uri']}: {e}")
                continue
                
        if added == 0:
            return await ctx.send(embed=create_error_embed("Failed to load any valid tracks (or all were < 30s)."))
            
        desc = f"Loaded playlist **{name}** ({added} tracks)"
        if skipped > 0:
            desc += f"\n⚠️ Skipped {skipped} tracks (< 30s)"
            
        await ctx.send(embed=create_success_embed(desc))
        
        if not vc.playing:
            await vc.play(await vc.queue.get_wait())

    @playlist.command(name="remove", aliases=["rem", "delete_song"])
    async def remove_song(self, ctx: commands.Context, name: str, index: int):
        """Remove a song from a playlist by index"""
        playlist = await self.playlists_col.find_one({"user_id": ctx.author.id, "name": name})
        
        if not playlist:
            return await ctx.send(embed=create_error_embed(f"Playlist **{name}** not found!"))
            
        tracks = playlist["tracks"]
        if index < 1 or index > len(tracks):
             return await ctx.send(embed=create_error_embed(f"Invalid index! Playlist has {len(tracks)} tracks."))
             
        removed = tracks.pop(index - 1)
        
        await self.playlists_col.update_one(
            {"_id": playlist["_id"]},
            {"$set": {"tracks": tracks}}
        )
        
        await ctx.send(embed=create_success_embed(f"Removed **{removed['title']}** from **{name}**"))
        
    # Aliases for p_create -> playlist create
    # Since we can't alias subcommands at root easily without a separate command function.
    # The user asked for `p_create` or `pcreate` or `playlist create`.
    # I will add root commands that redirect.

    @commands.command(name="pcreate", aliases=["p_create"])
    @playlist_cooldown()
    async def pcreate(self, ctx, *, name: str):
        """Alias for playlist create"""
        await self.create(ctx, name=name)

async def setup(bot):
    await bot.add_cog(Playlist(bot))
