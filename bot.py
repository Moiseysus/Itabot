import csv
import os
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)
from datetime import time
import pytz
from difflib import SequenceMatcher

# משתני סביבה
TOKEN = os.getenv("TELEGRAM_TOKEN")
TIMEZONE = os.getenv("TIMEZONE", "Asia/Jerusalem")
CHAT_ID = int(os.getenv("YOUR_CHAT_ID"))

# טעינת המילים מהקובץ
WORDS = []
with open("italian_words_clean.csv", newline='', encoding='utf-8') as csvfile:
    reader = csv.DictReader(csvfile)
    for row in reader:
        WORDS.append((row["italian_word"].strip(), row["translation"].strip()))

# סטטוס חידון לכל משתמש
user_quiz = {}

# יוצר הודעה עם 5 מילים רנדומליות
def get_daily_words():
    sample = random.sample(WORDS, 5)
    message = "המילים שלך להיום:\n"
    for i, (it, tr) in enumerate(sample, 1):
        message += f"{i}. {it} – {tr}\n"
    return message.strip()

# קביעת רמת דמיון בין מילים
def is_close_match(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio() > 0.75

# התחלה
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Ciao! אני הבוט שלך ללימוד איטלקית. שלח /daily למילים יומיות או /quiz לחידון.")

# פקודה למילים יומיות
async def daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(get_daily_words())

# התחלת חידון
async def quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    word, translation = random.choice(WORDS)
    user_id = update.effective_user.id
    user_quiz[user_id] = (word, translation.lower())
    
    # יצירת כפתור "דלג"
    keyboard = [
        [InlineKeyboardButton("דלג", callback_data="skip_quiz")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"מה הפירוש של: {word}?",
        reply_markup=reply_markup
    )

# טיפול בלחיצה על כפתור "דלג"
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "skip_quiz":
        user_id = query.from_user.id
        if user_id in user_quiz:
            del user_quiz[user_id]
        await query.edit_message_text("עברת לשאלה הבאה. שלח /quiz כדי לנסות שוב!")

# בדיקת תשובה מהמשתמש
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in user_quiz:
        correct = user_quiz[user_id][1]
        answer = update.message.text.strip().lower()
        del user_quiz[user_id]

        if answer == correct:
            await update.message.reply_text("מעולה! ענית נכון.")
        elif is_close_match(answer, correct):
            await update.message.reply_text(f"כמעט! התכוונת ל: {correct}")
        else:
            await update.message.reply_text(f"לא נכון. התשובה היא: {correct}")
    else:
        await update.message.reply_text("שלח /quiz כדי להתחיל חידון או /daily למילים יומיות.")

# שליחה יומית אוטומטית
async def send_daily_message(context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=CHAT_ID, text=get_daily_words())

# הרצה
if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()
    job_queue = app.job_queue

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("daily", daily))
    app.add_handler(CommandHandler("quiz", quiz))
    app.add_handler(CallbackQueryHandler(button_handler))  # כפתור "דלג"
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    jst = pytz.timezone(TIMEZONE)
    job_queue.run_daily(send_daily_message, time=time(9, 0, tzinfo=jst))

    app.run_polling()