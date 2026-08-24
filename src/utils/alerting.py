"""
Utility functions for logging messages to Discord.

Include AlertLevel enum and log_to_discord function.
"""

import requests
from enum import Enum

import os
from dotenv import load_dotenv

load_dotenv()

# Discord webhook URL retrieved from the environment configuration
DISCORD_WEBHOOK_URL = str(os.getenv("DISCORD_WEBHOOK_URL"))


# Enumeration representing the severity levels for alerts
class AlertLevel(Enum):
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


def log_to_discord(msg: str, level: AlertLevel):
    """Sends a formatted alert message to a Discord channel using a webhook.

    Args:
        msg (str): The message content to be logged.
        level (AlertLevel): The severity level of the alert.
    """
    content = f"[{level.value}] {msg}"

    if level == AlertLevel.ERROR:
        content += " @everyone"

    data = {"content": content}

    response = requests.post(DISCORD_WEBHOOK_URL, json=data)

    # Verify if the webhook request was successful (Discord returns 200 or 204)
    if response.status_code not in (200, 204):
        print(f"Erreur envoi Discord: {response.text}")