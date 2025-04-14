# file: sstv_bot_optimized.py

import os
import time
import asyncio
import discord
import sqlite3
import subprocess
import logging
import psutil
import shutil
from discord.ext import tasks, commands
from discord import app_commands, Status, Activity, ActivityType
from datetime import datetime, date
from dotenv import load_dotenv
from collections import deque
from discord.ext.commands import Context
import json
load_dotenv()
USER_DATA_DIR = "user_data"
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
WATCHED_FOLDER = os.getenv("WATCHED_FOLDER", "/tmp")
SSTV_CHANNEL_ID = int(os.getenv("SSTV_CHANNEL_ID"))
STATS_CHANNEL_ID = int(os.getenv("STATS_CHANNEL_ID"))
SDR_PING_HOST = os.getenv("SDR_PING_HOST", "192.168.1.1")
# Nom du fichier JSON où la date et l'heure sont stockées
LAST_SENT_FILE = "last_sent.json"
DECODED_FILE_PATH = "/tmp/decoded.txt"  # Le chemin vers le fichier contenant les messages FT8 décodés
DECODED_CHANNEL_ID = 1360728278305996830  # ID du salon Discord pour l'envoi des messages FT8
last_decoded_lines = []


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

WSPR_CHANNEL_ID = 1360722712292757736
WSPR_FILE_PATH = "/tmp/ALL_WSPR.TXT"
last_wspl_lines = []

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
last_decoded_lines = []  # Liste des dernières lignes envoyées, à garder pour ne pas envoyer les mêmes

os.makedirs(USER_DATA_DIR, exist_ok=True)

@bot.tree.command(name="log", description="Crée une base de données privée pour vous en MP")
async def log_command(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    user_dir = os.path.join(USER_DATA_DIR, user_id)
    db_path = os.path.join(user_dir, "data.db")

    if os.path.exists(user_dir):
        await interaction.response.send_message("Vous avez déjà une base de données.", ephemeral=True)
        return

    os.makedirs(user_dir)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE ft_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT,
            date TEXT,
            call TEXT,
            reste TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE stations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            description TEXT,
            image_path TEXT
        )
    """)
    conn.commit()
    conn.close()

    try:
        await interaction.user.send("🎉 Votre base de données a été créée avec succès ! Vous pouvez maintenant utiliser `/ft`, `/sta`, `/infos`, `/infosear`, `/export`, `/deleteall` et `/del` ici.")
        await interaction.response.send_message("📬 Je vous ai envoyé un MP !", ephemeral=True)
    except:
        await interaction.response.send_message("Je n'ai pas réussi à vous envoyer un MP. Activez vos messages privés.", ephemeral=True)

@bot.tree.command(name="ft", description="Ajoute un message radio FT8 dans votre base privée")
@app_commands.describe(type="Type de FT (8 ou 4)", date="Date", call="Callsign", reste="Autres infos")
async def ft(interaction: discord.Interaction, type: str, date: str, call: str, reste: str):
    if interaction.guild:
        await interaction.response.send_message("Cette commande n'est disponible qu'en MP.", ephemeral=True)
        return

    user_dir = os.path.join(USER_DATA_DIR, str(interaction.user.id))
    db_path = os.path.join(user_dir, "data.db")
    if not os.path.exists(db_path):
        await interaction.response.send_message("Vous devez d'abord utiliser la commande /log.", ephemeral=True)
        return

    conn = sqlite3.connect(db_path)
    conn.execute("INSERT INTO ft_messages (type, date, call, reste) VALUES (?, ?, ?, ?)", (type, date, call, reste))
    conn.commit()
    conn.close()
    await interaction.response.send_message("✅ Message FT enregistré.")

@bot.tree.command(name="sta", description="Ajoute une station de nombres découverte")
@app_commands.describe(description="Description de la station")
async def sta(interaction: discord.Interaction, description: str):
    if interaction.guild:
        await interaction.response.send_message("Cette commande n'est disponible qu'en MP.", ephemeral=True)
        return

    image_path = None
    if interaction.attachments:
        att = interaction.attachments[0]
        user_dir = os.path.join(USER_DATA_DIR, str(interaction.user.id))
        os.makedirs(user_dir, exist_ok=True)
        image_path = os.path.join(user_dir, att.filename)
        await att.save(image_path)

    db_path = os.path.join(USER_DATA_DIR, str(interaction.user.id), "data.db")
    conn = sqlite3.connect(db_path)
    conn.execute("INSERT INTO stations (description, image_path) VALUES (?, ?)", (description, image_path))
    conn.commit()
    conn.close()
    await interaction.response.send_message("📡 Station enregistrée.")

@bot.tree.command(name="infos", description="Affiche tout ce qui est enregistré dans votre base")
async def infos(interaction: discord.Interaction):
    if interaction.guild:
        await interaction.response.send_message("Cette commande n'est disponible qu'en MP.", ephemeral=True)
        return

    db_path = os.path.join(USER_DATA_DIR, str(interaction.user.id), "data.db")
    if not os.path.exists(db_path):
        await interaction.response.send_message("Aucune base trouvée. Utilisez d'abord /log", ephemeral=True)
        return

    conn = sqlite3.connect(db_path)
    ft_rows = conn.execute("SELECT * FROM ft_messages").fetchall()
    stations = conn.execute("SELECT * FROM stations").fetchall()
    conn.close()

    msg = f"**FT Messages:**\n"
    for r in ft_rows:
        msg += f"{r[0]}. {r[1]} | {r[2]} | {r[3]} | {r[4]}\n"
    msg += "\n**Stations:**\n"
    for s in stations:
        msg += f"{s[0]}. {s[1]}\n"
    await interaction.response.send_message(msg or "Rien enregistré.")

@bot.tree.command(name="infosear", description="Recherche dans votre base")
@app_commands.describe(query="Mot à rechercher")
async def infosear(interaction: discord.Interaction, query: str):
    if interaction.guild:
        await interaction.response.send_message("Cette commande n'est disponible qu'en MP.", ephemeral=True)
        return

    db_path = os.path.join(USER_DATA_DIR, str(interaction.user.id), "data.db")
    conn = sqlite3.connect(db_path)
    ft_rows = conn.execute("SELECT * FROM ft_messages WHERE type LIKE ? OR call LIKE ? OR reste LIKE ?", (f"%{query}%",)*3).fetchall()
    stations = conn.execute("SELECT * FROM stations WHERE description LIKE ?", (f"%{query}%",)).fetchall()
    conn.close()

    msg = f"**FT (resultats):**\n"
    for r in ft_rows:
        msg += f"{r[0]}. {r[1]} | {r[2]} | {r[3]} | {r[4]}\n"
    msg += "\n**Stations (resultats):**\n"
    for s in stations:
        msg += f"{s[0]}. {s[1]}\n"
    await interaction.response.send_message(msg or "Aucun résultat.")

@bot.tree.command(name="export", description="Exportez votre base de données et images dans un fichier zip")
async def export(interaction: discord.Interaction):
    if interaction.guild:
        await interaction.response.send_message("Commande disponible uniquement en MP.", ephemeral=True)
        return

    user_dir = os.path.join(USER_DATA_DIR, str(interaction.user.id))
    if not os.path.exists(user_dir):
        await interaction.response.send_message("Aucune base trouvée. Utilisez d'abord /log.", ephemeral=True)
        return

    zip_path = os.path.join(USER_DATA_DIR, f"export_{interaction.user.id}.zip")
    shutil.make_archive(zip_path.replace(".zip", ""), 'zip', user_dir)
    await interaction.response.send_message("Voici votre export :", file=discord.File(zip_path))
    os.remove(zip_path)

@bot.tree.command(name="deleteall", description="Supprime toute votre base de données et fichiers")
async def deleteall(interaction: discord.Interaction):
    user_dir = os.path.join(USER_DATA_DIR, str(interaction.user.id))
    if os.path.exists(user_dir):
        shutil.rmtree(user_dir)
        await interaction.response.send_message("🗑️ Tous vos données ont été supprimées.")
    else:
        await interaction.response.send_message("Aucune base trouvée.")

@bot.tree.command(name="del", description="Supprimer une entrée précise par ID et catégorie")
@app_commands.describe(categorie="ft ou sta", id="Numéro de l'entrée à supprimer")
async def delete(interaction: discord.Interaction, categorie: str, id: int):
    if interaction.guild:
        await interaction.response.send_message("Commande disponible uniquement en MP.", ephemeral=True)
        return

    table = "ft_messages" if categorie == "ft" else "stations" if categorie == "sta" else None
    if not table:
        await interaction.response.send_message("Catégorie invalide. Utilisez ft ou sta.", ephemeral=True)
        return

    db_path = os.path.join(USER_DATA_DIR, str(interaction.user.id), "data.db")
    if not os.path.exists(db_path):
        await interaction.response.send_message("Aucune base trouvée. Utilisez /log.", ephemeral=True)
        return

    conn = sqlite3.connect(db_path)
    conn.execute(f"DELETE FROM {table} WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    await interaction.response.send_message(f"Entrée {id} supprimée de {categorie}.")

async def monitor_decoded_file():
    global last_decoded_lines
    try:
        if not os.path.exists(DECODED_FILE_PATH):
            return

        with open(DECODED_FILE_PATH, "r") as f:
            lines = f.readlines()

        lines = [line.strip() for line in lines if line.strip()]
        new_lines = [line for line in lines if line not in last_decoded_lines]
        last_decoded_lines = lines[-100:]  # Garder les 100 dernières lignes

        if not new_lines:
            return  # Si aucune nouvelle ligne, ne rien faire

        channel = bot.get_channel(DECODED_CHANNEL_ID)
        if not channel:
            return

        for line in new_lines:
            parts = line.split()
            if len(parts) >= 7:  # Vérifier qu'il y a suffisamment d'éléments pour traiter la ligne
                date_time_str = parts[0]  # La première valeur est un identifiant temporel
                try:
                    # Formater la date et l'heure en objet datetime pour comparaison
                    message_datetime = datetime.strptime(date_time_str, "%d%m%y")
                    
                    # Vérifier si la date est plus ancienne que celle du dernier message envoyé
                    if last_sent_datetime and message_datetime <= last_sent_datetime:
                        continue  # Ignorer si la date est antérieure ou égale à la dernière envoyée

                    # Mettre à jour la dernière date et heure envoyée
                    last_sent_datetime = message_datetime
                    save_last_sent_datetime(last_sent_datetime)  # Sauvegarder la nouvelle date

                    # Traitement du message FT8
                    callsign_from = parts[-3]  # Callsign de l'émetteur
                    callsign_to = parts[-2]  # Callsign du récepteur
                    mode = parts[-1]  # Mode (FT8 dans ce cas)

                    message = (
                        f"📡 Nouveau message FT8 reçu :\n"
                        f"```{line}```\n"
                        f"🔗 QRZ (Emetteur) : [**{callsign_from}**](https://www.qrz.com/db/{callsign_from})\n"
                        f"🔗 QRZ (Récepteur) : [**{callsign_to}**](https://www.qrz.com/db/{callsign_to})"
                    )
                    await channel.send(message)  # Envoi du message formaté

                except ValueError:
                    logging.error(f"Erreur de format de date dans la ligne FT8: {line}")

    except Exception as e:
        logging.error(f"Erreur dans monitor_decoded_file: {e}")
        
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
    monitor_wspr_file.start()

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

def load_last_sent_datetime():
    try:
        with open(LAST_SENT_FILE, "r") as f:
            data = json.load(f)
            return datetime.strptime(data["last_sent"], "%Y-%m-%d %H:%M:%S") if "last_sent" in data else None
    except (FileNotFoundError, json.JSONDecodeError):
        return None

# Fonction pour sauvegarder la date et l'heure du dernier message envoyé
def save_last_sent_datetime(last_sent_datetime):
    try:
        with open(LAST_SENT_FILE, "w") as f:
            data = {
                "last_sent": last_sent_datetime.strftime("%Y-%m-%d %H:%M:%S")
            }
            json.dump(data, f)
    except Exception as e:
        logging.error(f"Erreur lors de la sauvegarde de la date de dernier envoi: {e}")

# Variable globale pour la dernière date et heure envoyée
last_sent_datetime = load_last_sent_datetime()

@tasks.loop(seconds=10)
async def monitor_wspr_file():
    global last_wspl_lines, last_sent_datetime
    try:
        if not os.path.exists(WSPR_FILE_PATH):
            return

        with open(WSPR_FILE_PATH, "r") as f:
            lines = f.readlines()

        lines = [line.strip() for line in lines if line.strip()]
        new_lines = [line for line in lines if line not in last_wspl_lines]
        last_wspl_lines = lines[-100:]

        if not new_lines:
            return

        channel = bot.get_channel(WSPR_CHANNEL_ID)
        if not channel:
            return

        for line in new_lines:
            parts = line.split()
            if len(parts) >= 6:
                # Extraire la date et l'heure de la ligne
                date_time_str = parts[0] + " " + parts[1]  # format: "250411 1750"
                try:
                    # Convertir la date et l'heure en objet datetime pour comparaison
                    message_datetime = datetime.strptime(date_time_str, "%d%m%y %H%M")
                    
                    # Vérifier si la date est plus ancienne que celle du dernier message envoyé
                    if last_sent_datetime and message_datetime <= last_sent_datetime:
                        continue  # Ignorer le message si sa date est antérieure ou égale

                    # Mettre à jour la dernière date et heure envoyée
                    last_sent_datetime = message_datetime
                    save_last_sent_datetime(last_sent_datetime)  # Sauvegarder la nouvelle date

                    # Traitement du message WSPR
                    callsign = parts[5]  # Call sign dans la ligne
                    qrz_link = f"https://www.qrz.com/db/{callsign}"  # Lien QRZ pour le call sign
                    message = (
                        f"📡 Nouveau message WSPR reçu :\n"
                        f"```{line}```\n"
                        f"🔗 QRZ : [**{callsign}**]({qrz_link})"  # Call sign cliquable
                    )
                    await channel.send(message)  # Envoi du message formaté
                except ValueError:
                    logging.error(f"Erreur de format de date dans la ligne WSPR: {line}")

    except Exception as e:
        logging.error(f"Erreur dans monitor_wspr_file: {e}")


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