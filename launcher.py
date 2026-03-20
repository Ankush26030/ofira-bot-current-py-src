import asyncio
import os
import sys
import math
import subprocess
import time
import aiohttp
from config import Config
from datetime import datetime

# ── Configuration ──
SHARDS_PER_CLUSTER = 2
GUILDS_PER_SHARD = 200
RESHARD_CHECK_INTERVAL = 1800  # 30 minutes

# ── ANSI Colors ──
class C:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    CYAN    = "\033[36m"
    GREEN   = "\033[32m"
    YELLOW  = "\033[33m"
    RED     = "\033[31m"
    MAGENTA = "\033[35m"
    BLUE    = "\033[34m"
    WHITE   = "\033[97m"
    BG_DARK = "\033[40m"

# ── Pretty Print Helpers ──
BANNER = f"""{C.CYAN}{C.BOLD}
    ╔═══════════════════════════════════════════════╗
    ║                                               ║
    ║   ♪  M U S I C   B O T   L A U N C H E R  ♪  ║
    ║                                               ║
    ╚═══════════════════════════════════════════════╝{C.RESET}
"""

def log_info(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"  {C.DIM}{ts}{C.RESET}  {C.CYAN}│{C.RESET}  {msg}")

def log_success(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"  {C.DIM}{ts}{C.RESET}  {C.GREEN}│{C.RESET}  {C.GREEN}✓{C.RESET} {msg}")

def log_warn(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"  {C.DIM}{ts}{C.RESET}  {C.YELLOW}│{C.RESET}  {C.YELLOW}⚠{C.RESET} {msg}")

def log_error(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"  {C.DIM}{ts}{C.RESET}  {C.RED}│{C.RESET}  {C.RED}✗{C.RESET} {msg}")

def log_section(title):
    print(f"\n  {C.MAGENTA}{C.BOLD}{'─' * 3} {title} {'─' * (40 - len(title))}{C.RESET}")

def print_config_table(rows):
    """Print a key-value table with aligned columns."""
    max_key = max(len(k) for k, _ in rows)
    for key, value in rows:
        padding = " " * (max_key - len(key))
        print(f"  {C.DIM}  │{C.RESET}    {C.WHITE}{key}{padding}{C.RESET}  {C.DIM}·{C.RESET}  {C.CYAN}{C.BOLD}{value}{C.RESET}")

# ── Discord API ──
async def get_recommended_shards(token):
    url = "https://discord.com/api/v10/gateway/bot"
    headers = {"Authorization": f"Bot {token}"}
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            if response.status == 200:
                data = await response.json()
                return data["shards"]
            else:
                log_error(f"Failed to fetch shard count (HTTP {response.status})")
                return 1

async def get_guild_count(token):
    url = "https://discord.com/api/v10/applications/@me"
    headers = {"Authorization": f"Bot {token}"}
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            if response.status == 200:
                data = await response.json()
                return data.get("approximate_guild_count", 0)
            else:
                log_error(f"Failed to fetch guild count (HTTP {response.status})")
                return 0

# ── Shard Math ──
def calculate_shards(guild_count, recommended_shards):
    desired_shards = max(1, math.ceil(guild_count / GUILDS_PER_SHARD))
    total_shards = max(recommended_shards, desired_shards)
    cluster_count = math.ceil(total_shards / SHARDS_PER_CLUSTER)
    return total_shards, cluster_count

# ── Cluster Management ──
def spawn_clusters(total_shards, cluster_count):
    processes = []
    for cluster_id in range(cluster_count):
        env = os.environ.copy()
        env["SHARD_COUNT"] = str(total_shards)
        env["CLUSTER_ID"] = str(cluster_id)
        env["CLUSTER_COUNT"] = str(cluster_count)
        p = subprocess.Popen([sys.executable, "bot.py"], env=env)
        processes.append(p)
        log_success(f"Cluster {C.BOLD}#{cluster_id}{C.RESET} launched  {C.DIM}(PID {p.pid}){C.RESET}")
    return processes

def stop_clusters(processes):
    for p in processes:
        try:
            p.terminate()
        except Exception:
            pass
    deadline = time.time() + 10
    for p in processes:
        remaining = max(0, deadline - time.time())
        try:
            p.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            p.kill()

# ── Main ──
async def main():
    # Enable ANSI on Windows
    if sys.platform == "win32":
        os.system("")

    print(BANNER)

    token = Config.DISCORD_TOKEN
    if not token:
        log_error("DISCORD_TOKEN not found in config. Aborting.")
        return

    # ── Fetch Info ──
    log_section("Connecting to Discord")
    log_info("Fetching gateway info...")

    recommended_shards = await get_recommended_shards(token)
    guild_count = await get_guild_count(token)
    total_shards, cluster_count = calculate_shards(guild_count, recommended_shards)

    log_success(f"Gateway connected  {C.DIM}(recommended {recommended_shards} shard{'s' if recommended_shards != 1 else ''}){C.RESET}")
    log_success(f"Guild count: {C.BOLD}{guild_count}{C.RESET}")

    # ── Config Table ──
    log_section("Configuration")
    print_config_table([
        ("Guilds",           str(guild_count)),
        ("Guilds / Shard",   str(GUILDS_PER_SHARD)),
        ("Total Shards",     str(total_shards)),
        ("Shards / Cluster", str(SHARDS_PER_CLUSTER)),
        ("Total Clusters",   str(cluster_count)),
        ("Auto-Reshard",     f"every {RESHARD_CHECK_INTERVAL // 60} min"),
    ])

    # ── Launch ──
    log_section("Launching Clusters")
    processes = spawn_clusters(total_shards, cluster_count)

    print(f"\n  {C.GREEN}{C.BOLD}  ● Bot is online — {len(processes)} cluster{'s' if len(processes) != 1 else ''} running{C.RESET}")
    print(f"  {C.DIM}    Press Ctrl+C to stop all clusters{C.RESET}\n")

    # ── Monitor Loop ──
    last_reshard_check = time.time()

    try:
        while True:
            await asyncio.sleep(5)

            # Dead cluster restart
            for i, p in enumerate(processes):
                if p.poll() is not None:
                    log_warn(f"Cluster {C.BOLD}#{i}{C.RESET}{C.YELLOW} died (code {p.returncode}). Restarting...{C.RESET}")
                    env = os.environ.copy()
                    env["SHARD_COUNT"] = str(total_shards)
                    env["CLUSTER_ID"] = str(i)
                    env["CLUSTER_COUNT"] = str(cluster_count)
                    new_p = subprocess.Popen([sys.executable, "bot.py"], env=env)
                    processes[i] = new_p
                    log_success(f"Cluster {C.BOLD}#{i}{C.RESET} restarted  {C.DIM}(PID {new_p.pid}){C.RESET}")

            # Auto-reshard check
            if time.time() - last_reshard_check >= RESHARD_CHECK_INTERVAL:
                last_reshard_check = time.time()
                try:
                    new_recommended = await get_recommended_shards(token)
                    new_guild_count = await get_guild_count(token)
                    new_total, new_cluster_count = calculate_shards(new_guild_count, new_recommended)

                    if new_total > total_shards:
                        log_section("Auto-Resharding")
                        log_warn(f"Guild count changed: {guild_count} → {new_guild_count}")
                        log_info(f"Shards: {total_shards} → {new_total}  |  Clusters: {cluster_count} → {new_cluster_count}")
                        log_info("Stopping old clusters...")
                        stop_clusters(processes)

                        total_shards = new_total
                        cluster_count = new_cluster_count
                        guild_count = new_guild_count

                        log_info("Spawning new clusters...")
                        processes = spawn_clusters(total_shards, cluster_count)
                        log_success(f"Reshard complete — {len(processes)} cluster{'s' if len(processes) != 1 else ''} running")
                    else:
                        log_info(f"{C.DIM}Reshard check: {new_guild_count} guilds, {total_shards} shard{'s' if total_shards != 1 else ''} — no change{C.RESET}")

                except Exception as e:
                    log_error(f"Reshard check failed: {e}")

    except KeyboardInterrupt:
        print()
        log_section("Shutting Down")
        log_info("Stopping all clusters...")
        stop_clusters(processes)
        log_success("All clusters stopped.")
        print(f"\n  {C.DIM}  Goodbye! ♪{C.RESET}\n")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
