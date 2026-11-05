# Import asyncio and some libs
import asyncio
from os import getenv
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command
from dotenv import load_dotenv
# Import handlers
from handlers.user_private import user_private_router
load_dotenv()

bot = Bot(getenv('TOKEN'))
dp = Dispatcher()

dp.include_router(user_private_router)

async def main():
    await dp.start_polling(bot)

asyncio.run(main())
