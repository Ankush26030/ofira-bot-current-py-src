import discord
import wavelink
from config import Config
from utils.embeds import create_error_embed
from player import CustomPlayer, safe_connect

class PlaylistInfoView(discord.ui.View):
    """View for Spotify playlist info with Play button"""
    
    def __init__(self, playlist_url, playlist_name, user_id):
        super().__init__(timeout=180)
        self.playlist_url = playlist_url
        self.playlist_name = playlist_name
        self.user_id = user_id
    
    @discord.ui.button(label="Play Playlist", style=discord.ButtonStyle.success, emoji="▶️")
    async def play_playlist_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle play playlist button click"""
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message(
                f"{Config.EMOJI_CROSS} This is not your playlist!",
                ephemeral=True
            )
        
        # Check if user is in voice
        if not interaction.user.voice:
            return await interaction.response.send_message(
                embed=create_error_embed("You need to be in a voice channel!"),
                ephemeral=True
            )
        
        # Connect to voice if needed
        if not interaction.guild.voice_client:
            try:
                vc = await safe_connect(interaction.user.voice.channel)
                vc.text_channel = interaction.channel
            except Exception as e:
                return await interaction.response.send_message(
                    embed=create_error_embed(f"Failed to join voice channel: {e}"),
                    ephemeral=True
                )
        
        vc: CustomPlayer = interaction.guild.voice_client
        
        # Check if user is in same channel
        if vc.channel != interaction.user.voice.channel:
            return await interaction.response.send_message(
                embed=create_error_embed("You must be in the same voice channel as me!"),
                ephemeral=True
            )
        
        await interaction.response.defer()
        
        # Search for the playlist on wavelink
        try:
            tracks = await wavelink.Playable.search(self.playlist_url)
            
            if not tracks:
                return await interaction.followup.send(
                    embed=create_error_embed("Could not load playlist tracks."),
                    ephemeral=True
                )
            
            # Handle playlist
            if isinstance(tracks, wavelink.Playlist):
                # Filter tracks < 30 seconds
                valid_tracks = []
                for track in tracks:
                    if track.is_stream or track.length >= 30000:
                        track.requester = interaction.user
                        valid_tracks.append(track)
                
                if not valid_tracks:
                    return await interaction.followup.send(
                        embed=create_error_embed("All tracks in this playlist are shorter than 30 seconds!"),
                        ephemeral=True
                    )
                
                for track in valid_tracks:
                    await vc.queue.put_wait(track)
                
                added = len(valid_tracks)
                skipped = len(tracks) - added
                
                desc = f"{Config.EMOJI_TICK} Added Spotify playlist **{self.playlist_name}** ({added} tracks) to queue"
                if skipped > 0:
                    desc += f"\n⚠️ Skipped {skipped} tracks (< 30s)"
                
                embed = discord.Embed(
                    description=desc,
                    color=Config.SUCCESS_COLOR
                )
                
                await interaction.followup.send(embed=embed)
                
                if not vc.playing:
                    await vc.play(await vc.queue.get_wait())
            else:
                return await interaction.followup.send(
                    embed=create_error_embed("Expected a playlist but got individual tracks."),
                    ephemeral=True
                )
                
        except Exception as e:
            await interaction.followup.send(
                embed=create_error_embed(f"Error loading playlist: {str(e)}"),
                ephemeral=True
            )

class SpotifyPlaylistSelect(discord.ui.Select):
    """Dropdown for selecting Spotify playlists to play"""
    
    def __init__(self, playlists, user_id):
        self.user_id = user_id
        self.playlists_data = playlists
        
        options = []
        for i, playlist in enumerate(playlists[:25]):  # Discord limit is 25 options
            # Create option
            option = discord.SelectOption(
                label=playlist['name'][:100],  # Max 100 chars
                description=f"{playlist['tracks']['total']} tracks" if playlist.get('tracks') else "Playlist",
                value=str(i),
                emoji="🎵"
            )
            options.append(option)
        
        super().__init__(
            placeholder="Select a playlist to play...",
            min_values=1,
            max_values=1,
            options=options
        )
    
    async def callback(self, interaction: discord.Interaction):
        """Handle playlist selection"""
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message(
                f"{Config.EMOJI_CROSS} This is not your playlist menu!",
                ephemeral=True
            )
        
        # Get selected playlist
        selected_index = int(self.values[0])
        playlist = self.playlists_data[selected_index]
        playlist_url = playlist['external_urls']['spotify']
        
        # Check if user is in voice
        if not interaction.user.voice:
            return await interaction.response.send_message(
                embed=create_error_embed("You need to be in a voice channel!"),
                ephemeral=True
            )
        
        # Connect to voice if needed
        if not interaction.guild.voice_client:
            try:
                vc = await safe_connect(interaction.user.voice.channel)
                vc.text_channel = interaction.channel
            except Exception as e:
                return await interaction.response.send_message(
                    embed=create_error_embed(f"Failed to join voice channel: {e}"),
                    ephemeral=True
                )
        
        vc: CustomPlayer = interaction.guild.voice_client
        
        # Check if user is in same channel
        if vc.channel != interaction.user.voice.channel:
            return await interaction.response.send_message(
                embed=create_error_embed("You must be in the same voice channel as me!"),
                ephemeral=True
            )
        
        await interaction.response.defer()
        
        # Search for the playlist on wavelink
        try:
            tracks = await wavelink.Playable.search(playlist_url)
            
            if not tracks:
                return await interaction.followup.send(
                    embed=create_error_embed("Could not load playlist tracks."),
                    ephemeral=True
                )
            
            # Handle playlist
            if isinstance(tracks, wavelink.Playlist):
                # Filter tracks < 30 seconds
                valid_tracks = []
                for track in tracks:
                    if track.is_stream or track.length >= 30000:
                        track.requester = interaction.user
                        valid_tracks.append(track)
                
                if not valid_tracks:
                    return await interaction.followup.send(
                        embed=create_error_embed("All tracks in this playlist are shorter than 30 seconds!"),
                        ephemeral=True
                    )
                
                for track in valid_tracks:
                    await vc.queue.put_wait(track)
                
                added = len(valid_tracks)
                skipped = len(tracks) - added
                
                desc = f"{Config.EMOJI_TICK} Added Spotify playlist **{playlist['name']}** ({added} tracks) to queue"
                if skipped > 0:
                    desc += f"\n⚠️ Skipped {skipped} tracks (< 30s)"
                
                embed = discord.Embed(
                    description=desc,
                    color=Config.SUCCESS_COLOR
                )
                
                await interaction.followup.send(embed=embed)
                
                if not vc.playing:
                    await vc.play(await vc.queue.get_wait())
            else:
                return await interaction.followup.send(
                    embed=create_error_embed("Expected a playlist but got individual tracks."),
                    ephemeral=True
                )
                
        except Exception as e:
            await interaction.followup.send(
                embed=create_error_embed(f"Error loading playlist: {str(e)}"),
                ephemeral=True
            )

class SpotifyPlaylistView(discord.ui.View):
    """View for Spotify playlist selection"""
    
    def __init__(self, playlists, user_id):
        super().__init__(timeout=180)
        self.add_item(SpotifyPlaylistSelect(playlists, user_id))

class SpotifyProfileView(discord.ui.View):
    """View for Spotify profile interactions"""
    
    def __init__(self, spotify_helper, target_user_id):
        super().__init__(timeout=180)
        self.spotify = spotify_helper
        self.target_user_id = target_user_id

    @discord.ui.button(label="Playlists", style=discord.ButtonStyle.success, emoji="🎵")
    async def playlists_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle playlists button click"""
        await interaction.response.defer(ephemeral=True)
        
        # Get playlists
        playlists = self.spotify.get_user_playlists(self.target_user_id)
        
        if not playlists:
            return await interaction.followup.send(
                "Could not find any public playlists for this user.", 
                ephemeral=True
            )
            
        # Create view for playlists
        view = SpotifyPlaylistView(playlists, interaction.user.id)
        
        await interaction.followup.send(
            content=f"Found **{len(playlists)}** public playlists.",
            view=view,
            ephemeral=True
        )
