import discord
from discord.ext import commands
import wavelink
from player import CustomPlayer
from utils.ratelimit import spotify_cooldown
from utils.spotify_helper import SpotifyHelper
from utils.checks import in_voice
from config import Config


def _sp_view(bot, title: str, body: str, *, error: bool = False) -> discord.ui.LayoutView:
    """Build a Components V2 view for Spotify messages."""
    view = discord.ui.LayoutView()
    colour = discord.Colour(bot.config.ERROR_COLOR if error else 0x1DB954)
    container = discord.ui.Container(accent_colour=colour)
    container.add_item(discord.ui.TextDisplay(f"### {title}"))
    container.add_item(discord.ui.Separator())
    container.add_item(discord.ui.TextDisplay(body))
    view.add_item(container)
    return view


class Spotify(commands.Cog):
    """Spotify integration commands"""
    
    def __init__(self, bot):
        self.bot = bot
        self.spotify = SpotifyHelper()
    
    @commands.group(name="spotify", aliases=["sp"], invoke_without_command=True)
    @spotify_cooldown()
    async def spotify_group(self, ctx: commands.Context):
        """Spotify commands - search albums, artists, playlists, and profiles"""
        await ctx.send_help(ctx.command)
    
    @spotify_group.command(name="auth", aliases=["status"])
    @spotify_cooldown()
    async def auth(self, ctx: commands.Context):
        """Check Spotify API authentication status"""
        if self.spotify.is_authenticated():
            view = _sp_view(
                self.bot, "Spotify API Connected",
                f"Successfully authenticated with Spotify API\n\n"
                f"**Status:** ✓ Ready\n"
                f"**Client ID:** `{Config.SPOTIFY_CLIENT_ID[:20]}...`"
            )
        else:
            view = _sp_view(
                self.bot, "Spotify API Not Connected",
                "Failed to authenticate with Spotify API. Please check credentials.",
                error=True
            )
        
        await ctx.send(view=view)
    
    @spotify_group.command(name="playlist", aliases=["pl"])
    @spotify_cooldown()
    async def playlist(self, ctx: commands.Context, *, playlist_url: str):
        """Get information about a Spotify playlist
        
        Usage: ,spotify playlist <url or id>
        Example: ,spotify playlist 37i9dQZF1DXcBWIGoYBM5M
        """
        if not self.spotify.is_authenticated():
            return await ctx.send(view=_sp_view(self.bot, "Not Authenticated", "Spotify API is not authenticated!", error=True))
        
        async with ctx.typing():
            playlist = self.spotify.get_playlist(playlist_url)
            
            if not playlist:
                return await ctx.send(view=_sp_view(self.bot, "Not Found", "Could not find that playlist. Make sure the URL or ID is correct.", error=True))
            
            owner = playlist['owner']['display_name']
            tracks_total = playlist['tracks']['total']
            followers = playlist['followers']['total']
            
            # Build info text
            lines = [
                f"**{playlist['name']}**",
                f"{playlist.get('description', 'No description')}",
                "",
                f"**Owner:** {owner}",
                f"**Tracks:** {tracks_total:,}",
                f"**Followers:** {self.spotify.format_number(followers)}",
            ]
            
            status = []
            if playlist.get('public'):
                status.append("Public")
            if playlist.get('collaborative'):
                status.append("Collaborative")
            if status:
                lines.append(f"**Status:** {' • '.join(status)}")
            
            view = discord.ui.LayoutView(timeout=180)
            container = discord.ui.Container(accent_colour=discord.Colour(0x1DB954))
            container.add_item(discord.ui.TextDisplay("### Spotify Playlist"))
            container.add_item(discord.ui.Separator())
            container.add_item(discord.ui.TextDisplay("\n".join(lines)))
            view.add_item(container)
            
            # Add buttons
            from utils.spotify_views import PlaylistInfoView
            play_view = PlaylistInfoView(playlist['external_urls']['spotify'], playlist['name'], ctx.author.id)
            
            # Add link button + play button as action row
            action_row = discord.ui.ActionRow()
            action_row.add_item(discord.ui.Button(label="Open on Spotify", style=discord.ButtonStyle.link, url=playlist['external_urls']['spotify']))
            view.add_item(action_row)
            
        await ctx.send(view=view)
        # Send play button separately since it needs callback
        await ctx.send(view=play_view)
    
    @spotify_group.command(name="profile", aliases=["user"])
    @spotify_cooldown()
    async def profile(self, ctx: commands.Context, *, username: str = None):
        """Get information about a Spotify user profile
        
        Usage: ,spotify profile [username or url]
        If no username is provided, shows your linked profile.
        """
        if not self.spotify.is_authenticated():
            return await ctx.send(view=_sp_view(self.bot, "Not Authenticated", "Spotify API is not authenticated!", error=True))
        
        # If no username provided, try to find linked profile
        if not username:
            profile = await self.bot.spotify_profiles_col.find_one({"discord_id": ctx.author.id})
            if not profile:
                return await ctx.send(view=_sp_view(
                    self.bot, "Not Linked",
                    "You haven't linked your Spotify profile yet!\n"
                    "Please provide a username or use `,spotify login` to link your account.",
                    error=True
                ))
            username = profile['spotify_id']
        
        async with ctx.typing():
            user = self.spotify.get_user_profile(username)
            
            if not user:
                return await ctx.send(view=_sp_view(self.bot, "Not Found", "Could not find that user. Make sure the username is correct.", error=True))
            
            followers = user['followers']['total']
            
            lines = [
                f"**{user.get('display_name', user['id'])}**",
                "",
                f"**Followers:** {self.spotify.format_number(followers)}",
                f"**User ID:** `{user['id']}`",
            ]
            
            if 'product' in user:
                lines.append(f"**Account Type:** {user['product'].title()}")
            
            view = discord.ui.LayoutView(timeout=180)
            container = discord.ui.Container(accent_colour=discord.Colour(0x1DB954))
            container.add_item(discord.ui.TextDisplay("### Spotify Profile"))
            container.add_item(discord.ui.Separator())
            container.add_item(discord.ui.TextDisplay("\n".join(lines)))
            view.add_item(container)
            
            # Add link button
            action_row = discord.ui.ActionRow()
            action_row.add_item(discord.ui.Button(label="Open on Spotify", style=discord.ButtonStyle.link, url=user['external_urls']['spotify']))
            view.add_item(action_row)
            
        await ctx.send(view=view)
        
        # Send playlists button separately
        from utils.spotify_views import SpotifyProfileView
        profile_view = SpotifyProfileView(self.spotify, user['id'])
        await ctx.send(view=profile_view)

    @spotify_group.command(name="album", aliases=["ab"])
    @spotify_cooldown()
    async def album(self, ctx: commands.Context, *, album_url: str):
        """Get information about a Spotify album
        
        Usage: ,spotify album <url or id>
        Example: ,spotify album 41zDWUZpSLh5a3794hYl7g
        """
        if not self.spotify.is_authenticated():
            return await ctx.send(view=_sp_view(self.bot, "Not Authenticated", "Spotify API is not authenticated!", error=True))
        
        async with ctx.typing():
            album = self.spotify.get_album(album_url)
            
            if not album:
                return await ctx.send(view=_sp_view(self.bot, "Not Found", "Could not find that album. Make sure the URL or ID is correct.", error=True))
            
            artists = ", ".join([artist['name'] for artist in album['artists']])
            release_date = album['release_date']
            total_tracks = album['total_tracks']
            
            lines = [
                f"**{album['name']}**",
                "",
                f"**Artist:** {artists}",
                f"**Release Date:** {release_date}",
                f"**Tracks:** {total_tracks}",
            ]
            
            if 'popularity' in album:
                popularity = album['popularity']
                pop_bar = "█" * (popularity // 10) + "░" * (10 - popularity // 10)
                lines.append(f"**Popularity:** {pop_bar} {popularity}%")
            
            lines.append(f"\n-# {album['album_type'].title()}")
            
            view = discord.ui.LayoutView(timeout=30)
            container = discord.ui.Container(accent_colour=discord.Colour(0x1DB954))
            container.add_item(discord.ui.TextDisplay("### Spotify Album"))
            container.add_item(discord.ui.Separator())
            container.add_item(discord.ui.TextDisplay("\n".join(lines)))
            view.add_item(container)
            
            # Add link button
            action_row = discord.ui.ActionRow()
            action_row.add_item(discord.ui.Button(label="Open on Spotify", style=discord.ButtonStyle.link, url=album['external_urls']['spotify']))
            view.add_item(action_row)
            
        await ctx.send(view=view)
    

    
    @spotify_group.command(name="searchartist", aliases=["artist", "sar"])
    @spotify_cooldown()
    async def search_artist(self, ctx: commands.Context, *, query: str):
        """Search for artists on Spotify
        
        Usage: ,spotify searchartist <query>
        Example: ,spotify searchartist Drake
        """
        if not self.spotify.is_authenticated():
            return await ctx.send(view=_sp_view(self.bot, "Not Authenticated", "Spotify API is not authenticated!", error=True))
        
        async with ctx.typing():
            artists = self.spotify.search_artists(query, limit=10)
            
            if not artists:
                return await ctx.send(view=_sp_view(self.bot, "Not Found", f"No artists found for '{query}'", error=True))
            
            description = []
            for i, artist in enumerate(artists[:10], 1):
                followers = self.spotify.format_number(artist['followers']['total'])
                genres = ", ".join(artist['genres'][:3]) if artist.get('genres') else 'N/A'
                popularity = artist.get('popularity', 0)
                
                pop_bar = "█" * (popularity // 10) + "░" * (10 - popularity // 10)
                
                artist_info = (
                    f"**{i}. [{artist['name']}]({artist['external_urls']['spotify']})**\n"
                    f"   Followers: {followers}\n"
                    f"   Popularity: {pop_bar} {popularity}%\n"
                )
                if genres != 'N/A':
                    artist_info += f"   Genres: {genres}\n"
                
                description.append(artist_info)
            
            view = discord.ui.LayoutView(timeout=30)
            container = discord.ui.Container(accent_colour=discord.Colour(0x1DB954))
            container.add_item(discord.ui.TextDisplay(f"### Artist Search: '{query}'"))
            container.add_item(discord.ui.Separator())
            container.add_item(discord.ui.TextDisplay("\n".join(description)))
            container.add_item(discord.ui.TextDisplay(f"-# Showing {len(artists)} results"))
            view.add_item(container)
            
        await ctx.send(view=view)
    
    @spotify_group.command(name="login", aliases=["link", "connect"])
    @spotify_cooldown()
    async def login(self, ctx: commands.Context, *, profile_url: str):
        """Link your Spotify profile to view and play your playlists
        
        Usage: ,spotify login <profile url or username>
        Example: ,spotify login https://open.spotify.com/user/yourname
        """
        if not self.spotify.is_authenticated():
            return await ctx.send(view=_sp_view(self.bot, "Not Authenticated", "Spotify API is not authenticated!", error=True))
        
        async with ctx.typing():
            # Get user profile
            user = self.spotify.get_user_profile(profile_url)
            
            if not user:
                return await ctx.send(view=_sp_view(self.bot, "Not Found", "Could not find that Spotify profile. Make sure the URL or username is correct.", error=True))
            
            # Save to database
            await self.bot.spotify_profiles_col.update_one(
                {"discord_id": ctx.author.id},
                {
                    "$set": {
                        "discord_id": ctx.author.id,
                        "spotify_id": user['id'],
                        "spotify_display_name": user.get('display_name', user['id']),
                        "spotify_url": user['external_urls']['spotify']
                    }
                },
                upsert=True
            )
            
            view = _sp_view(
                self.bot, "Spotify Profile Linked",
                f"Successfully linked your Discord account to Spotify profile **{user.get('display_name', user['id'])}**\n\n"
                f"-# Use `,spotify myplaylists` to view and play your Spotify playlists!"
            )
            
        await ctx.send(view=view)
    
    @spotify_group.command(name="logout", aliases=["unlink", "disconnect"])
    @spotify_cooldown()
    async def logout(self, ctx: commands.Context):
        """Unlink your Spotify profile from your Discord account
        
        Usage: ,spotify logout
        """
        # Check if user has a linked profile
        profile = await self.bot.spotify_profiles_col.find_one({"discord_id": ctx.author.id})
        
        if not profile:
            return await ctx.send(view=_sp_view(self.bot, "Not Linked", "You don't have a linked Spotify profile!", error=True))
        
        # Delete from database
        await self.bot.spotify_profiles_col.delete_one({"discord_id": ctx.author.id})
        
        view = _sp_view(
            self.bot, "Spotify Profile Unlinked",
            f"Successfully unlinked your Spotify profile **{profile['spotify_display_name']}** from your Discord account."
        )
        
        await ctx.send(view=view)
    
    @spotify_group.command(name="myplaylists", aliases=["mpl", "playlists"])
    @spotify_cooldown()
    @in_voice()
    async def my_playlists(self, ctx: commands.Context):
        """View and play your Spotify playlists
        
        Usage: ,spotify myplaylists
        Note: You must link your profile first with ,spotify login
        """
        if not self.spotify.is_authenticated():
            return await ctx.send(view=_sp_view(self.bot, "Not Authenticated", "Spotify API is not authenticated!", error=True))
        
        # Check if user has linked their profile
        profile = await self.bot.spotify_profiles_col.find_one({"discord_id": ctx.author.id})
        
        if not profile:
            return await ctx.send(view=_sp_view(
                self.bot, "Not Linked",
                "You haven't linked your Spotify profile yet!\n\n"
                "Use `,spotify login <your_profile_url>` to link your account.",
                error=True
            ))
        
        async with ctx.typing():
            # Get user's playlists
            playlists = self.spotify.get_user_playlists(profile['spotify_id'])
            
            if not playlists:
                return await ctx.send(view=_sp_view(self.bot, "No Playlists", "Could not fetch your playlists or you have no playlists.", error=True))
            
            # Import the view
            from utils.spotify_views import SpotifyPlaylistView
            
            view = discord.ui.LayoutView(timeout=180)
            container = discord.ui.Container(accent_colour=discord.Colour(0x1DB954))
            container.add_item(discord.ui.TextDisplay(f"### {profile['spotify_display_name']}'s Playlists"))
            container.add_item(discord.ui.Separator())
            container.add_item(discord.ui.TextDisplay(f"Found **{len(playlists)}** playlists. Select one from the dropdown to play it!"))
            view.add_item(container)
            
            await ctx.send(view=view)
            
            # Send dropdown separately (needs View with callbacks)
            playlist_view = SpotifyPlaylistView(playlists, ctx.author.id)
            await ctx.send(content="-# Select a playlist below:", view=playlist_view)

async def setup(bot):
    await bot.add_cog(Spotify(bot))

