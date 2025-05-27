import csv
import os
import random
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from datetime import time
import pytz

# משתני סביבה
TOKEN = os.getenv("TELEGRAM_TOKEN")
TIMEZONE = os.getenv("TIMEZONE", "Asia/Jerusalem")
CHAT_ID = int(os.getenv("YOUR_CHAT_ID"))

# טוען מילים מקובץ CSV
WORDS = []
with open("italian_words_clean.csv", newline='', encoding='utf-8') as csvfile:
    reader = csv.DictReader(csvfile)
    for row in reader:
        WORDS.append((row["italian_word"].strip(), row["translation"].strip()))

# מעקב אחר חידונים לפי משתמש
user_quiz = {}

# מחזיר 5 מילים רנדומליות
def get_daily_words():
    sample = random.sample(WORDS, 5)
    message = "המילים שלך להיום:\n"
    for i, (it, tr) in enumerate(sample, 1):
        message += f"{i}. {it} – {tr}\n"
    return message.strip()

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Ciao! אני הבוט שלך ללימוד איטלקית. שלח /daily למילים יומיות או /quiz לחידון.")

# /daily
async def daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(get_daily_words())

# /quiz
async def quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    word, translation = random.choice(WORDS)
    user_id = update.effective_user.id
    user_quiz[user_id] = (word, translation.lower())
    await update.message.reply_text(f"מה הפירוש של: {word}?")

# בודק תשובה של המשתמש
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in user_quiz:
        correct = user_quiz[user_id][1]
        answer = update.message.text.lower().strip()
        del user_quiz[user_id]
        if correct in answer:
            await update.message.reply_text("נכון! כל הכבוד.")
        else:
            await update.message.reply_text(f"לא בדיוק... הפירוש הוא: {correct}")
    else:
        await update.message.reply_text("שלח /quiz כדי להתחיל חידון או /daily למילים יומיות.")

# שליחה יומית אוטומטית
async def send_daily_message(context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=CHAT_ID, text=get_daily_words())

# הרצת הבוט
if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("daily", daily))
    app.add_handler(CommandHandler("quiz", quiz))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # תזמון יומי ב-9:00 לפי שעון ישראל
    jst = pytz.timezone(TIMEZONE)
    app.job_queue.run_daily(send_daily_message, time=time(9, 0, tzinfo=jst))

    app.run_polling()