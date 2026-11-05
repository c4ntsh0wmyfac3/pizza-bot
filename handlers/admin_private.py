from aiogram import F, types, Router
from aiogram.filters import CommandStart, Command

admin_private_router = Router()

@admin_private_router(CommandStart())
async def cmd_start(message: types.Message):
    await message.answer("Welcome, admin!")
