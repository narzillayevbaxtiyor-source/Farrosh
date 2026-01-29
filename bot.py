import os
import logging
from telegram import Update
from telegram.ext import (
    Application,
    MessageHandler,
    ContextTypes,
    filters,
)

# ================== ENV ==================
BOT_TOKEN = os.getenv("BOT_TOKEN")
ALLOWED_CHAT_ID = int(os.getenv("ALLOWED_CHAT_ID", "0"))

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN yo‘q")
if not ALLOWED_CHAT_ID:
    raise RuntimeError("ALLOWED_CHAT_ID yo‘q")

# ================== LOG ==================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
log = logging.getLogger("cleaner-bot")

# ================== HELPERS ==================
def is_admin(update: Update) -> bool:
    member = update.effective_chat.get_member(update.effective_user.id)
    return member.status in ("administrator", "creator")

# ================== HANDLERS ==================
async def delete_links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg or not msg.text:
        return

    if update.effective_chat.id != ALLOWED_CHAT_ID:
        return

    if is_admin(update):
        return  # admin linklari o‘chmaydi

    if "http://" in msg.text or "https://" in msg.text or "t.me/" in msg.text:
        try:
            await msg.delete()
            log.info("Link o‘chirildi")
        except Exception:
            pass

async def delete_joins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg:
        return

    if update.effective_chat.id != ALLOWED_CHAT_ID:
        return

    try:
        await msg.delete()
        log.info("Join/left xabari o‘chirildi")
    except Exception:
        pass

# ================== MAIN ==================
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # Linklarni o‘chirish
    app.add_handler(
        MessageHandler(filters.Chat(ALLOWED_CHAT_ID) & filters.TEXT, delete_links)
    )

    # Join / left ni o‘chirish
    app.add_handler(
        MessageHandler(
            filters.Chat(ALLOWED_CHAT_ID)
            & (filters.StatusUpdate.NEW_CHAT_MEMBERS | filters.StatusUpdate.LEFT_CHAT_MEMBER),
            delete_joins,
        )
    )

    log.info("🧹 Cleaner bot ishga tushdi")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
