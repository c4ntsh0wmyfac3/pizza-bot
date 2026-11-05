from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

kb_start = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="Menu"),
                KeyboardButton(text="About store"),
            ],
            [
                KeyboardButton(text="Shipping options"),
                KeyboardButton(text="Payment options"),
            ]
        ],
        resize_keyboard=True,
        input_field_placeholder="Select option"
)

kb_end = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="Support"),
                KeyboardButton(text="Other social media")
            ],
            [
                KeyboardButton(text="YouTube"),
                KeyboardButton(text="Telegram")
            ]
        ],
        resize_keyboard=True,
        input_field_placeholder="Other socials"
)
