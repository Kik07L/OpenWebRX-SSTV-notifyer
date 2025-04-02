import os
import time
import requests
from datetime import datetime

# L'URL du webhook Discord
WEBHOOK_URL = "URLSHERE"

# Dossier à surveiller (fichiers SSTV)
watched_folder = "/tmp"

# Liste des fichiers déjà présents
already_seen = set(os.listdir(watched_folder))

def get_current_time():
    """ Retourne l'heure actuelle sous forme de chaîne """
    now = datetime.now()  # Obtient l'heure actuelle
    return now.strftime("%Y-%m-%d %H:%M:%S")  # Format : 2025-04-02 14:10:00

def extract_frequency(file_name):
    """ Extrait la fréquence depuis le nom du fichier """
    # Supposons que la fréquence soit la dernière partie du nom du fichier avant l'extension
    base_name = file_name.split('.')[0]  # Enlève l'extension .png
    parts = base_name.split('-')  # Sépare par le tiret "-"
    if len(parts) >= 4:
        frequency = parts[-1]  # La fréquence est la dernière partie
        return frequency
    return "Inconnue"  # Si le format est inattendu, retourne "Inconnue"

def send_discord_notification(file_path, file_name):
    """ Envoie une notification Discord avec l'image SSTV et son nom """
    frequency = extract_frequency(file_name)
    current_time = get_current_time()
    with open(file_path, "rb") as f:
        files = {"file": f}
        payload = {
            "content": f" {current_time} 📡 New SSTV incoming ! : {file_name}\nFreq : {frequency} kHz 📡"
        }
        requests.post(WEBHOOK_URL, files=files, data=payload)

while True:
    time.sleep(10)  # Vérifie toutes les 10 secondes
    current_files = set(os.listdir(watched_folder))
    new_files = current_files - already_seen

    for new_file in new_files:
        # Vérifie que c'est un fichier PNG
        if new_file.endswith(".png"):
            file_path = os.path.join(watched_folder, new_file)
            send_discord_notification(file_path, new_file)  # Envoie l'image à Discord

    already_seen = current_files
