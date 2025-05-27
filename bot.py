import csv
import os
import random
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
from datetime import datetime, timedelta, time
import pytz
from difflib import SequenceMatcher

TOKEN = os.getenv("TELEGRAM_TOKEN")
TIMEZONE = os.getenv("TIMEZONE", "Asia/Jerusalem")
CHAT_ID = int(os.getenv("YOUR_CHAT_ID"))
PROGRESS_FILE = "progress.json"

# טוען מילים
WORDS = []
with open("italian_words_clean.csv", newline='', encoding='utf-8') as csvfile:
    reader = csv.DictReader(csvfile)
    for row in reader:
        WORDS.append((row["italian_word"].strip(), row["translation"].strip()))

# מצב חידון
user_quiz = {}
pending_confirmation = {}

# טוען מעקב התקדמות
def load_progress():
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_progress(data):
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

progress_data = load_progress()

# מחזיר מילים רלוונטיות להיום
def get_due_words(chat_id, limit=5):
    today = datetime.now().date()
    due = []
    user_data = progress_data.get(str(chat_id), {})

    for word, (it, tr) in enumerate(WORDS):
        entry = user_data.get(it, {})
        last_seen = datetime.fromisoformat(entry.get("last_seen")) if entry.get("last_seen") else None
        streak = entry.get("streak", 0)

        days_delay = 1 if streak == 0 else 2 if streak == 1 else 3
        next_time = (last_seen + timedelta(days=days_delay)) if last_seen else datetime.min

        if next_time.date() <= today:
            due.append((it, tr))

        if len(due) >= limit:
            break

    # אם אין מספיק מילים → מוסיף חדשות
    if len(due) < limit:
        used_words = {w for w in user_data}
        extras = [(it, tr) for it, tr in WORDS if it not in used_words]
        random.shuffle(extras)
        due += extras[:limit - len(due)]

    return due

# דמיון בין מילים
def is_close_match(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio() > 0.75

# בדיקת תשובה
def is_correct(answer, translations):
    for option in translations:
        if answer == option:
            return True
    return False

def is_almost_correct(answer, translations):
    for option in translations:
        if is_close_match(answer, option):
            return option
    return None

# מילים יומיות
def get_daily_words(chat_id):
    sample = get_due_words(chat_id)
    message = "המילים שלך להיום:\n"
    for i, (it, tr) in enumerate(sample, 1):
        message += f"{i}. {it} – {tr}\n"
    return message.strip()

# START
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Ciao! אני הבוט שלך ללימוד איטלקית. שלח /daily או /quiz.")

# DAILY
async def daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(get_daily_words(update.effective_user.id))

# QUIZ
async def quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    word, translation = random.choice(WORDS)
    user_id = update.effective_user.id
    user_quiz[user_id] = (word, translation)

    keyboard = [
        [InlineKeyboardButton("דלג", callback_data="skip_quiz")]
    ]
    await update.message.reply_text(
        f"מה הפירוש של: {word}?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# תשובה
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    answer = update.message.text.strip().lower()

    if user_id in pending_confirmation:
        correct = pending_confirmation[user_id]["correct"]
        word = pending_confirmation[user_id]["word"]
        del pending_confirmation[user_id]

        if answer in ["כן", "כן.", "y", "yes"]:
            await update.message.reply_text("מעולה! נחשב כתשובה נכונה.")
            update_progress(user_id, word, correct=True)
        else:
            await update.message.reply_text(f"לא נורא! הפירוש הוא: {correct}")
            update_progress(user_id, word, correct=False)
        return

    if user_id in user_quiz:
        word, raw_translation = user_quiz[user_id]
        del user_quiz[user_id]

        options = [t.strip().lower() for t in raw_translation.replace("–", ",").replace("-", ",").split(",")]

        if is_correct(answer, options):
            await update.message.reply_text("מעולה! ענית נכון.")
            update_progress(user_id, word, correct=True)
        else:
            close = is_almost_correct(answer, options)
            if close:
                pending_confirmation[user_id] = {"correct": close, "word": word}
                keyboard = [
                    [
                        InlineKeyboardButton("כן", callback_data="confirm_yes"),
                        InlineKeyboardButton("לא", callback_data="confirm_no")
                    ]
                ]
                await update.message.reply_text(
                    f"נראה שהתכוונת ל: {close} — נכון?",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            else:
                await update.message.reply_text(f"לא בדיוק... הפירוש הוא: {raw_translation}")
                update_progress(user_id, word, correct=False)
    else:
        await update.message.reply_text("שלח /quiz כדי להתחיל חידון או /daily למילים יומיות.")

# טיפול בלחצנים
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    if query.data == "skip_quiz":
        if user_id in user_quiz:
            del user_quiz[user_id]
        await query.edit_message_text("שאלה דולגה. שלח /quiz כדי להמשיך.")

    elif query.data in ["confirm_yes", "confirm_no"]:
        if user_id in pending_confirmation:
            data = pending_confirmation[user_id]
            correct = data["correct"]
            word = data["word"]
            del pending_confirmation[user_id]

            if query.data == "confirm_yes":
                await query.edit_message_text("מעולה! נחשב כתשובה נכונה.")
                update_progress(user_id, word, correct=True)
            else:
                await query.edit_message_text(f"אוקיי! הפירוש הוא: {correct}")
                update_progress(user_id, word, correct=False)

# עדכון התקדמות
def update_progress(chat_id, word, correct):
    chat_data = progress_data.setdefault(str(chat_id), {})
    word_entry = chat_data.setdefault(word, {"streak": 0, "last_seen": None})

    if correct:
        word_entry["streak"] = min(word_entry["streak"] + 1, 2)
    else:
        word_entry["streak"] = 0

    word_entry["last_seen"] = datetime.now().isoformat()
    save_progress(progress_data)

# שליחה יומית
async def send_daily_message(context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=CHAT_ID, text=get_daily_words(CHAT_ID))

# הרצה
if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()
    job_queue = app.job_queue

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("daily", daily))
    app.add_handler(CommandHandler("quiz", quiz))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    jst = pytz.timezone(TIMEZONE)
    job_queue.run_daily(send_daily_message, time=time(9, 0, tzinfo=jst))

    app.run_polling()