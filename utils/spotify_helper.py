import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from config import Config
import re

class SpotifyHelper:
    """Helper class for Spotify API interactions"""
    
    def __init__(self):
        """Initialize Spotify client with credentials"""
        self.client = None
        self.authenticated = False
        self._initialize()
    
    def _initialize(self):
        """Initialize the Spotify client"""
        try:
            if not Config.SPOTIFY_CLIENT_ID or not Config.SPOTIFY_CLIENT_SECRET:
                print("WARNING: Spotify credentials not configured")
                return
            
            auth_manager = SpotifyClientCredentials(
                client_id=Config.SPOTIFY_CLIENT_ID,
                client_secret=Config.SPOTIFY_CLIENT_SECRET
            )
            self.client = spotipy.Spotify(auth_manager=auth_manager)
            self.authenticated = True
            print("✓ Spotify API initialized successfully")
        except Exception as e:
            print(f"ERROR: Failed to initialize Spotify API: {e}")
            self.authenticated = False
    
    def is_authenticated(self):
        """Check if Spotify client is authenticated"""
        return self.authenticated
    
    def extract_id(self, url_or_id, type_='playlist'):
        """Extract Spotify ID from URL or return ID if already an ID"""
        if not url_or_id:
            return None
        
        # If it's already an ID (no slashes or dots), return it
        if '/' not in url_or_id and '.' not in url_or_id:
            return url_or_id
        
        # Extract from URL
        patterns = {
            'playlist': r'playlist/([a-zA-Z0-9]+)',
            'user': r'user/([a-zA-Z0-9]+)',
            'album': r'album/([a-zA-Z0-9]+)',
            'artist': r'artist/([a-zA-Z0-9]+)',
            'track': r'track/([a-zA-Z0-9]+)'
        }
        
        pattern = patterns.get(type_, r'([a-zA-Z0-9]+)')
        match = re.search(pattern, url_or_id)
        return match.group(1) if match else url_or_id
    
    def get_playlist(self, playlist_id):
        """Get playlist information"""
        if not self.authenticated:
            return None
        
        try:
            playlist_id = self.extract_id(playlist_id, 'playlist')
            return self.client.playlist(playlist_id)
        except Exception as e:
            print(f"Error getting playlist: {e}")
            return None
    
    def get_user_profile(self, user_id):
        """Get user profile information"""
        if not self.authenticated:
            return None
        
        try:
            user_id = self.extract_id(user_id, 'user')
            return self.client.user(user_id)
        except Exception as e:
            print(f"Error getting user profile: {e}")
            return None
    
    def search_albums(self, query, limit=10):
        """Search for albums"""
        if not self.authenticated:
            return None
        
        try:
            results = self.client.search(q=query, type='album', limit=limit)
            return results.get('albums', {}).get('items', [])
        except Exception as e:
            print(f"Error searching albums: {e}")
            return None
    
    def search_artists(self, query, limit=10):
        """Search for artists"""
        if not self.authenticated:
            return None
        
        try:
            results = self.client.search(q=query, type='artist', limit=limit)
            return results.get('artists', {}).get('items', [])
        except Exception as e:
            print(f"Error searching artists: {e}")
            return None
    
    def search_tracks(self, query, limit=10):
        """Search for tracks"""
        if not self.authenticated:
            return None
        
        try:
            results = self.client.search(q=query, type='track', limit=limit)
            return results.get('tracks', {}).get('items', [])
        except Exception as e:
            print(f"Error searching tracks: {e}")
            return None
    
    def get_album(self, album_id):
        """Get album information"""
        if not self.authenticated:
            return None
        
        try:
            album_id = self.extract_id(album_id, 'album')
            return self.client.album(album_id)
        except Exception as e:
            print(f"Error getting album: {e}")
            return None
    
    def get_artist(self, artist_id):
        """Get artist information"""
        if not self.authenticated:
            return None
        
        try:
            artist_id = self.extract_id(artist_id, 'artist')
            return self.client.artist(artist_id)
        except Exception as e:
            print(f"Error getting artist: {e}")
            return None
    
    def format_number(self, num):
        """Format large numbers (e.g., 1000000 -> 1M)"""
        if num >= 1_000_000:
            return f"{num / 1_000_000:.1f}M"
        elif num >= 1_000:
            return f"{num / 1_000:.1f}K"
        return str(num)
    
    def get_user_playlists(self, user_id, limit=50):
        """Get user's playlists"""
        if not self.authenticated:
            return None
        
        try:
            user_id = self.extract_id(user_id, 'user')
            results = self.client.user_playlists(user_id, limit=limit)
            return results.get('items', [])
        except Exception as e:
            print(f"Error getting user playlists: {e}")
            return None
