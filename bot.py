import os
import re
import json
import time
import logging
from typing import Optional, Set

from telegram import Update
from telegram.constants import ChatType
from telegram.error import BadRequest
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from telegram import ChatPermissions

# ================== ENV ==================
BOT_TOKEN = (os.getenv("BOT_TOKEN") or "").strip()
ALLOWED_CHAT_ID = int((os.getenv("ALLOWED_CHAT_ID") or "0").strip() or "0")

# Admin IDs: "123,456" (optional, empty bo'lsa hech kim admin emas deb oladi)
ADMIN_IDS_RAW = (os.getenv("ADMIN_IDS") or "").strip()
ADMIN_IDS: Set[int] = set()
if ADMIN_IDS_RAW:
    for x in ADMIN_IDS_RAW.split(","):
        x = x.strip()
        if x.isdigit():
            ADMIN_IDS.add(int(x))

# Default mute time (minutes). /setmutemin bilan o'zgartirasiz.
STATE_FILE = (os.getenv("STATE_FILE") or "mod_state.json").strip()
DEFAULT_MUTE_MIN = int((os.getenv("DEFAULT_MUTE_MIN") or "1440").strip() or "1440")  # 24 soat

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

# ================== STATE ==================
def load_state():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"mute_min": DEFAULT_MUTE_MIN}
    except Exception:
        log.exception("state load failed")
        return {"mute_min": DEFAULT_MUTE_MIN}

def save_state(s):
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(s, f, ensure_ascii=False, indent=2)
    except Exception:
        log.exception("state save failed")

STATE = load_state()
STATE.setdefault("mute_min", DEFAULT_MUTE_MIN)

def get_mute_seconds() -> int:
    m = int(STATE.get("mute_min", DEFAULT_MUTE_MIN))
    m = max(1, m)
    return m * 60

# ================== HELPERS ==================
LINK_RE = re.compile(
    r"(?i)\b("
    r"https?://|"
    r"www\.|"
    r"t\.me/|"
    r"telegram\.me/|"
    r"bit\.ly/|"
    r"tinyurl\.com/|"
    r"goo\.gl/|"
    r"wa\.me/|"
    r"instagram\.com/|"
    r"facebook\.com/|"
    r"youtube\.com/|"
    r"youtu\.be/|"
    r"discord\.gg/|"
    r"joinchat/|"
    r"@[\w_]{4,}"
    r")"
)

def is_allowed_group(update: Update) -> bool:
    chat = update.effective_chat
    return bool(chat and chat.id == ALLOWED_CHAT_ID)

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

def has_link_text(text: str) -> bool:
    if not text:
        return False
    return bool(LINK_RE.search(text))

def has_link_entities(msg) -> bool:
    # URL / TEXT_LINK entity bo'lsa ham link hisoblaymiz
    ents = []
    try:
        ents.extend(msg.entities or [])
    except Exception:
        pass
    try:
        ents.extend(msg.caption_entities or [])
    except Exception:
        pass

    for e in ents:
        if e.type in ("url", "text_link"):
            return True
        # mention ham linkga o'xshash bo'lishi mumkin, lekin yuqorida regex ham bor
    return False

async def delete_message_safe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=update.effective_message.message_id)
    except Exception:
        pass

async def mute_user(context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_id: int, seconds: int) -> bool:
    until_date = int(time.time()) + seconds
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
            until_date=until_date,
        )
        return True
    except BadRequest as e:
        log.warning("restrict failed: %s", e)
        return False
    except Exception:
        log.exception("restrict failed")
        return False

async def unmute_user(context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_id: int) -> bool:
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
        can_invite_users=True,
    )
    try:
        await context.bot.restrict_chat_member(
            chat_id=chat_id,
            user_id=user_id,
            permissions=perms,
        )
        return True
    except Exception:
        return False

# ================== COMMANDS ==================
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # faqat adminlar ko'rsin (spam bo'lmasin)
    if not is_allowed_group(update):
        return
    uid = update.effective_user.id if update.effective_user else 0
    if not is_admin(uid):
        return
    await update.effective_message.reply_text(
        "✅ Cleaner bot ishlayapti.\n"
        "- Link tashlansa: o'chadi + user mute\n"
        "- Kirdi/chiqdi: o'chadi\n\n"
        "Admin:\n"
        "/setmutemin 60  (mute minut)\n"
        "/unmute (reply qilib)"
    )

async def setmutemin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed_group(update):
        return
    uid = update.effective_user.id if update.effective_user else 0
    if not is_admin(uid):
        return

    if not context.args:
        await update.effective_message.reply_text(f"Hozirgi mute: {STATE['mute_min']} minut.\nMisol: /setmutemin 60")
        return

    try:
        m = int(context.args[0])
        m = max(1, m)
        STATE["mute_min"] = m
        save_state(STATE)
        await update.effective_message.reply_text(f"✅ Mute vaqti: {m} minut.")
    except Exception:
        await update.effective_message.reply_text("Noto‘g‘ri. Misol: /setmutemin 60")

async def unmute_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed_group(update):
        return
    uid = update.effective_user.id if update.effective_user else 0
    if not is_admin(uid):
        return

    msg = update.effective_message
    if not msg.reply_to_message or not msg.reply_to_message.from_user:
        await msg.reply_text("Unmute qilish uchun reply qiling: /unmute")
        return

    target_id = msg.reply_to_message.from_user.id
    ok = await unmute_user(context, update.effective_chat.id, target_id)
    if ok:
        await msg.reply_text("✅ Unmute qilindi.")
    else:
        await msg.reply_text("❌ Unmute bo‘lmadi. Bot adminmi? Restrict ruxsati bormi?")

# ================== HANDLERS ==================
async def delete_join_leave(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # "kirdi/chiqdi" service messages
    if not is_allowed_group(update):
        return
    await delete_message_safe(update, context)

async def link_cleaner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed_group(update):
        return

    msg = update.effective_message
    if not msg:
        return

    # admin link tashlasa o'chirmaymiz (xohlasangiz o'chiramiz)
    from_user = msg.from_user
    if from_user and is_admin(from_user.id):
        return

    text = (msg.text or "") + "\n" + (msg.caption or "")
    if not (has_link_text(text) or has_link_entities(msg)):
        return

    # 1) xabarni o'chirish
    await delete_message_safe(update, context)

    # 2) userni mute qilish (yozolmaydi)
    if from_user:
        await mute_user(
            context=context,
            chat_id=update.effective_chat.id,
            user_id=from_user.id,
            seconds=get_mute_seconds(),
        )

# ================== MAIN ==================
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # Admin buyruqlar
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("setmutemin", setmutemin_cmd))
    app.add_handler(CommandHandler("unmute", unmute_cmd))

    # Join/leave delete
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, delete_join_leave))
    app.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, delete_join_leave))

    # Link cleaner (text/caption)
    app.add_handler(MessageHandler((filters.TEXT | filters.Caption(True)), link_cleaner))

    log.info("✅ Cleaner bot ishga tushdi. ALLOWED_CHAT_ID=%s", ALLOWED_CHAT_ID)
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
