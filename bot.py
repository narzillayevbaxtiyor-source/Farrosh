import os
import logging
from telegram import Update
from telegram.ext import (
    Application,
    MessageHandler,
    ContextTypes,
    filters,
)

BOT_TOKEN = os.getenv("BOT_TOKEN")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
log = logging.getLogger(__name__)


# === LINK TOZALOVCHI ===
async def clean_links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    user = update.effective_user

    # admin bo‘lsa — o‘chirmaymiz
    member = await context.bot.get_chat_member(
        update.effective_chat.id, user.id
    )
    if member.status in ("administrator", "creator"):
        return

    # link bo‘lsa — o‘chiramiz
    if update.message.entities:
        for e in update.message.entities:
            if e.type in ("url", "text_link"):
                await update.message.delete()
                return


# === SERVICE MESSAGE (kirdi / chiqdi) ===
async def delete_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.delete()


def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # linklar
    app.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS & filters.Entity("url"),
            clean_links,
        )
    )

    # kirdi / chiqdi
    app.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS & filters.StatusUpdate.ALL,
            delete_service,
        )
    )

    log.info("🧹 Cleaner bot ishga tushdi")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
