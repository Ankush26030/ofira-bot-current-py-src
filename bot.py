import discord
from discord.ext import commands
import wavelink
import asyncio
import logging
from motor.motor_asyncio import AsyncIOMotorClient
from config import Config
from player import CustomPlayer, safe_connect
from utils.embeds import create_error_embed
import sys
import traceback

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

# ── ANSI Colors ──
class _C:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    CYAN    = "\033[36m"
    GREEN   = "\033[32m"
    YELLOW  = "\033[33m"
    RED     = "\033[31m"
    MAGENTA = "\033[35m"
    WHITE   = "\033[97m"

def _ts():
    from datetime import datetime as _dt
    return _dt.now().strftime("%H:%M:%S")

def _log(msg):      print(f"  {_C.DIM}{_ts()}{_C.RESET}  {_C.CYAN}│{_C.RESET}  {msg}")
def _ok(msg):       print(f"  {_C.DIM}{_ts()}{_C.RESET}  {_C.GREEN}│{_C.RESET}  {_C.GREEN}✓{_C.RESET} {msg}")
def _warn(msg):     print(f"  {_C.DIM}{_ts()}{_C.RESET}  {_C.YELLOW}│{_C.RESET}  {_C.YELLOW}⚠{_C.RESET} {msg}")
def _err(msg):      print(f"  {_C.DIM}{_ts()}{_C.RESET}  {_C.RED}│{_C.RESET}  {_C.RED}✗{_C.RESET} {msg}")
def _section(t):    print(f"\n  {_C.MAGENTA}{_C.BOLD}{'─' * 3} {t} {'─' * (40 - len(t))}{_C.RESET}")

class MusicBot(commands.AutoShardedBot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        
        # Get sharding configuration
        shard_count = Config.SHARD_COUNT
        cluster_id = Config.CLUSTER_ID
        cluster_count = Config.CLUSTER_COUNT
        
        # Calculate which shards this cluster should handle
        # We calculate this even for single clusters to ensure specific shard IDs are assigned
        # This prevents "Shard ID None" messages in logs
        shard_ids = None
        if shard_count:
            # Distribute shards across clusters
            shards_per_cluster = shard_count // cluster_count
            remainder = shard_count % cluster_count
            
            start_shard = cluster_id * shards_per_cluster + min(cluster_id, remainder)
            end_shard = start_shard + shards_per_cluster + (1 if cluster_id < remainder else 0)
            shard_ids = list(range(start_shard, end_shard))
        
        super().__init__(
            command_prefix=self.get_prefix,
            intents=intents,
            help_command=None,
            owner_ids=Config.OWNER_IDS,
            status=discord.Status.dnd,
            activity=discord.Activity(type=discord.ActivityType.listening, name=",help | ,play"),
            case_insensitive=True,
            shard_count=shard_count,  # Can be None (auto), or a number
            shard_ids=shard_ids,  # Only set for multi-cluster, otherwise None
            allowed_mentions=discord.AllowedMentions(
                everyone=False,  # Block @everyone / @here
                roles=False,     # Block @role pings
                users=False      # Show mentions but don't ping/notify
            )
        )
        
        # Store cluster information
        self.cluster_id = cluster_id
        self.cluster_count = cluster_count
        
        self.config = Config
        self.search_source = "ytsearch"  # Default search source, changeable via ,searchengine
        self.mongo = AsyncIOMotorClient(self.config.MONGODB_URI)
        self.db = self.mongo["musicBot"]  # Default database
        self.noprefix_col = self.db["noprefix"]
        self.blacklist_col = self.db["blacklist"]
        self.prefixes_col = self.db["prefixes"]
        self.settings_col = self.db["settings"]
        self.playlists_col = self.db["playlists"]
        self.team_col = self.db["team"]  # Team members (can manage noprefix)
        self.extra_owners_col = self.db["extra_owners"]  # Extra owners (full access except eval)
        self.spotify_profiles_col = self.db["spotify_profiles"]  # User Spotify profile links
        self.badges_col = self.db["badges"]  # Badge definitions
        self.user_badges_col = self.db["user_badges"]  # User badge assignments
        self.user_profiles_col = self.db["user_profiles"]  # User profiles (bio, likes, commands_used)
        self.user_likes_col = self.db["user_likes"]  # Like records (who liked whom + timestamp)
        self.cluster_stats_col = self.db["cluster_stats"]  # Per-cluster stats for cross-cluster aggregation
        self.giveaways_col = self.db["giveaways"]  # Giveaway data
        
        # Anti-spam
        self.spam_control = {}  # Format: {user_id: {command_name: [timestamps]}}
        # 1 command per 2.0 seconds
        self.global_cooldown = commands.CooldownMapping.from_cooldown(1, 2.0, commands.BucketType.user)
        
    async def get_prefix(self, message):
        if not message.guild:
            return self.config.DEFAULT_PREFIX
            
        # Get custom prefix
        config = await self.prefixes_col.find_one({"guild_id": message.guild.id})
        prefix = config["prefix"] if config else self.config.DEFAULT_PREFIX
        
        # Create list of valid prefixes (original + uppercase for case insensitivity)
        valid_prefixes = [prefix]
        if prefix.lower() != prefix.upper():
            valid_prefixes.append(prefix.upper())
            
        # Add bot mention as a valid prefix
        mention_prefixes = [f'<@{self.user.id}> ', f'<@!{self.user.id}> ']
        
        # Check if user has no-prefix access
        is_noprefix = await self.is_noprefix(message.author.id)
        if is_noprefix:
            prefixes = mention_prefixes + valid_prefixes + ['']
            return prefixes
            
        return mention_prefixes + valid_prefixes

    async def on_command_completion(self, ctx):
        """Track command usage per user."""
        try:
            await self.user_profiles_col.update_one(
                {"user_id": ctx.author.id},
                {"$inc": {"commands_used": 1}},
                upsert=True,
            )
        except Exception:
            pass

    async def is_noprefix(self, user_id: int) -> bool:
        """Check if a user has no-prefix access (handles timed expiry)."""
        doc = await self.noprefix_col.find_one({"user_id": user_id})
        if doc is None:
            return False
        expires_at = doc.get("expires_at")
        if expires_at is not None:
            import datetime
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=datetime.timezone.utc)
            if expires_at <= datetime.datetime.now(datetime.timezone.utc):
                # Expired — clean up
                await self.noprefix_col.delete_one({"user_id": user_id})
                return False
        return True

    async def is_blacklisted(self, user_id: int) -> bool:
        """Check if a user is blacklisted"""
        user = await self.blacklist_col.find_one({"user_id": user_id})
        return user is not None

    async def is_team_member(self, user_id: int) -> bool:
        """Check if a user is a team member"""
        user = await self.team_col.find_one({"user_id": user_id})
        return user is not None

    async def is_extra_owner(self, user_id: int) -> bool:
        """Check if a user is an extra owner"""
        user = await self.extra_owners_col.find_one({"user_id": user_id})
        return user is not None

    async def blacklist_check(self, ctx):
        if await self.is_blacklisted(ctx.author.id):
            # Silently block the command by raising a special exception
            # that won't trigger any error messages
            raise commands.CheckFailure("__SILENT_BLACKLIST__")
        return True
        
    async def check_global_cooldown(self, ctx):
        # Skip cooldown for owners
        if await self.is_owner(ctx.author):
            return True
            
        bucket = self.global_cooldown.get_bucket(ctx.message)
        retry_after = bucket.update_rate_limit()
        if retry_after:
            raise commands.CommandOnCooldown(bucket, retry_after)
        return True

    async def maintenance_check(self, ctx):
        """Check if bot is in maintenance mode"""
        if getattr(self, 'maintenance_mode', False):
            # Allow owners to use commands during maintenance
            if await self.is_owner(ctx.author):
                return True
            # Block everyone else
            await ctx.send(embed=create_error_embed("🔧 Bot is currently in maintenance mode. Please try again later."))
            return False
        return True

    async def setup_hook(self):
        """Initialize connections and load cogs"""
        # Add global checks
        self.add_check(self.blacklist_check)
        self.add_check(self.check_global_cooldown)
        self.add_check(self.maintenance_check)
        
        # Connect to Lavalink
        nodes = [
            wavelink.Node(
                uri=f"http://{self.config.LAVALINK_HOST}:{self.config.LAVALINK_PORT}",
                password=self.config.LAVALINK_PASSWORD,
                identifier=self.config.LAVALINK_IDENTIFIER
            )
        ]
        
        _section("Lavalink")
        _log(f"Connecting to {_C.BOLD}{self.config.LAVALINK_HOST}:{self.config.LAVALINK_PORT}{_C.RESET}...")
        await wavelink.Pool.connect(nodes=nodes, client=self, cache_capacity=100)
        
        # Load extensions
        extensions = [
            'jishaku',  # Python debugging and evaluation
            'commands.play',
            'commands.queue',
            'commands.control',
            'commands.voice',
            'commands.filters',
            'commands.advanced',
            'commands.search',
            'commands.events',
            'commands.owner',
            'commands.settings',
            'commands.help',
            'commands.afk',
            'commands.moderation',
            'commands.playlist',
            'commands.spotify',
            'commands.utility',
            'commands.vcmod',

            'commands.customize',
            'commands.logging',
            'commands.badges',
            'commands.giveaway',
            'commands.searchengine',
        ]
        
        _section("Loading Extensions")
        loaded = 0
        failed = 0
        for ext in extensions:
            try:
                await self.load_extension(ext)
                _ok(f"{_C.WHITE}{ext}{_C.RESET}")
                loaded += 1
            except Exception as e:
                import traceback
                _err(f"{_C.WHITE}{ext}{_C.RESET}  {_C.DIM}({e}){_C.RESET}")
                failed += 1
                traceback.print_exc()
                with open("error_log.txt", "a") as f:
                     f.write(f"Failed to load {ext}: {e}\n")
                     traceback.print_exc(file=f)
                     f.write("\n")
        
        color = _C.GREEN if failed == 0 else _C.YELLOW
        _log(f"{color}{loaded} loaded{_C.RESET}, {_C.RED if failed else _C.DIM}{failed} failed{_C.RESET}")
        
    async def on_ready(self):
        _section("Bot Ready")
        _ok(f"Logged in as {_C.BOLD}{_C.CYAN}{self.user}{_C.RESET}  {_C.DIM}(ID: {self.user.id}){_C.RESET}")
        _ok(f"Guilds: {_C.BOLD}{len(self.guilds)}{_C.RESET}  │  Users: {_C.BOLD}{sum(g.member_count or 0 for g in self.guilds)}{_C.RESET}  │  Cogs: {_C.BOLD}{len(self.cogs)}{_C.RESET}")
        
        # Display shard information
        if self.shard_count:
            shard_str = f"Shards: {_C.BOLD}{self.shard_count}{_C.RESET}"
            if self.shard_ids:
                shard_str += f"  │  This cluster: {_C.BOLD}{self.shard_ids}{_C.RESET}  │  Cluster {_C.BOLD}{self.cluster_id + 1}/{self.cluster_count}{_C.RESET}"
            else:
                shard_str += f"  {_C.DIM}(single cluster){_C.RESET}"
            _ok(shard_str)
        else:
            _ok(f"Shards: {_C.BOLD}auto{_C.RESET}  {_C.DIM}(Discord determines count){_C.RESET}")
        
        print(f"\n  {_C.GREEN}{_C.BOLD}  ● Bot is online and ready!{_C.RESET}\n")
        
        # Sync application commands if we had any hybrid commands
        # await self.tree.sync()
        
        # Auto-reconnect to 24/7 channels immediately as background task
        self.loop.create_task(self.reconnect_247_channels())
        
        # Start periodic cluster stats sync
        self.loop.create_task(self._sync_cluster_stats_loop())
    
    async def reconnect_247_channels(self):
        """Reconnect to voice channels where 24/7 mode was enabled"""
        try:
            # Wait for wavelink to be fully ready
            await asyncio.sleep(5)

            # Find all guilds with 24/7 enabled
            guilds_with_247 = []
            async for guild_data in self.settings_col.find({"247": True}):
                guilds_with_247.append(guild_data)
            
            if not guilds_with_247:
                logger.info("No guilds with 24/7 mode enabled")
                return
            
            logger.info(f"Found {len(guilds_with_247)} guild(s) with 24/7 mode enabled")
            
            for guild_data in guilds_with_247:
                guild_id = guild_data.get("guild_id")
                voice_channel_id = guild_data.get("voice_channel_id")
                
                if not guild_id or not voice_channel_id:
                    continue
                
                guild = self.get_guild(guild_id)
                if not guild:
                    logger.warning(f"Could not find guild {guild_id} for 24/7 reconnect - removing from database")
                    await self.settings_col.update_one(
                        {"guild_id": guild_id},
                        {"$set": {"247": False}, "$unset": {"voice_channel_id": ""}}
                    )
                    continue
                
                # Skip if already connected
                if guild.voice_client:
                    logger.info(f"Already connected to voice in guild {guild.name}")
                    continue
                
                voice_channel = guild.get_channel(voice_channel_id)
                if not voice_channel:
                    logger.warning(f"Could not find voice channel {voice_channel_id} in guild {guild.name}")
                    # Disable 24/7 since channel no longer exists
                    await self.settings_col.update_one(
                        {"guild_id": guild_id},
                        {"$set": {"247": False}, "$unset": {"voice_channel_id": ""}}
                    )
                    continue
                
                try:
                    player = await safe_connect(voice_channel)
                    logger.info(f"Reconnected to 24/7 channel in guild {guild.name}")
                except Exception as e:
                    logger.error(f"Failed to reconnect to 24/7 channel in guild {guild.name}: {e}")
                
                # Stagger reconnects to avoid overwhelming Lavalink
                await asyncio.sleep(3)

        except Exception as e:
            # Log the error but don't crash the bot
            # Check if it's a DNS/Connection error to suppress spam
            str_e = str(e)
            if "nameservers failed" in str_e or "SERVFAIL" in str_e or "Timeout" in str_e:
                 logger.warning(f"24/7 Reconnect prevented by DB Connection Error: {e}")
            else:
                 logger.error(f"Error in reconnect_247_channels: {e}")
                 import traceback
                 traceback.print_exc()

    async def _sync_cluster_stats_loop(self):
        """Periodically write this cluster's stats to MongoDB for cross-cluster aggregation."""
        await self.wait_until_ready()
        while not self.is_closed():
            try:
                await self.cluster_stats_col.update_one(
                    {"cluster_id": self.cluster_id},
                    {"$set": {
                        "cluster_id": self.cluster_id,
                        "guilds": len(self.guilds),
                        "users": sum(g.member_count or 0 for g in self.guilds),
                        "channels": sum(len(g.channels) for g in self.guilds),
                        "voice_clients": len(self.voice_clients),
                        "shard_ids": self.shard_ids or [],
                        "updated_at": asyncio.get_event_loop().time(),
                    }},
                    upsert=True,
                )
            except Exception:
                pass
            await asyncio.sleep(30)

    async def on_wavelink_node_ready(self, payload: wavelink.NodeReadyEventPayload):
        _ok(f"Lavalink node {_C.BOLD}{payload.node.identifier}{_C.RESET} connected")

    async def on_message(self, message):
        """Handle bot mentions and process commands"""
        # Ignore bot messages
        if message.author.bot:
            return
            
        # Check if bot is mentioned (and it's not just a command with mention prefix)
        if self.user.mentioned_in(message) and not message.mention_everyone:
            # Check if it's just a mention without a command
            content = message.content.replace(f'<@{self.user.id}>', '').replace(f'<@!{self.user.id}>', '').strip()
            
            if not content or content == '':
                # Get the server's prefix
                if message.guild:
                    config = await self.prefixes_col.find_one({"guild_id": message.guild.id})
                    prefix = config["prefix"] if config else self.config.DEFAULT_PREFIX
                else:
                    prefix = self.config.DEFAULT_PREFIX
                
                # Build Components V2 LayoutView
                view = discord.ui.LayoutView(timeout=None)
                container = discord.ui.Container(accent_colour=discord.Colour(self.config.EMBED_COLOR))

                container.add_item(discord.ui.TextDisplay(
                    f"### <a:Wave:1476301683259867329> Hello, I'm {self.user.name}!\n"
                    f"I'm a powerful music bot designed to bring high-quality music to your server!\n\n"
                    f"**My prefix is:** `{prefix}`\n"
                    f"**Example:** `{prefix}play <song name>`"
                ))

                container.add_item(discord.ui.Separator())

                container.add_item(discord.ui.TextDisplay(
                    f"**<a:quicknote:1476302387680379010> Quick Start**\n"
                    f"`{prefix}play` — Play a song\n"
                    f"`{prefix}queue` — View the queue\n"
                    f"`{prefix}help` — View all commands"
                ))

                container.add_item(discord.ui.Separator())

                # Link buttons
                invite_url = f"https://discord.com/api/oauth2/authorize?client_id={self.user.id}&permissions=8&scope=bot%20applications.commands"
                btn_row = discord.ui.ActionRow()
                btn_row.add_item(discord.ui.Button(label="Invite Me", style=discord.ButtonStyle.link, url=invite_url, emoji="📨"))
                btn_row.add_item(discord.ui.Button(label="Support Server", style=discord.ButtonStyle.link, url=self.config.SUPPORT_SERVER, emoji="🛠️"))
                container.add_item(btn_row)

                view.add_item(container)
                await message.channel.send(view=view)
                return
        
        # Process commands normally
        await self.process_commands(message)


    async def on_command_error(self, ctx, error):
        from utils.embeds import create_error_embed
        import time
        
        if isinstance(error, commands.CommandNotFound):
            return
            
        if isinstance(error, commands.CommandOnCooldown):
            # Anti-Spam / Auto-Blacklist Logic
            user_id = ctx.author.id
            command_name = ctx.command.qualified_name if ctx.command else "unknown"
            now = time.time()
            
            # Initialize user data if not present
            if user_id not in self.spam_control:
                self.spam_control[user_id] = {}
            
            # Initialize command tracking for this user
            if command_name not in self.spam_control[user_id]:
                self.spam_control[user_id][command_name] = []
            
            # Get timestamps for this command
            timestamps = self.spam_control[user_id][command_name]
            
            # Remove timestamps older than 3 seconds
            timestamps[:] = [ts for ts in timestamps if now - ts <= 3]
            
            # Add current timestamp
            timestamps.append(now)
            
            # Check if user spammed same command 3 times in 3 seconds
            if len(timestamps) >= 3:
                # Blacklist user silently
                await self.blacklist_col.update_one(
                    {"user_id": user_id},
                    {"$set": {
                        "user_id": user_id,
                        "reason": f"Auto-blacklist: Spamming '{command_name}' command"
                    }},
                    upsert=True
                )
                # Cleanup memory
                del self.spam_control[user_id]
                return
            
            # No cooldown warning message - just silently ignore
            return

        if isinstance(error, commands.MissingRequiredArgument):
            cmd = ctx.command
            
            # Get correct prefix for display
            prefix = ctx.prefix
            # If invoked with no prefix (noprefix user) or via mention, show the server's configured prefix
            if prefix is None or prefix == "":
                if ctx.guild:
                    config = await self.prefixes_col.find_one({"guild_id": ctx.guild.id})
                    prefix = config["prefix"] if config else self.config.DEFAULT_PREFIX
                else:
                    prefix = self.config.DEFAULT_PREFIX
                
            # Construct syntax
            # command.signature gives the arguments like "<query>" or "[reason]"
            syntax = f"{prefix}{cmd.qualified_name} {cmd.signature}"
            
            embed = discord.Embed(color=self.config.ERROR_COLOR)
            embed.set_author(name=f"Correct Usage for {cmd.name}", icon_url=self.user.display_avatar.url)
            embed.description = f"```\n{syntax}\n```"
            
            if cmd.aliases:
                embed.add_field(name="Aliases", value=", ".join(cmd.aliases))
                
            embed.set_footer(text=f"Requested by {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
            
            await ctx.send(embed=embed)
            return

        if isinstance(error, commands.CheckFailure):
            # Silent blacklist - don't send any message
            if str(error) == "__SILENT_BLACKLIST__":
                return
            # If the check itself sent a message, we might double up, 
            # but ideally checks should raise with a message.
            if str(error):
                await ctx.send(embed=create_error_embed(str(error)))
            return

        if isinstance(error, commands.MissingPermissions):
            await ctx.send(embed=create_error_embed(f"You are missing permissions: {', '.join(error.missing_permissions)}"))
            return

        if isinstance(error, commands.BotMissingPermissions):
            await ctx.send(embed=create_error_embed(f"I am missing permissions: {', '.join(error.missing_permissions)}"))
            return
            
        if isinstance(error, commands.BadArgument):
            await ctx.send(embed=create_error_embed(f"Invalid argument: {str(error)}"))
            return
            
        logger.error(f'Ignoring exception in command {ctx.command}:')
        traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)

bot = MusicBot()

if __name__ == "__main__":
    import asyncio
    
    async def main():
        async with bot:
            await bot.start(Config.DISCORD_TOKEN)

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
