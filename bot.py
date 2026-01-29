import os
import logging
from telegram import Update
from telegram.ext import (
    Application,
    MessageHandler,
    ContextTypes,
    filters,
)
from telegram.constants import ChatMemberStatus

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
async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user = update.effective_user
    chat = update.effective_chat
    if not user or not chat:
        return False

    member = await context.bot.get_chat_member(chat.id, user.id)
    return member.status in (
        ChatMemberStatus.ADMINISTRATOR,
        ChatMemberStatus.OWNER,
    )

# ================== CLEAN LINK ==================
async def clean_links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    msg = update.effective_message

    if not chat or not msg:
        return

    if chat.id != ALLOWED_CHAT_ID:
        return

    # admin bo‘lsa tegma
    if await is_admin(update, context):
        return

    # TEXT ichidagi link
    if msg.entities:
        for e in msg.entities:
            if e.type in ("url", "text_link"):
                await msg.delete()
                return

    # CAPTION ichidagi link
    if msg.caption_entities:
        for e in msg.caption_entities:
            if e.type in ("url", "text_link"):
                await msg.delete()
                return

# ================== CLEAN JOIN / LEAVE ==================
async def clean_join_leave(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat

    if not msg or not chat:
        return

    if chat.id != ALLOWED_CHAT_ID:
        return

    await msg.delete()

# ================== MAIN ==================
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # linklar
    app.add_handler(
        MessageHandler(
            filters.Chat(ALLOWED_CHAT_ID)
            & (filters.TEXT | filters.CAPTION),
            clean_links,
        )
    )

    # join / leave
    app.add_handler(
        MessageHandler(
            filters.Chat(ALLOWED_CHAT_ID)
            & (filters.StatusUpdate.NEW_CHAT_MEMBERS | filters.StatusUpdate.LEFT_CHAT_MEMBER),
            clean_join_leave,
        )
    )

    log.info("🧹 Cleaner bot ishga tushdi")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
