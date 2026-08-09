"""
safe_message.py — Safe Telegram message editing utility.

When a message contains a photo (sent via send_photo / reply_photo),
calling edit_message_text() on it raises:
    telegram.error.BadRequest: There is no text in the message to edit

Use safe_edit_text() instead — it automatically handles photo messages
by deleting the photo and sending a fresh text message.
"""

import logging
from telegram import Update, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.error import BadRequest

logger = logging.getLogger(__name__)


async def safe_edit_text(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    text: str,
    reply_markup=None,
    parse_mode: str = "Markdown",
):
    """
    Safely edit or replace the current message with new text.

    - If message has a photo: deletes old message, sends new text message.
    - If message is plain text: uses edit_message_text (in-place edit).
    - Falls back to sending a new reply_text if edit fails.
    """
    query = update.callback_query
    if not query:
        # Called from a regular message context — just reply
        await update.effective_message.reply_text(
            text, reply_markup=reply_markup, parse_mode=parse_mode
        )
        return

    msg = query.message
    is_photo_message = bool(msg.photo)

    if is_photo_message:
        # Photo messages cannot be edited to text — delete and send fresh
        try:
            await msg.delete()
        except Exception:
            pass
        await context.bot.send_message(
            chat_id=msg.chat_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
        )
    else:
        # Plain text message — edit in place
        try:
            await query.edit_message_text(
                text, reply_markup=reply_markup, parse_mode=parse_mode
            )
        except BadRequest as e:
            if "there is no text" in str(e).lower() or "message is not modified" in str(e).lower():
                # Fallback: send a new message
                try:
                    await msg.delete()
                except Exception:
                    pass
                await context.bot.send_message(
                    chat_id=msg.chat_id,
                    text=text,
                    reply_markup=reply_markup,
                    parse_mode=parse_mode,
                )
            else:
                logger.exception("safe_edit_text: unexpected BadRequest")
                raise
        except Exception:
            # Last resort fallback
            try:
                await msg.reply_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
            except Exception:
                logger.exception("safe_edit_text: all fallbacks failed")
