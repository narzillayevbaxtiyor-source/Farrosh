import os
import logging
from telegram import Update
from telegram.ext import Application, MessageHandler, ContextTypes, filters

BOT_TOKEN = (os.getenv("BOT_TOKEN") or "").strip()

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger(__name__)

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN yo‘q. Railway Variables ga BOT_TOKEN qo‘ying.")

# === LINK TOZALOVCHI ===
async def clean_links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg:
        return

    user = update.effective_user
    chat = update.effective_chat
    if not user or not chat:
        return

    # Admin bo‘lsa — o‘chirmaymiz
    member = await context.bot.get_chat_member(chat.id, user.id)
    if member.status in ("administrator", "creator"):
        return

    # Matndagi linklar (url / text_link)
    if msg.entities:
        for e in msg.entities:
            if e.type in ("url", "text_link"):
                try:
                    await msg.delete()
                except Exception:
                    pass
                return

    # Caption ichidagi linklar (rasm/video caption)
    if msg.caption_entities:
        for e in msg.caption_entities:
            if e.type in ("url", "text_link"):
                try:
                    await msg.delete()
                except Exception:
                    pass
                return

# === SERVICE MESSAGE (kirdi/chiqdi) o‘chirish ===
async def delete_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if msg:
        try:
            await msg.delete()
        except Exception:
            pass

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    group_filter = filters.ChatType.GROUPS | filters.ChatType.SUPERGROUP

    # Link bo‘lsa o‘chirish
    app.add_handler(
        MessageHandler(
            group_filter & (filters.Entity("url") | filters.CaptionEntity("url")),
            clean_links,
        )
    )

    # Kirdi/chiqdi o‘chirish
    app.add_handler(
        MessageHandler(
            group_filter & filters.StatusUpdate.ALL,
            delete_service,
        )
    )

    log.info("🧹 Cleaner bot ishga tushdi")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
