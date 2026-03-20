import wavelink
from wavelink.exceptions import LavalinkException
from typing import Optional
import logging as _logging
import random
import logging
import asyncio
import discord

logger = logging.getLogger(__name__)


async def safe_connect(channel: discord.VoiceChannel, *, timeout: float = 30) -> "CustomPlayer":
    """Safely connect to a voice channel, handling stale Lavalink sessions.
    
    This is the single entry point for ALL voice connections. It handles:
    1. Cleaning up any existing stale voice client
    2. Destroying orphaned Lavalink sessions
    3. Connecting with proper error recovery
    
    Returns the connected CustomPlayer on success, raises on failure.
    """
    guild = channel.guild

    # Step 1: Clean up any existing voice client
    if guild.voice_client:
        try:
            await guild.voice_client.disconnect(force=True)
        except Exception:
            pass
        await asyncio.sleep(0.5)

    # Step 2: Destroy any stale Lavalink session for this guild
    try:
        node = wavelink.Pool.get_node()
        await node._destroy_player(guild.id)
    except Exception:
        pass  # Session may not exist, that's fine

    # Step 3: Connect
    try:
        player: CustomPlayer = await channel.connect(cls=CustomPlayer, timeout=timeout)
        return player
    except Exception as first_err:
        logger.warning("First connect attempt failed for guild %s: %s. Retrying...", guild.id, first_err)

        # Clean up again in case the failed attempt left a partial state
        if guild.voice_client:
            try:
                await guild.voice_client.disconnect(force=True)
            except Exception:
                pass

        try:
            node = wavelink.Pool.get_node()
            await node._destroy_player(guild.id)
        except Exception:
            pass

        await asyncio.sleep(1)

        # Step 4: Retry once
        player: CustomPlayer = await channel.connect(cls=CustomPlayer, timeout=timeout)
        return player


class CustomPlayer(wavelink.Player):
    """Custom player with queue, autoplay, and loop functionality"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.queue: wavelink.Queue = wavelink.Queue()
        self.history: list[wavelink.Playable] = []
        self.loop_mode: str = "off"  # off, track, queue
        self.autoplay_enabled: bool = False
        self.np_message: Optional[discord.Message] = None
        self._autoplay_fails: int = 0  # consecutive autoplay failures

    async def _dispatch_voice_update(self) -> None:
        """Override to include channelId which Lavalink v4 requires.
        
        Key fix: On stale session errors, we destroy and retry. If the retry
        also fails, we disconnect BUT still need to avoid leaving connect()
        hanging — so we never return without either setting the event or
        disconnecting (which clears it).
        """
        assert self.guild is not None
        data = self._voice_state["voice"]

        session_id = data.get("session_id", None)
        token = data.get("token", None)
        endpoint = data.get("endpoint", None)

        if not session_id or not token or not endpoint:
            return

        # Include channelId - Lavalink v4 requires this field
        channel_id = str(self.channel.id) if self.channel else None
        request = {
            "voice": {
                "sessionId": session_id,
                "token": token,
                "endpoint": endpoint,
                "channelId": channel_id,
            }
        }

        try:
            await self.node._update_player(self.guild.id, data=request)
        except (LavalinkException, Exception) as first_err:
            # Stale/expired session — destroy it on Lavalink and retry once
            logger.warning(
                "Player %s voice update rejected (%s). Destroying and retrying...",
                self.guild.id, first_err,
            )
            try:
                await self.node._destroy_player(self.guild.id)
            except Exception:
                pass  # Destroy may also fail if session is already gone

            try:
                await self.node._update_player(self.guild.id, data=request)
            except Exception as retry_err:
                logger.error(
                    "Player %s retry also failed: %s — connection will fail.",
                    self.guild.id, retry_err,
                )
                # Do NOT call disconnect() here — it would deadlock or interfere
                # with the connect() flow. Instead, just return without setting
                # _connection_event. The connect() call will time out on its own,
                # but we reduce the timeout pain by letting it happen naturally.
                return

        self._connection_event.set()
        logger.debug("Player %s is dispatching VOICE_UPDATE.", self.guild.id)
        
    async def _refresh_track(self, track: wavelink.Playable) -> wavelink.Playable | None:
        """Re-search a track to get a fresh stream URL from Lavalink.
        
        Returns the refreshed track or None if re-search fails.
        """
        try:
            source = getattr(self.client, 'search_source', 'ytsearch')
            query = f"{source}:{track.title} - {track.author}"
            results = await wavelink.Playable.search(query)
            if results:
                fresh = results[0]
                # Preserve the original requester
                if hasattr(track, 'requester'):
                    fresh.requester = track.requester
                return fresh
        except Exception as e:
            print(f"[REFRESH] Failed to refresh track '{track.title}': {e}")
        return None

    async def play_next(self, track: Optional[wavelink.Playable] = None, *, failed: bool = False) -> None:
        """Play the next track based on loop mode and queue"""
        # If track is passed (from on_track_end), use it as reference for looping/autoplay
        # If not passed, try to use self.current (though it might be None if track ended)
        reference_track = track or self.current
        
        print(f"[PLAY_NEXT] loop_mode={self.loop_mode}, queue_empty={self.queue.is_empty}, queue_size={len(self.queue)}, connected={self.connected}")
        
        # If the previous track failed to load, track consecutive failures
        if failed:
            self._autoplay_fails += 1
            if self._autoplay_fails >= 3:
                print(f"[PLAY_NEXT] Too many consecutive failures ({self._autoplay_fails}), stopping autoplay attempts")
                self._autoplay_fails = 0
                return
        else:
            self._autoplay_fails = 0
        
        if self.loop_mode == "track" and reference_track:
            # If the track just failed, re-search it to get a fresh stream URL
            if failed:
                print(f"[PLAY_NEXT] Loop track failed, re-searching for fresh URL...")
                fresh = await self._refresh_track(reference_track)
                if fresh:
                    await self.play(fresh)
                    return
                else:
                    print(f"[PLAY_NEXT] Could not refresh track, skipping loop replay")
                    return
            # Replay current track
            await self.play(reference_track)
            return
            
        if self.loop_mode == "queue" and reference_track:
            # Add current track back to queue
            await self.queue.put_wait(reference_track)
        
        if not self.queue.is_empty:
            # Play next track from queue
            next_track = await self.queue.get_wait()
            print(f"[PLAY_NEXT] Playing next: {next_track.title}")
            try:
                await self.play(next_track)
            except Exception as e:
                print(f"[PLAY_NEXT] ERROR playing next track: {e}")
                # Track object may have a stale stream URL, try refreshing it
                print(f"[PLAY_NEXT] Attempting to refresh track...")
                fresh = await self._refresh_track(next_track)
                if fresh:
                    try:
                        await self.play(fresh)
                    except Exception as e2:
                        print(f"[PLAY_NEXT] Refreshed track also failed: {e2}")
                else:
                    print(f"[PLAY_NEXT] Could not refresh track, skipping")
        elif self.autoplay_enabled:
            # Autoplay: fetch recommended tracks
            # Use reference track or last track from history
            ref = reference_track or (self.history[-1] if self.history else None)
            
            if ref:
                try:
                    # Construct search query based on source
                    if ref.source == "youtube":
                         query = f"https://www.youtube.com/watch?v={ref.identifier}&list=RD{ref.identifier}"
                    else:
                         source = getattr(self.client, 'search_source', 'ytsearch')
                         query = f"{source}:{ref.title} - {ref.author}"
                         
                    recommended = await wavelink.Playable.search(query)
                    
                    if recommended and len(recommended) > 1:
                        # Play a random recommended track (skip first as it's usually the same)
                        next_track = random.choice(recommended[1:min(5, len(recommended))])
                        await self.play(next_track)
                except Exception as e:
                    print(f"Autoplay error: {e}")
                    self._autoplay_fails += 1
        else:
            print(f"[PLAY_NEXT] Nothing to play")
    
    def toggle_loop(self) -> str:
        """Toggle loop mode: off -> track -> queue -> off"""
        modes = ["off", "track", "queue"]
        current_index = modes.index(self.loop_mode)
        self.loop_mode = modes[(current_index + 1) % len(modes)]
        return self.loop_mode
    
    def toggle_autoplay(self) -> bool:
        """Toggle autoplay mode"""
        self.autoplay_enabled = not self.autoplay_enabled
        return self.autoplay_enabled
    
    def add_to_history(self, track: wavelink.Playable) -> None:
        """Add track to history (max 50 tracks)"""
        self.history.append(track)
        if len(self.history) > 50:
            self.history.pop(0)
