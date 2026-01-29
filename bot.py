import os
import re
import logging
from typing import Set

from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, ContextTypes, filters

# ================== ENV ==================
BOT_TOKEN = (os.getenv("BOT_TOKEN") or "").strip()
ALLOWED_CHAT_ID = int((os.getenv("ALLOWED_CHAT_ID") or "0").strip() or "0")

# Admin IDs: "123,456" (ixtiyoriy). Bo'sh bo'lsa — bot adminlarni o'zi tekshiradi.
ADMIN_IDS_RAW = (os.getenv("ADMIN_IDS") or "").strip()
ADMIN_IDS: Set[int] = set()
if ADMIN_IDS_RAW:
    for x in ADMIN_IDS_RAW.split(","):
        x = x.strip()
        if x.isdigit():
            ADMIN_IDS.add(int(x))

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN topilmadi. Variables ga BOT_TOKEN qo'ying.")
if not ALLOWED_CHAT_ID:
    raise RuntimeError("ALLOWED_CHAT_ID topilmadi. Variables ga ALLOWED_CHAT_ID qo'ying.")

# ================== LOGGING ==================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger("cleaner-bot")

# ================== REGEX ==================
URL_RE = re.compile(
    r"(?i)\b("
    r"(?:https?://|www\.)\S+"
    r"|t\.me/\S+"
    r"|telegram\.me/\S+"
    r")"
)

# ================== HELPERS ==================
def is_allowed_group(update: Update) -> bool:
    chat = update.effective_chat
    return bool(chat and chat.id == ALLOWED_CHAT_ID)

async def is_user_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """ADMIN_IDS bo'lsa shu ro'yxat, bo'lmasa Telegramdan adminligini tekshiradi."""
    user = update.effective_user
    chat = update.effective_chat
    if not user or not chat:
        return False

    if ADMIN_IDS:
        return user.id in ADMIN_IDS

    try:
        member = await context.bot.get_chat_member(chat.id, user.id)
        return member.status in ("administrator", "creator")
    except Exception:
        return False

# ================== HANDLERS ==================
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed_group(update):
        return
    await update.effective_message.reply_text(
        "🧹 Cleaner bot ishlayapti.\n"
        "• Oddiy user link tashlasa — o‘chiradi\n"
        "• Kirdi/chiqdini — o‘chiradi\n"
        "• Admin linklari — o‘chmaydi"
    )

async def clean_links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg or not is_allowed_group(update):
        return

    text = (msg.text or "") + " " + (msg.caption or "")
    if not text.strip():
        return

    # Link bormi?
    if not URL_RE.search(text):
        return

    # Admin linklarini o'chirmaymiz
    if await is_user_admin(update, context):
        return

    # Oddiy user link tashlasa -> o'chiramiz
    try:
        await context.bot.delete_message(chat_id=msg.chat_id, message_id=msg.message_id)
    except Exception:
        log.exception("delete_message failed (links)")

async def clean_join_leave(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg or not is_allowed_group(update):
        return

    # new members / left member service messages
    try:
        await context.bot.delete_message(chat_id=msg.chat_id, message_id=msg.message_id)
    except Exception:
        log.exception("delete_message failed (join/leave)")

# ================== MAIN ==================
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_cmd))

    # Linklarni o'chirish (text yoki caption)
    app.add_handler(
        MessageHandler(
            filters.Chat(ALLOWED_CHAT_ID) & (filters.TEXT | filters.CAPTION),
            clean_links,
        )
    )

    # Kirdi/chiqdini o'chirish
    app.add_handler(
        MessageHandler(
            filters.Chat(ALLOWED_CHAT_ID)
            & (filters.StatusUpdate.NEW_CHAT_MEMBERS | filters.StatusUpdate.LEFT_CHAT_MEMBER),
            clean_join_leave,
        )
    )

    log.info("🧹 Cleaner bot ishga tushdi. ALLOWED_CHAT_ID=%s", ALLOWED_CHAT_ID)
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
