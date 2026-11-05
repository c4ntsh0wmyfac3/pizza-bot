from aiogram import F, types, Router
from aiogram.filters import CommandStart, Command
from kbs import reply

user_private_router = Router()

# Start command
@user_private_router.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.answer("Hi, i'm your personal assistent!", reply_markup=reply.kb_start)

# Help command
@user_private_router.message(F.text.lower() == "help")
@user_private_router.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer("Help page.")

# End command
@user_private_router.message(F.text.lower() == "end")
@user_private_router.message(Command("end"))
async def cmd_help(message: types.Message):
    await message.answer("The End.", reply_markup=reply.kb_end)

@user_private_router.message(F.text.lower() == "hey")
@user_private_router.message(Command("hey"))
async def cmd_help(message: types.Message):
    await message.answer("Hey, how are you? I'm your assistent! maybe;)")

@user_private_router.message(F.photo)
async def cmd_photo(message: types.Message):
    await message.answer(f"{message.photo} is cool")

# Echo message
@user_private_router.message()
async def cmd_echo(message: types.Message):
    await message.answer(message.text)

