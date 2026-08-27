"""
set_webhook.py — Register your PythonAnywhere URL as the Telegram Webhook
==========================================================================
Run this script ONCE after deploying to PythonAnywhere to tell Telegram
where to send updates.

Usage:
    python set_webhook.py

You will be prompted for your PythonAnywhere username (e.g. 'shali123').
The webhook will be set to: https://YOURUSERNAME.pythonanywhere.com/webhook
"""

import os
import sys
import asyncio

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from telegram import Bot
from config import BOT_TOKEN


async def set_webhook(webhook_url: str) -> None:
    bot = Bot(token=BOT_TOKEN)

    # Remove any existing webhook / polling first
    await bot.delete_webhook(drop_pending_updates=True)
    print("✅ Cleared any existing webhook / polling.")

    # Set the new webhook
    result = await bot.set_webhook(
        url=webhook_url,
        allowed_updates=[
            "message",
            "callback_query",
            "my_chat_member",
        ],
        drop_pending_updates=True,
    )

    if result:
        print(f"\n🎉 Webhook successfully set!\n")
        print(f"   URL: {webhook_url}")
    else:
        print("❌ Failed to set webhook. Check your token and URL.")

    # Print webhook info for confirmation
    info = await bot.get_webhook_info()
    print(f"\n📋 Webhook Info:")
    print(f"   URL:              {info.url}")
    print(f"   Pending updates:  {info.pending_update_count}")
    print(f"   Last error:       {info.last_error_message or 'None'}")

    await bot.close()


async def delete_webhook() -> None:
    bot = Bot(token=BOT_TOKEN)
    await bot.delete_webhook(drop_pending_updates=True)
    print("✅ Webhook deleted. Your bot will no longer receive updates via webhook.")
    print("   To use polling again, run bot.py directly.")
    await bot.close()


if __name__ == '__main__':
    print("=" * 60)
    print("  Oxel Bot — Webhook Registration Tool")
    print("=" * 60)
    print()

    action = input("Choose action:\n  [1] Set webhook (deploy)\n  [2] Delete webhook (switch back to polling)\nEnter 1 or 2: ").strip()

    if action == '2':
        asyncio.run(delete_webhook())
        sys.exit(0)

    username = input("\nEnter your PythonAnywhere username (e.g. shali123): ").strip()
    if not username:
        print("❌ Username cannot be empty.")
        sys.exit(1)

    custom_path = input("Custom subdomain/path? Press Enter to use default\n  (default: https://{username}.pythonanywhere.com/webhook): ").strip()

    if custom_path:
        webhook_url = custom_path if custom_path.startswith('http') else f"https://{custom_path}"
    else:
        webhook_url = f"https://{username}.pythonanywhere.com/webhook"

    print(f"\n📡 Setting webhook to: {webhook_url}")
    confirm = input("Confirm? (y/n): ").strip().lower()

    if confirm != 'y':
        print("Cancelled.")
        sys.exit(0)

    asyncio.run(set_webhook(webhook_url))
