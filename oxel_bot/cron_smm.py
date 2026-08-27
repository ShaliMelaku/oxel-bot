"""
Autonomous Daily SMM Publisher Cron Script for Oxel Bot.
Can be run via PythonAnywhere Scheduled Tasks tab or background scheduler.
Command for PythonAnywhere:
python /home/shalioxel/oxel-bot/oxel_bot/cron_smm.py
"""
import asyncio
import logging
from telegram import Bot
from config import BOT_TOKEN
from database import SessionLocal
from services.smm_service import publish_smm_post_to_channel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def run_daily_smm():
    bot = Bot(token=BOT_TOKEN)
    db = SessionLocal()
    try:
        logger.info("Executing Autonomous Daily SMM Channel Post...")
        ok, msg = await publish_smm_post_to_channel(bot, db)
        logger.info(f"Autonomous SMM Result: {msg}")
    except Exception as e:
        logger.error(f"Error executing autonomous SMM cron: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(run_daily_smm())
