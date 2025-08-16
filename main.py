import asyncio

import telebot
from telebot.async_telebot import AsyncTeleBot, ExceptionHandler

import config

logger = telebot.async_telebot.logger
telebot.async_telebot.logger.setLevel("INFO")

class BotExceptionHandler(ExceptionHandler):
    async def handle(self, exception):
        logger.error(exception, exc_info=True)

TOKEN = config.TOKEN
bot = AsyncTeleBot(
    token=TOKEN,
    exception_handler=BotExceptionHandler()
)


if __name__ == "__main__":
    asyncio.run(bot.infinity_polling())
