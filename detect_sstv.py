# file: sstv_bot_optimized.py

import os
import time
import asyncio
import discord
import sqlite3
import subprocess
import logging
import psutil
from discord.ext import tasks, commands
from discord import app_commands, Status, Activity, ActivityType
from datetime import datetime, date
from dotenv import load_dotenv
from collections import deque

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
WATCHED_FOLDER = os.getenv("WATCHED_FOLDER", "/tmp")
SSTV_CHANNEL_ID = int(os.getenv("SSTV_CHANNEL_ID"))
STATS_CHANNEL_ID = int(os.getenv("STATS_CHANNEL_ID"))
SDR_PING_HOST = os.getenv("SDR_PING_HOST", "192.168.1.1")

logging.basicConfig(level=logging.INFO)
bot_start_time = time.time()

intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
bot = commands.Bot(command_prefix="!", intents=intents)

conn = sqlite3.connect("sstv_stats.db")
c = conn.cursor()
c.execute("""
CREATE TABLE IF NOT EXISTS sstv_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT,
    timestamp TEXT,
    validated INTEGER
)
""")
conn.commit()

seen_files = set()
stats_message = None
MENTION_USER_ID = 552917118186684436

ping_cache = deque(maxlen=1)
ping_last_time = 0


def format_uptime(seconds):
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    return f"{hours}h {minutes}m"


def extract_filename(message):
    for attachment in message.attachments:
        return attachment.filename
    return ""


def ping(host):
    try:
        result = subprocess.run(
            ["ping", "-c", "1", "-W", "1", host],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True
        )
        output = result.stdout
        if result.returncode == 0:
            time_ms = output.split("time=")[-1].split(" ")[0]
            return True, f"{time_ms} ms"
        else:
            return False, "unreachable"
    except:
        return False, "error"


async def handle_new_file(filename):
    filepath = os.path.join(WATCHED_FOLDER, filename)

    if not filename.lower().endswith(".png") or not filename.startswith("SSTV-"):
        return

    if not os.path.exists(filepath):
        return

    await asyncio.sleep(1)

    try:
        parts = filename.split('-')
        freq = parts[-1].split('.')[0] if len(parts) >= 2 else "Unknown"
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        channel = bot.get_channel(SSTV_CHANNEL_ID)
        if channel is None:
            return

        content = (
            f"\n📡 **New SSTV Signal**\n"
            f"**File**: `{filename}`\n"
            f"**Frequency**: {freq} kHz\n"
            f"**Time**: {now}"
        )

        file = discord.File(filepath, filename=filename)
        message = await channel.send(content=content, file=file)

        await asyncio.sleep(0.5)
        await message.add_reaction("✅")
        await asyncio.sleep(0.5)
        await message.add_reaction("❌")

        c.execute("INSERT INTO sstv_events (filename, timestamp, validated) VALUES (?, ?, NULL)", (filename, now))
        conn.commit()

    except Exception as e:
        logging.error(f"Failed to handle file {filename}: {e}", exc_info=True)


@bot.event
async def on_ready():
    logging.info(f"Logged in as {bot.user.name}")
    await bot.tree.sync()
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.streaming, name="The Ai Oshino Websdr", url="https://twitch.tv/kik07L"))
    monitor_folder.start()
    update_stats_message.start()
    ping_watcher.start()


@bot.event
async def on_raw_reaction_add(payload):
    if payload.user_id == bot.user.id:
        return

    channel = bot.get_channel(payload.channel_id)
    message = await channel.fetch_message(payload.message_id)

    if str(payload.emoji) == "❌":
        await message.delete()
        c.execute("UPDATE sstv_events SET validated = 0 WHERE filename = ?", (extract_filename(message),))
        conn.commit()

    elif str(payload.emoji) == "✅":
        await message.clear_reactions()
        c.execute("UPDATE sstv_events SET validated = 1 WHERE filename = ?", (extract_filename(message),))
        conn.commit()


@tasks.loop(seconds=3)
async def monitor_folder():
    files = os.listdir(WATCHED_FOLDER)
    new_files = set(files) - seen_files
    for f in new_files:
        await handle_new_file(f)
    seen_files.update(new_files)


@tasks.loop(seconds=30)
async def ping_watcher():
    global ping_cache, ping_last_time
    ok, result = ping(SDR_PING_HOST)
    ping_cache.clear()
    ping_cache.append((ok, result))
    ping_last_time = time.time()


@tasks.loop(seconds=15)
async def update_stats_message():
    global stats_message

    today = date.today().isoformat()
    c.execute("SELECT COUNT(*) FROM sstv_events WHERE DATE(timestamp) = ?", (today,))
    total_today = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM sstv_events WHERE DATE(timestamp) = ? AND validated = 1", (today,))
    approved_today = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM sstv_events WHERE DATE(timestamp) = ? AND validated = 0", (today,))
    rejected_today = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM sstv_events WHERE validated = 1")
    total_approved = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM sstv_events WHERE validated = 0")
    total_rejected = c.fetchone()[0]

    c.execute("SELECT MAX(timestamp) FROM sstv_events")
    last_sstv = c.fetchone()[0] or "Never"

    sdr_ok, sdr_ping = ping_cache[0] if ping_cache else (False, "pending")
    bot_latency = round(bot.latency * 1000)

    uptime_bot = format_uptime(time.time() - bot_start_time)
    uptime_sys = format_uptime(time.time() - psutil.boot_time())

    content = (
        f"\n📡 **SSTV Stats**\n"
        f"📶 SDR Ping: `{sdr_ping}`\n"
        f"🤖 Bot Ping: `{bot_latency} ms`\n"
        f"📅 **Last SSTV**: `{last_sstv}`\n"
        f"⏰ Bot Uptime: `{uptime_bot}`\n"
        f"🖥️ Server Uptime: `{uptime_sys}`\n\n"
        f"📅 **Today**:\n"
        f"• Total: {total_today}\n"
        f"• ✅ Approved: {approved_today} ({round((approved_today/total_today)*100) if total_today else 0}%)\n"
        f"• ❌ Rejected: {rejected_today} ({round((rejected_today/total_today)*100) if total_today else 0}%)\n\n"
        f"🏆 **All-Time**:\n"
        f"• ✅ Approved: {total_approved}\n"
        f"• ❌ Rejected: {total_rejected}"
    )

    channel = bot.get_channel(STATS_CHANNEL_ID)
    if stats_message is None:
        messages = [msg async for msg in channel.history(limit=10)]
        for msg in messages:
            if msg.author == bot.user:
                stats_message = msg
                break
        if stats_message is None:
            stats_message = await channel.send(content)
    else:
        await stats_message.edit(content=content)


@bot.tree.command(name="refreshstats", description="Force update the stats message")
async def refreshstats(interaction: discord.Interaction):
    await interaction.response.send_message("🔄 Refreshing stats...", ephemeral=True)
    await update_stats_message()
    await interaction.edit_original_response(content="✅ Stats updated.")


async def error_notifier(error_text):
    try:
        user_mention = f"<@{MENTION_USER_ID}>"
        message = f"{user_mention} {user_mention} {user_mention} \nAn error occurred in the SSTV bot. See attached log."
        filename = "error_log.txt"
        with open(filename, "w") as f:
            f.write(error_text)

        channel = bot.get_channel(SSTV_CHANNEL_ID)
        if channel:
            await channel.send(content=message, file=discord.File(filename))
    except Exception as e:
        logging.error("Failed to send error notification", exc_info=e)


if __name__ == "__main__":
    try:
        bot.run(DISCORD_TOKEN)
    except Exception as e:
        import traceback
        loop = asyncio.get_event_loop()
        loop.run_until_complete(error_notifier(traceback.format_exc()))
        raise