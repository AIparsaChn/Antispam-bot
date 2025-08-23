import asyncio
import datetime
from typing import Optional

import telebot
from telebot.types import Message
from telebot.async_telebot import AsyncTeleBot, ExceptionHandler
from telebot.asyncio_handler_backends import BaseMiddleware, CancelUpdate
from telebot.formatting import munderline
from redis.asyncio import Redis

import config

logger = telebot.async_telebot.logger
telebot.async_telebot.logger.setLevel("INFO")

class BotExceptionHandler(ExceptionHandler):
    async def handle(self, exception):
        logger.error(exception, exc_info=True)

TOKEN = config.TOKEN
bot = AsyncTeleBot(
    token=TOKEN,
    exception_handler=BotExceptionHandler(),
)

def time_string_to_seconds(time_str: str):
    hours, minutes, seconds = time_str.split(":")
    total_seconds = int(hours)*3600 + int(minutes)*60 + int(seconds)
    return total_seconds

WARNING_TIMES = 3
SPAM_SECOND_THRESHOLD = 10
SPAM_COUNT_MESSAGE_THRESHOLD = 4
RESTRICTED_TIME = "2:00:00"
restricted_time_seconds = time_string_to_seconds(RESTRICTED_TIME)

class AntiSpamMiddleware(BaseMiddleware):
    _redis_db: Optional[Redis] = None
    restricted_key = "restrict:"
    warning_key = "warning:"
    spam_key = "spam:"

    def __init__(self):
        self.update_types = ["message"]

    async def pre_process(self, message: Message, data):
        if message.from_user.is_bot:
            print("It's a bot")
        if self._redis_db is None:
            await self.__initialize_connection()

        user_id = message.from_user.id
        if await self._redis_db.get(self.restricted_key+str(user_id)):
            return CancelUpdate()

        elif await self.is_spam(user_id):
            warning_count = await self.set_warning(user_id)
            await bot.send_message(
                chat_id=message.chat.id,
                text=f"""This is your {warning_count} warning(s).
if you get warning more than three times you will be restricted for {RESTRICTED_TIME}."""
            )
            if warning_count >= 3:
                await self.restrict_user(user_id)
                await bot.send_message(
                    chat_id=message.chat.id,
                    text=f"You've restricted for {munderline(RESTRICTED_TIME)}.",
                    parse_mode="markdown"
                )

    async def post_process(self, message, data, exception):
        pass

    async def is_spam(self, user_id):
        spam_key = self.spam_key+str(user_id)
        message_count = await self._redis_db.incr(spam_key)

        if message_count == 1:
            await self._redis_db.expire(
                name=spam_key,
                time=SPAM_SECOND_THRESHOLD
            )
        if message_count >= SPAM_COUNT_MESSAGE_THRESHOLD:
            return True
        return False

    async def set_warning(self, user_id):
        warning_key = self.warning_key+str(user_id)
        warning_count = await self._redis_db.incr(warning_key)
        spam_key = self.spam_key+str(user_id)
        await self._redis_db.delete(spam_key)
        return warning_count

    async def restrict_user(self, user_id):
        await self._redis_db.set(
            name=self.restricted_key+str(user_id),
            value=f"restricted at {datetime.datetime.now()}",
            ex=restricted_time_seconds
        )
        warning_key = self.warning_key+str(user_id)
        await self._redis_db.delete(warning_key)

    @staticmethod
    async def _create_connection():
        return await Redis(
            host="localhost",
            port=6379,
            db=0,
            decode_responses=True
        )

    async def __initialize_connection(self):
        self._redis_db = await self._create_connection()


bot.setup_middleware(AntiSpamMiddleware())


@bot.message_handler()
async def echo_message(message: Message):
    await bot.send_message(
        chat_id=message.chat.id,
        text=message.text
    )


if __name__ == "__main__":
    asyncio.run(bot.infinity_polling(), debug=True)
