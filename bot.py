
import csv
import os
import random
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from datetime import time
import pytz

# Load environment variables
TOKEN = os.getenv("TELEGRAM_TOKEN")
TIMEZONE = os.getenv("TIMEZONE", "Asia/Jerusalem")

# Load words from CSV
WORDS = []
with open("italian_words_clean.csv", newline='', encoding='utf-8') as csvfile:
    reader = csv.DictReader(csvfile)
    for row in reader:
        WORDS.append((row["italian_word"].strip(), row["translation"].strip()))

# Per-user quiz state
user_quiz = {}

# Format 5 random words
def get_daily_words():
    sample = random.sample(WORDS, 5)
    message = "המילים שלך להיום:\n"
    for i, (it, tr) in enumerate(sample, 1):
        message += f"{i}. {it} – {tr}\n"
    return message.strip()

# Command: /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Ciao! אני הבוט שלך ללימוד איטלקית. שלח /daily למילים יומיות או /quiz לחידון.")

# Command: /daily
async def daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(get_daily_words())

# Command: /quiz
async def quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    word, translation = random.choice(WORDS)
    user_id = update.effective_user.id
    user_quiz[user_id] = (word, translation.lower())
    await update.message.reply_text(f"מה הפירוש של: {word}?")

# Handle answers
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

# Schedule daily message
async def send_daily_message(context: ContextTypes.DEFAULT_TYPE):
    chat_id = os.getenv("YOUR_CHAT_ID")
    if chat_id:
        await context.bot.send_message(chat_id=int(chat_id), text=get_daily_words())

# Main
if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("daily", daily))
    app.add_handler(CommandHandler("quiz", quiz))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Daily job
    jst = pytz.timezone(TIMEZONE)
    app.job_queue.run_daily(send_daily_message, time=time(9, 0, tzinfo=jst))

    app.run_polling()
