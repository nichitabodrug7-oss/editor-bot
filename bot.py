"""
Редактор-помощник — Telegram-бот для журфака (бесплатная версия)
--------------------------------------------------------------------
Присылаешь текст — бот проверяет грамматику, штампы, "воду",
предлагает варианты заголовков. Работает через Google Gemini
(бесплатный API) и крутится на бесплатном тарифе Render.com.

Переменные окружения (задаются на хостинге, не в коде!):
    TELEGRAM_BOT_TOKEN  — токен от @BotFather
    GEMINI_API_KEY      — ключ с aistudio.google.com/apikey
    WEBHOOK_URL         — публичный адрес сервиса на Render,
                           например https://editor-bot.onrender.com
                           (без слэша на конце)

Особенность бесплатного тарифа Render: сервис засыпает после
15 минут без запросов. Первое сообщение после паузы может
обрабатываться до минуты — это нормально, не баг.
"""

import os
import logging

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
import google.generativeai as genai

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("editor-bot")

TELEGRAM_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
GEMINI_KEY = os.environ["GEMINI_API_KEY"]
WEBHOOK_URL = os.environ["WEBHOOK_URL"].rstrip("/")
PORT = int(os.environ.get("PORT", 8443))

genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel("gemini-2.5-flash")

SYSTEM_PROMPT = (
    "Ты — опытный редактор в русскоязычной журналистике. Тебе присылают "
    "черновик текста студента журфака (заметка, статья, интервью). "
    "Разбери его по пунктам, кратко и по делу:\n\n"
    "1. Грамматика и пунктуация — только реальные ошибки, с исправлением.\n"
    "2. Штампы и канцелярит — конкретные фразы из текста, которые стоит "
    "заменить, с примером замены.\n"
    "3. «Вода» — предложения или абзацы, которые не несут информации.\n"
    "4. Заголовок — предложи 3 варианта, разного тона (нейтральный, "
    "интригующий, разговорный).\n\n"
    "Пиши по-русски, коротко, без общих фраз вроде «текст хороший». "
    "Если текст короче пары предложений или это не связный текст — "
    "вежливо попроси прислать черновик статьи.\n\n"
    "Вот текст для разбора:\n\n"
)

MAX_CHARS = 6000


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Я редактор-помощник для журфака.\n\n"
        "Пришли мне текст статьи или заметки — проверю грамматику, "
        "штампы, «воду» и предложу заголовки.\n\n"
        f"Ограничение: до {MAX_CHARS} символов за раз.\n\n"
        "Если бот долго не отвечал — первое сообщение может обрабатываться "
        "до минуты, он «просыпается»."
    )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if len(text) > MAX_CHARS:
        await update.message.reply_text(
            f"Текст длинноват ({len(text)} символов) — пришли фрагмент "
            f"до {MAX_CHARS} символов, например, по частям."
        )
        return

    thinking_msg = await update.message.reply_text("Читаю и разбираю…")

    try:
        response = model.generate_content(SYSTEM_PROMPT + text)
        result = response.text
    except Exception as e:
        log.exception("Gemini API error")
        await thinking_msg.edit_text(f"Не получилось обработать текст: {e}")
        return

    if len(result) <= 4096:
        await thinking_msg.edit_text(result)
    else:
        await thinking_msg.delete()
        for i in range(0, len(result), 4096):
            await update.message.reply_text(result[i:i + 4096])


def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    log.info("Запускаю через webhook на порт %s", PORT)
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=TELEGRAM_TOKEN,
        webhook_url=f"{WEBHOOK_URL}/{TELEGRAM_TOKEN}",
    )


if __name__ == "__main__":
    main()
