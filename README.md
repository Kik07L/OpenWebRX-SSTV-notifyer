# SSTV Signal Detection & Notification

This project monitors the `/tmp/` folder for SSTV images, extracts the frequency from the filename, and sends a Discord notification with the image, frequency, and reception time.

## Requirements
- Python 3.x
- `requests` library
- A Discord webhook URL
- OpenWebRX running and saving SSTV images to `/tmp/`

## Installation

1. **Clone the repo**:

    ```bash
    git clone <repository-url>
    cd <repository-folder>
    ```

2. **Install dependencies**:

    ```bash
    pip install requests
    ```

3. **Set up Discord webhook**:
   Replace the `WEBHOOK_URL` in `detect_sstv.py` with your Discord webhook URL.

4. **Run the script** manually:

    ```bash
    python3 detect_sstv.py
    ```

   Alternatively, you can set up a **systemd service** to run it in the background.

5. **Test**:
   Drop a PNG file in `/tmp/` with the format `SSTV-<date>-<time>-<frequency>.png`. The script will send a notification to Discord.

## Example Notification
📡 New SSTV signal detected: SSTV-250402-140842-14230.png Frequency: 14230 Hz Reception time: 2025-04-02 14:10:00 📡

## Troubleshooting
- Check service logs: 

    ```bash
    sudo journalctl -u detect_sstv.service -f
    ```
