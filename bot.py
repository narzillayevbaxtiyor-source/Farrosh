import os
import re
import logging
from datetime import timedelta
from typing import Optional, Set

from telegram import Update, ChatPermissions
from telegram.constants import ChatType
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ================== ENV ==================
BOT_TOKEN = (os.getenv("BOT_TOKEN") or "").strip()
ALLOWED_CHAT_ID = int((os.getenv("ALLOWED_CHAT_ID") or "0").strip() or "0")

# Default mute minutes for link spam
MUTE_MINUTES_DEFAULT = int((os.getenv("MUTE_MINUTES") or "10").strip() or "10")

# Admin IDs: "123,456" (optional). Bo'sh bo'lsa: bot faqat Telegram adminlarini tan oladi.
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

# ================== LINK DETECT ==================
URL_RE = re.compile(
    r"(?i)\b("
    r"(?:https?://|www\.)\S+"
    r"|t\.me/\S+"
    r"|telegram\.me/\S+"
    r"|@\w{3,}"
    r")\b"
)

def is_allowed_group(update: Update) -> bool:
    chat = update.effective_chat
    return bool(chat and chat.id == ALLOWED_CHAT_ID)

async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> bool:
    # 1) explicit ADMIN_IDS
    if ADMIN_IDS and user_id in ADMIN_IDS:
        return True

    # 2) telegram admin check (only in allowed group)
    if not is_allowed_group(update):
        return False
    try:
        member = await context.bot.get_chat_member(ALLOWED_CHAT_ID, user_id)
        return member.status in ("administrator", "creator")
    except Exception:
        return False

def has_link_text(text: str) -> bool:
    if not text:
        return False
    return bool(URL_RE.search(text))

def has_link_entities(msg) -> bool:
    # Entity'lar orqali ham tekshiramiz (URL, TEXT_LINK, MENTION)
    try:
        entities = []
        if msg.entities:
            entities.extend(msg.entities)
        if msg.caption_entities:
            entities.extend(msg.caption_entities)

        for e in entities:
            # url, text_link, mention
            if e.type in ("url", "text_link", "mention"):
                return True
    except Exception:
        pass
    return False

def extract_text_and_caption(update: Update) -> str:
    msg = update.effective_message
    if not msg:
        return ""
    parts = []
    if getattr(msg, "text", None):
        parts.append(msg.text)
    if getattr(msg, "caption", None):
        parts.append(msg.caption)
    return "\n".join(parts).strip()

# ================== ACTIONS ==================
async def delete_message_safely(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        await update.effective_message.delete()
    except Exception:
        pass

async def mute_user(chat_id: int, user_id: int, minutes: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    minutes = max(1, int(minutes))
    until = update_until = None
    try:
        until = context.application.bot.defaults  # dummy to avoid linter (not used)
    except Exception:
        pass

    try:
        until_date = context.application._job_queue.scheduler.timezone  # not reliable
    except Exception:
        until_date = None

    # PTB accepts datetime; easiest: use timedelta with utcnow
    from datetime import datetime, timezone
    until_dt = datetime.now(timezone.utc) + timedelta(minutes=minutes)

    perms = ChatPermissions(
        can_send_messages=False,
        can_send_audios=False,
        can_send_documents=False,
        can_send_photos=False,
        can_send_videos=False,
        can_send_video_notes=False,
        can_send_voice_notes=False,
        can_send_polls=False,
        can_send_other_messages=False,
        can_add_web_page_previews=False,
        can_change_info=False,
        can_invite_users=False,
        can_pin_messages=False,
        can_manage_topics=False,
    )
    try:
        await context.bot.restrict_chat_member(
            chat_id=chat_id,
            user_id=user_id,
            permissions=perms,
            until_date=until_dt,
        )
        return True
    except Exception:
        log.exception("restrict_chat_member failed")
        return False

async def unmute_user(chat_id: int, user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    perms = ChatPermissions(
        can_send_messages=True,
        can_send_audios=True,
        can_send_documents=True,
        can_send_photos=True,
        can_send_videos=True,
        can_send_video_notes=True,
        can_send_voice_notes=True,
        can_send_polls=True,
        can_send_other_messages=True,
        can_add_web_page_previews=True,
        can_change_info=False,
        can_invite_users=True,
        can_pin_messages=False,
        can_manage_topics=False,
    )
    try:
        await context.bot.restrict_chat_member(
            chat_id=chat_id,
            user_id=user_id,
            permissions=perms,
        )
        return True
    except Exception:
        log.exception("unrestrict failed")
        return False

# ================== SETTINGS (in-memory) ==================
# Minimal: runtime o'zgaradi, restart bo'lsa env defaultga qaytadi
MUTE_MINUTES = MUTE_MINUTES_DEFAULT

# ================== HANDLERS ==================
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Jim turadigan bot, start faqat admin uchun info
    uid = update.effective_user.id if update.effective_user else 0
    if not await is_admin(update, context, uid):
        return
    await update.effective_message.reply_text(
        "✅ Cleaner bot ishlayapti.\n"
        "• Linklar o‘chiriladi\n"
        "• Link tashlaganlar vaqtincha yozolmaydi\n"
        "• Kirdi/chiqdilar o‘chiriladi\n\n"
        "Admin buyruqlar:\n"
        "/setmutemin 10\n"
        "/unmute (reply qilib)"
    )

async def setmutemin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed_group(update) and (update.effective_chat and update.effective_chat.type != ChatType.PRIVATE):
        return

    uid = update.effective_user.id if update.effective_user else 0
    if not await is_admin(update, context, uid):
        return

    global MUTE_MINUTES
    if not context.args:
        await update.effective_message.reply_text(f"Hozirgi mute: {MUTE_MINUTES} daqiqa. Misol: /setmutemin 10")
        return

    try:
        m = int(context.args[0])
        MUTE_MINUTES = max(1, m)
        await update.effective_message.reply_text(f"✅ Mute {MUTE_MINUTES} daqiqaga o‘zgardi.")
    except Exception:
        await update.effective_message.reply_text("❌ Noto‘g‘ri. Misol: /setmutemin 10")

async def unmute_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed_group(update):
        return

    uid = update.effective_user.id if update.effective_user else 0
    if not await is_admin(update, context, uid):
        return

    msg = update.effective_message
    target_id: Optional[int] = None

    if msg.reply_to_message and msg.reply_to_message.from_user:
        target_id = msg.reply_to_message.from_user.id
    elif context.args and context.args[0].isdigit():
        target_id = int(context.args[0])

    if not target_id:
        await msg.reply_text("Reply qilib /unmute yozing yoki /unmute 12345")
        return

    ok = await unmute_user(ALLOWED_CHAT_ID, target_id, context)
    if ok:
        await msg.reply_text("✅ Unmute qilindi.")
    else:
        await msg.reply_text("❌ Unmute bo‘lmadi. Bot adminmi?")

async def delete_join_leave(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Kirdi/chiqdini o‘chiradi
    if not is_allowed_group(update):
        return
    await delete_message_safely(update, context)

async def link_cleaner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Faqat allowed groupda ishlaydi
    if not is_allowed_group(update):
        return

    msg = update.effective_message
    if not msg:
        return

    # Bot o'zi / adminlar link tashlasa o‘chirmaymiz
    from_user = msg.from_user
    if not from_user:
        return

    if await is_admin(update, context, from_user.id):
        return

    # Faqat text/caption ichida link bo‘lsa ishlaydi, aks holda jim
    full_text = extract_text_and_caption(update)
    if not (has_link_text(full_text) or has_link_entities(msg)):
        return

    # 1) Xabarni o‘chirish
    await delete_message_safely(update, context)

    # 2) Foydalanuvchini mute qilish
    ok = await mute_user(ALLOWED_CHAT_ID, from_user.id, MUTE_MINUTES, context)
    if ok:
        log.info("Muted user_id=%s for %s min (link)", from_user.id, MUTE_MINUTES)
    else:
        log.warning("Failed to mute user_id=%s (need admin perms)", from_user.id)

# ================== MAIN ==================
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # Admin-only info/controls
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("setmutemin", setmutemin_cmd))
    app.add_handler(CommandHandler("unmute", unmute_cmd))

    # Delete join/leave service messages
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, delete_join_leave))
    app.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, delete_join_leave))

    # Link cleaner (text + captions)
    app.add_handler(MessageHandler((filters.TEXT | filters.Caption(True)), link_cleaner))

    log.info("✅ Cleaner bot ishga tushdi. ALLOWED_CHAT_ID=%s mute=%smin", ALLOWED_CHAT_ID, MUTE_MINUTES)
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
