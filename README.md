# SSTV Discord Bot

This bot listens for SSTV signals from OpenWebRX, processes them, and sends notifications to a Discord channel with image reactions for validation.

## Features

- **SSTV Signal Handling**: The bot detects SSTV signals and sends images to the Discord channel with **reaction buttons** for validation:
  - ✅ Approve the image
  - ❌ Reject the image
- **Status Information**: The bot displays a custom status showing the following:
  - **SSTV Stats**:
    - **Today’s SSTV received count**.
    - **Number of approved and rejected images**.
  - **Bot and SDR status**: Displays:
    - **Ping** for the SDR (configured to `192.168.1.1` by default).
    - **Bot latency**.
    - **Uptime** of the bot and the server.
    - **Last received SSTV timestamp**.
- **Custom Streaming Status**: The bot sets its status as **streaming** with the title: *The Ai Oshino Websdr* (with a purple dot on Discord).
- **Error Notifications**: In case of an error, the bot will:
  - Mention you **three times** (@kik) in a Discord message.
  - Attach an error log file for debugging.

## Requirements

- **Python 3.x**
- **Discord.py library** (`pip install discord.py`)
- **SQLite** (for storing SSTV statistics)

## Setup

1. **Clone the repository**:
    ```bash
    git clone https://github.com/yourusername/sstv-discord-bot.git
    cd sstv-discord-bot
    ```

2. **Create a `.env` file** in the project root with your Discord bot token and other configurations:
    ```env
    DISCORD_TOKEN=your-discord-bot-token
    WATCHED_FOLDER=/tmp
    SSTV_CHANNEL_ID=your-channel-id
    STATS_CHANNEL_ID=your-stats-channel-id
    SDR_PING_HOST=192.168.1.1
    ```

3. **Install required dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

4. **Run the bot**:
    ```bash
    python bot.py
    ```

## How it works

- **SSTV Signal Detection**:
  The bot listens for new SSTV images in the specified folder (`/tmp` by default). When a new image appears, it is automatically uploaded to the configured Discord channel.
  
- **Approval System**:
  - The bot posts the image in Discord and adds two reactions: ✅ for approval and ❌ for rejection.
  - When a reaction is added:
    - ✅: Clears the reactions and marks the image as approved.
    - ❌: Deletes the message and marks the image as rejected.

- **Stats Message**:
  - Every 10 seconds, the bot updates a message with the current SSTV stats, including:
    - Total SSTV received today.
    - The number of approved and rejected images.
    - SDR and bot pings, and uptime information.

- **Error Handling**:
  - If an error occurs, the bot sends a notification with the error message and logs the issue, attaching a `.txt` file with the error details.
  - The bot will mention you **three times** with your Discord ID in case of an error.

## Commands

- `/refreshstats`:
  Forces the bot to update the stats message immediately.

## Bot Streaming Status

The bot’s status is set to **streaming**, and it uses a custom title: *The Ai Oshino Websdr*. This appears in Discord as the purple dot typically seen with Twitch streamers.

## Notes

- This bot requires that the `SSTV_CHANNEL_ID` and `STATS_CHANNEL_ID` be valid Discord channel IDs where the bot can send messages.
- You can replace the default `SDR_PING_HOST` (192.168.1.1) with the IP address of your SDR if needed.
- **Make sure your bot is added to your server with the appropriate permissions** to read messages, send messages, and add reactions in the
