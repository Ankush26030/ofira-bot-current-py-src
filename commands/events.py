import discord
from discord.ext import commands
import wavelink
import time
import asyncio
from player import CustomPlayer, safe_connect
from utils.views import NowPlayingView
from utils.music_card import generate_music_card

class Events(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._update_tasks: dict[int, asyncio.Task] = {}  # guild_id -> task
        self._rejoin_cooldowns: dict[int, float] = {}  # guild_id -> last rejoin attempt timestamp
        self._rejoin_attempts: dict[int, int] = {}  # guild_id -> consecutive fail count
        self._rejoin_in_progress: set[int] = set()  # guild_ids currently being rejoined

    def cog_unload(self):
        for task in self._update_tasks.values():
            task.cancel()
        self._update_tasks.clear()

    def _cancel_update_task(self, guild_id: int):
        task = self._update_tasks.pop(guild_id, None)
        if task and not task.done():
            task.cancel()

    async def _update_np_loop(self, player: CustomPlayer, guild_id: int):
        """Background loop: update the NP music card every 30 seconds."""
        try:
            while True:
                await asyncio.sleep(30)

                if not player or not player.current or not player.connected:
                    break
                if player.paused:
                    continue
                if not player.np_message:
                    break

                try:
                    card_file = await generate_music_card(
                        player.current,
                        position=player.position,
                        requester=getattr(player.current, 'requester', None),
                    )
                    new_view = NowPlayingView(player, card_file)
                    await player.np_message.edit(attachments=[card_file], view=new_view)
                except discord.NotFound:
                    player.np_message = None
                    break
                except Exception:
                    pass
        except asyncio.CancelledError:
            pass

    @commands.Cog.listener()
    async def on_wavelink_track_start(self, payload: wavelink.TrackStartEventPayload):
        player: CustomPlayer = payload.player
        if not player:
            return

        # Use the track from the payload (more reliable than player.current which can be None)
        track = payload.track or player.current
        if not track:
            print("[TRACK_START] No track available, skipping NP card")
            return

        guild_id = player.guild.id
        self._cancel_update_task(guild_id)

        # Successfully playing = reset rejoin failure counters for this guild
        self._rejoin_attempts.pop(guild_id, None)
        self._rejoin_cooldowns.pop(guild_id, None)

        # Add to history
        player.add_to_history(payload.track)

        # Delete previous now playing message
        if player.np_message:
            old_msg = player.np_message
            player.np_message = None  # Clear reference immediately to prevent duplicates
            try:
                await old_msg.delete()
            except discord.HTTPException:
                pass

        # Generate music card and build LayoutView
        card_file = await generate_music_card(
            track,
            position=0,
            requester=getattr(track, 'requester', None),
        )
        view = NowPlayingView(player, card_file)
        
        # Determine channel to send NP message
        channel = getattr(player, 'home', None)
        
        if hasattr(player, 'text_channel'):
             channel = player.text_channel
        
        if channel:
            player.np_message = await channel.send(view=view, file=card_file)

        # Start progress update loop
        self._update_tasks[guild_id] = asyncio.create_task(
            self._update_np_loop(player, guild_id)
        )

        # Update Voice Channel Status
        if player.channel:
            try:
                status = f"<a:music_2:1245071479435952279> {track.title} - {track.author}"[:100]
                await player.channel.edit(status=status)
            except Exception:
                pass

    @commands.Cog.listener()
    async def on_wavelink_track_exception(self, payload: wavelink.TrackExceptionEventPayload):
        """Log the actual Lavalink exception when a track fails to load."""
        player = payload.player
        track = payload.track
        exception = payload.exception
        title = getattr(track, 'title', 'Unknown') if track else 'Unknown'
        print(f"[TRACK_EXCEPTION] Track '{title}' failed: {exception}")

    @commands.Cog.listener()
    async def on_wavelink_track_end(self, payload: wavelink.TrackEndEventPayload):
        """Handle track end - play next track from queue or autoplay"""
        player: CustomPlayer = payload.player
        if not player:
            return

        print(f"[TRACK_END] reason={payload.reason}, queue_empty={player.queue.is_empty}, queue_size={len(player.queue)}")

        # Cancel the progress update loop for this guild
        self._cancel_update_task(player.guild.id)
            
        # Check if we forced a stop (e.g. from empty VC)
        if getattr(player, 'forcing_stop', False):
            player.forcing_stop = False # Reset flag
            return # Don't play next, don't send queue ended message, etc.

        # CRITICAL FIX: Ignore REPLACED (seeking/skipping causing replace)
        # We only want to auto-play next if the track FINISHED naturally, errored, or was STOPPED (by skip)
        # If we ignore STOPPED, the 'skip' command (which stops the track) will fail to play the next song.
        if payload.reason.upper() in ["REPLACED", "CLEANUP"]:
            return
            
        # For STOPPED, we proceed, because 'skip' triggers STOPPED.
        # But if it was a manual ',stop' (queue cleared), play_next will just find empty queue and finish.
        # If it was Empty VC stop, 'forcing_stop' above handles it.


        # Detect load failures and pass to play_next for retry limiting
        is_load_failed = payload.reason.upper() == "LOADFAILED"
        
        if is_load_failed:
            # Delay before retrying to prevent tight spam loop
            await asyncio.sleep(1.5)
            print(f"[TRACK_END] Track failed to load, retrying with backoff...")
        
        # Call the play_next method
        print(f"[TRACK_END] Calling play_next...")
        await player.play_next(track=payload.track, failed=is_load_failed)
        
        # Check if queue has ended
        await asyncio.sleep(0.5)
        
        if player.queue.is_empty and not player.playing and not player.autoplay_enabled:
            # Queue finished
            if hasattr(player, 'np_message') and player.np_message:
                try:
                    await player.np_message.delete()
                    player.np_message = None
                except discord.HTTPException:
                    pass
            
            # Send queue ended message
            if hasattr(player, 'text_channel') and player.text_channel:
                embed = discord.Embed(
                    description="🎵 **Queue ended!** Thanks for listening!\n\nUse `,play <song>` to start playing again.",
                    color=self.bot.config.EMBED_COLOR
                )
                try:
                    await player.text_channel.send(embed=embed)
                except:
                    pass
            
            # Clear voice channel status
            if player.channel:
                try:
                    await player.channel.edit(status=None)
                except:
                    pass

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        # 1. Bot Disconnect Check (Must be first, because guild.voice_client might be None)
        if member.id == self.bot.user.id and after.channel is None:
            guild_id = member.guild.id

            # Check for 24/7 Mode - Auto Rejoin Strategy
            try:
                # --- Anti-loop guard: skip if rejoin is already in progress for this guild ---
                if guild_id in self._rejoin_in_progress:
                    print(f"[24/7] Skipping rejoin for guild {guild_id} - already in progress")
                    return

                # --- Anti-loop guard: cooldown (60s between attempts) ---
                now = time.time()
                last_attempt = self._rejoin_cooldowns.get(guild_id, 0)
                if (now - last_attempt) < 60:
                    print(f"[24/7] Skipping rejoin for guild {guild_id} - cooldown active ({int(60 - (now - last_attempt))}s remaining)")
                    return

                # --- Anti-loop guard: max 3 consecutive failures ---
                attempts = self._rejoin_attempts.get(guild_id, 0)
                if attempts >= 3:
                    print(f"[24/7] Skipping rejoin for guild {guild_id} - max retries ({attempts}) reached, waiting for cooldown reset")
                    # Reset after 5 minutes of backing off
                    if (now - last_attempt) >= 300:
                        self._rejoin_attempts[guild_id] = 0
                    return

                data = await self.bot.settings_col.find_one({"guild_id": guild_id})
                if data and data.get("247", False):
                    saved_channel_id = data.get("voice_channel_id")
                    if saved_channel_id:
                        # Mark rejoin in progress
                        self._rejoin_in_progress.add(guild_id)
                        self._rejoin_cooldowns[guild_id] = now

                        try:
                            # Wait 5 seconds to ensure it wasn't a valid "247 off" command or intentional shutdown
                            await asyncio.sleep(5)

                            # Re-check if 24/7 is STILL on
                            data = await self.bot.settings_col.find_one({"guild_id": guild_id})
                            if not (data and data.get("247", False)):
                                return

                            target_channel = self.bot.get_channel(saved_channel_id)
                            if not target_channel:
                                return

                            player = await safe_connect(target_channel)
                            player.text_channel = self.bot.get_channel(data.get("text_channel_id")) if data.get("text_channel_id") else None

                            # Success! Reset failure counter
                            self._rejoin_attempts.pop(guild_id, None)

                            # Send notification
                            try:
                                embed = discord.Embed(
                                    description=f"🔄 **24/7 Mode Active:** Auto-rejoining <#{saved_channel_id}>...",
                                    color=self.bot.config.SUCCESS_COLOR
                                )
                                if player.text_channel:
                                    await player.text_channel.send(embed=embed)
                            except:
                                pass

                        except Exception as e:
                            # Increment failure counter
                            self._rejoin_attempts[guild_id] = self._rejoin_attempts.get(guild_id, 0) + 1
                            print(f"[24/7] Failed to auto-rejoin guild {guild_id} (attempt {self._rejoin_attempts[guild_id]}/3): {e}")
                        finally:
                            # Always release the in-progress lock
                            self._rejoin_in_progress.discard(guild_id)

            except Exception as e:
                self._rejoin_in_progress.discard(guild_id)
                print(f"[24/7] Error in auto-rejoin logic for guild {guild_id}: {e}")
            
            return

        # 2. Get Player for other checks
        player: CustomPlayer = member.guild.voice_client
        if not player:
            return

        # Bot Joined Logic (Fresh Connect)
        if member.id == self.bot.user.id and before.channel is None and after.channel is not None:
             # Logic similar to move, but specifically for initial join
            now = time.time()
            player.last_move_time = now # enable grace period
            
             # Update player channel reference immediately
            try:
                player.channel = after.channel
            except:
                pass
            
            # Cancel disconnects
            player.waiting_to_disconnect = False
            player.disconnect_token = time.monotonic()
            
             # Update 24/7 Channel ID if enabled
            data = await self.bot.settings_col.find_one({"guild_id": member.guild.id})
            if data and data.get("247", False):
                await self.bot.settings_col.update_one(
                    {"guild_id": member.guild.id},
                    {"$set": {"voice_channel_id": after.channel.id}}
                )
            
            return

        # Bot Moved Logic
        if member.id == self.bot.user.id and before.channel and after.channel and before.channel != after.channel:
            # Check if 24/7 is enabled
            data = await self.bot.settings_col.find_one({"guild_id": member.guild.id})
            if data and data.get("247", False):
                saved_channel_id = data.get("voice_channel_id")
                
                # If we are moved AWAY from the saved channel, GO BACK!
                if saved_channel_id and after.channel.id != saved_channel_id:
                    # Notify
                    if hasattr(player, 'text_channel') and player.text_channel:
                         try:
                            embed = discord.Embed(
                                description=f"⚠️ **24/7 Mode is Active!** I cannot be moved from <#{saved_channel_id}>.",
                                color=self.bot.config.ERROR_COLOR
                            )
                            await player.text_channel.send(embed=embed)
                         except:
                             pass
                    
                    # Force Reconnect to Original Channel
                    try:
                        target_channel = self.bot.get_channel(saved_channel_id)
                        if target_channel:
                            # Save current state (Queue & Track)
                            current_track = player.current
                            params = []
                            if hasattr(player, 'queue'):
                                # queue is wavelink.Queue, iterable
                                params = list(player.queue)

                            # Reconnect with fresh session via safe_connect
                            player = await safe_connect(target_channel)
                            player.text_channel = self.bot.get_channel(data.get("text_channel_id")) if data.get("text_channel_id") else None

                            # Restore Queue
                            if params:
                                for track in params:
                                    await player.queue.put_wait(track)
                            
                            # Resume playback
                            if current_track:
                                await player.play(current_track)
                        return # Exit function, don't run other move logic
                    except Exception as e:
                        print(f"Failed to move back to 24/7 channel: {e}")

            # Send notification (Rate limited 10s)
            last_move_msg = getattr(player, 'last_move_msg_time', 0)
            now = time.time()
            
            if (now - last_move_msg) > 10:
                if hasattr(player, 'text_channel') and player.text_channel:
                    try:
                        embed = discord.Embed(
                            description=f"🔄 I was moved to **{after.channel.name}**!",
                            color=self.bot.config.EMBED_COLOR
                        )
                        await player.text_channel.send(embed=embed)
                        player.last_move_msg_time = now
                    except:
                        pass
            
            # Set move notification timestamp
            player.last_move_time = now

            # CRITICAL: Manually update player.channel reference so checks view the NEW channel
            # This fixes "Everyone left" triggering because it was looking at the old channel
            try:
                player.channel = after.channel
            except:
                pass
                
            # Cancel any pending disconnect flags
            player.waiting_to_disconnect = False
            
            # CRITICAL: Invalidate any running disconnect tasks (like the 30s timer from previous VC)
            player.disconnect_token = time.monotonic()
            
            # Ensure playing continues & Force Resync audio
            if player.playing:
                try:
                    await player.pause(True)
                    await asyncio.sleep(0.5)
                    await player.pause(False)
                except Exception as e:
                    print(f"DEBUG: Failed to resync audio on move: {e}")
                    try:
                         # If pause failed (likely 404), reconnect session
                         current = player.current
                         player = await safe_connect(after.channel)
                         if current:
                            await player.play(current)
                    except:
                        pass
            elif player.paused:
                await player.pause(False)

            # NOTE: We DO NOT update 24/7 channel here anymore. It sticks to the original one.


        # If the bot is not in a channel, ignore
        if not player.channel:
            return

        # Check if 24/7 is enabled
        data = await self.bot.settings_col.find_one({"guild_id": member.guild.id})
        is_247 = data.get("247", False) if data else False
            
        # Check members (excluding bots)
        members = [m for m in player.channel.members if not m.bot]
        
        # USERS PRESENT: Reset Logic
        if len(members) > 0:
            player.waiting_to_disconnect = False
            # Generate a new token to invalidate any running disconnect tasks
            player.disconnect_token = time.monotonic()
            return

        # CHANNEL EMPTY: Logic
        if len(members) == 0:
            # GRACE PERIOD: If bot was moved recently (< 10s), wait and re-check
            # Instead of returning immediately, we wait 12s then verify if it's still empty.
            if (time.time() - getattr(player, 'last_move_time', 0)) < 10:
                await asyncio.sleep(12)
                
                # Re-verify state after wait
                if not player.channel:
                    return
                members = [m for m in player.channel.members if not m.bot]
                if len(members) > 0:
                    return # Users arrived during wait

                if len(members) > 0:
                    return # Users arrived during wait

            # Check if we are already handling an empty channel event
            if getattr(player, 'waiting_to_disconnect', False):
                return
            
            # Set flag to prevent multiple triggers
            player.waiting_to_disconnect = True
            
            # Generate a unique token for THIS task
            task_token = time.monotonic()
            player.disconnect_token = task_token
            
            # Case 1: Music IS playing
            if player.playing:
                # Stop music IMMEDIATELY (User request: "GANA BAND HOJAYE")
                player.forcing_stop = True
                player.queue.clear()
                try:
                    await player.stop()
                except:
                    pass
                
                # 24/7 Handling after stop
                if is_247:
                    # Notify and stay
                    stopped_embed = discord.Embed(
                        description="⏹️ Everyone left... Music stopped.\n\n*24/7 mode is enabled - staying in voice channel*",
                        color=self.bot.config.EMBED_COLOR
                    )
                    
                    if hasattr(player, 'np_message') and player.np_message:
                        try:
                            await player.np_message.delete()
                            player.np_message = None
                        except:
                            pass
                            
                    if hasattr(player, 'text_channel') and player.text_channel:
                        try:
                            await player.text_channel.send(embed=stopped_embed)
                        except:
                            pass
                            
                    if player.channel:
                        try:
                            await player.channel.edit(status=None)
                        except:
                            pass
                    
                    # Keep lock True to prevent further notifications
                    return
                else:
                    # Not 24/7: Continue to leave logic (silent wait)
                    pass 

            # Case 2: Music NOT playing (or just stopped above)
            
            # If 24/7 mode and we are idle (not playing), do nothing and stay
            if is_247:
                # Just return. Lock stays True.
                return
            
            # If NOT 24/7: Wait 3 minutes (or remaining time)
            
            # Calculate remaining wait
            # If we played music, we waited 30s already.
            # If we didn't, we waited 0s.
            remaining_wait = 150 if player.playing else 180
            if not player.playing and not getattr(player, 'forcing_stop', False): 
                 remaining_wait = 180
            
            await asyncio.sleep(remaining_wait)
            
            # TASK VALIDITY CHECK AGAIN
            current_token_on_player = getattr(player, 'disconnect_token', 0)
            if current_token_on_player != task_token:
                return # Abort
            
            # Recheck
            player = member.guild.voice_client
            if not player or not player.channel:
                return
            members = [m for m in player.channel.members if not m.bot]
            if len(members) > 0:
                player.waiting_to_disconnect = False
                return
                
            # Leave
            leaving_embed = discord.Embed(
                description="😔 No one came back... Leaving the voice channel!",
                color=self.bot.config.EMBED_COLOR
            )
            
            if hasattr(player, 'np_message') and player.np_message:
                try:
                    await player.np_message.delete()
                except:
                    pass
            
            if hasattr(player, 'text_channel') and player.text_channel:
                try:
                    await player.text_channel.send(embed=leaving_embed)
                except:
                    pass
            
            await player.disconnect()                
async def setup(bot):
    await bot.add_cog(Events(bot))
