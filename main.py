import asyncio
import logging
import os
from datetime import datetime

import aiosqlite
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardRemove,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

# ─────────────────────────────────────────────
# CONFIG (put these in environment variables in production)
# ─────────────────────────────────────────────
BOT_TOKEN = os.getenv("TOKEN")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "123456789"))  # your user ID or group ID
DB_PATH = "tickets.db"

logging.basicConfig(level=logging.INFO)

# ─────────────────────────────────────────────
# DATABASE HELPERS
# ─────────────────────────────────────────────
async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id BIGINT NOT NULL,
                username TEXT,
                category TEXT,
                subject TEXT,
                details TEXT,
                status TEXT DEFAULT 'new',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.commit()


async def create_ticket(data: dict) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO tickets (user_id, username, category, subject, details) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                data["user_id"],
                data.get("username"),
                data.get("category"),
                data.get("subject"),
                data.get("details"),
            ),
        )
        await db.commit()
        return cursor.lastrowid


async def update_ticket_status(ticket_id: int, status: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE tickets SET status = ? WHERE id = ?", (status, ticket_id)
        )
        await db.commit()


async def get_ticket(ticket_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


# ─────────────────────────────────────────────
# FSM STATES
# ─────────────────────────────────────────────
class TicketForm(StatesGroup):
    category = State()
    subject = State()
    details = State()
    confirm = State()


# ─────────────────────────────────────────────
# KEYBOARDS
# ─────────────────────────────────────────────
CATEGORIES = ["💳 Billing", "🛠 Technical", "📦 Delivery", "❓ Other"]


def category_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for i, cat in enumerate(CATEGORIES):
        builder.button(text=cat, callback_data=f"cat_{i}")
    builder.adjust(2)
    return builder.as_markup()


def confirm_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Submit", callback_data="confirm_submit")
    builder.button(text="✏️ Edit subject", callback_data="edit_subject")
    builder.button(text="✏️ Edit details", callback_data="edit_details")
    builder.button(text="❌ Cancel", callback_data="cancel")
    builder.adjust(2, 2)
    return builder.as_markup()


def admin_ticket_kb(ticket_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🛠 In work", callback_data=f"status_{ticket_id}_in_progress")
    builder.button(text="✅ Done", callback_data=f"status_{ticket_id}_done")
    builder.button(text="❌ Rejected", callback_data=f"status_{ticket_id}_rejected")
    builder.button(text="💬 Reply", callback_data=f"reply_{ticket_id}")
    builder.adjust(3, 1)
    return builder.as_markup()


# ─────────────────────────────────────────────
# ROUTERS
# ─────────────────────────────────────────────
customer_router = Router()
admin_router = Router()


# ─── CUSTOMER FLOW ───────────────────────────
@customer_router.message(CommandStart())
async def start_handler(message: Message, state: FSMContext) -> None:
    await state.clear()
    builder = InlineKeyboardBuilder()
    builder.button(text="🎫 Create a ticket", callback_data="new_ticket")
    await message.answer(
        "👋 Welcome! I’m the support bot.\n\n"
        "Press the button below to open a ticket. You can also use /cancel at any time.",
        reply_markup=builder.as_markup(),
    )


@customer_router.callback_query(F.data == "new_ticket")
async def new_ticket(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.message.edit_text(
        "📂 Choose a category:", reply_markup=category_kb()
    )
    await state.set_state(TicketForm.category)
    await callback.answer()


@customer_router.callback_query(TicketForm.category, F.data.startswith("cat_"))
async def process_category(callback: CallbackQuery, state: FSMContext) -> None:
    idx = int(callback.data.split("_")[1])
    await state.update_data(category=CATEGORIES[idx])
    await state.set_state(TicketForm.subject)
    await callback.message.edit_text(
        "📝 Briefly describe the issue (5–100 characters):"
    )
    await callback.answer()


@customer_router.message(TicketForm.subject, F.text)
async def process_subject(message: Message, state: FSMContext) -> None:
    text = message.text.strip()
    if not (5 <= len(text) <= 100):
        await message.answer("⚠️ Please send a subject between 5 and 100 characters.")
        return
    await state.update_data(subject=text)
    await state.set_state(TicketForm.details)
    await message.answer(
        "📄 Now provide more details. You can also send a photo or file."
    )


@customer_router.message(TicketForm.details, F.text | F.photo | F.document)
async def process_details(message: Message, state: FSMContext) -> None:
    details = message.text or (message.caption if message.caption else "[attachment]")
    await state.update_data(details=details, user_id=message.from_user.id,
                            username=message.from_user.username or "—")
    data = await state.get_data()

    summary = (
        f"🎫 <b>Ticket summary</b>\n\n"
        f"<b>Category:</b> {data['category']}\n"
        f"<b>Subject:</b> {data['subject']}\n"
        f"<b>Details:</b> {data['details']}\n\n"
        f"Is everything correct?"
    )
    await state.set_state(TicketForm.confirm)
    await message.answer(summary, reply_markup=confirm_kb(), parse_mode="HTML")


# ─── EDIT FLOWS (inline editing) ─────────────
@customer_router.callback_query(TicketForm.confirm, F.data == "edit_subject")
async def edit_subject(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(TicketForm.subject)
    await callback.message.answer("📝 Send the new subject (5–100 characters):")
    await callback.answer()


@customer_router.callback_query(TicketForm.confirm, F.data == "edit_details")
async def edit_details(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(TicketForm.details)
    await callback.message.answer("📄 Send the new details:")
    await callback.answer()


# ─── CONFIRM & SUBMIT ────────────────────────
@customer_router.callback_query(TicketForm.confirm, F.data == "confirm_submit")
async def submit_ticket(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    await state.clear()  # clear state first to prevent double-tap

    ticket_id = await create_ticket(data)

    # Notify customer
    await callback.message.edit_text(
        f"✅ Ticket <b>#{ticket_id}</b> created!\n"
        f"We’ll notify you when the status changes.",
        parse_mode="HTML",
    )

    # Notify admin with a card
    admin_text = (
        f"🎫 <b>New ticket #{ticket_id}</b>\n\n"
        f"<b>From:</b> @{data['username']} (<code>{data['user_id']}</code>)\n"
        f"<b>Category:</b> {data['category']}\n"
        f"<b>Subject:</b> {data['subject']}\n"
        f"<b>Details:</b> {data['details']}"
    )
    await callback.bot.send_message(
        ADMIN_CHAT_ID, admin_text, reply_markup=admin_ticket_kb(ticket_id),
        parse_mode="HTML",
    )
    await callback.answer("Submitted!")


@customer_router.callback_query(TicketForm.confirm, F.data == "cancel")
async def cancel_ticket(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("❌ Ticket creation cancelled. Use /start to begin again.")
    await callback.answer()


# ─── CATCH-ALL for unexpected input in FSM ───
@customer_router.message(StateFilter(TicketForm))
async def fsm_fallback(message: Message) -> None:
    await message.answer(
        "⚠️ Please use the buttons above or send the requested text.\n"
        "Use /cancel to abort."
    )


@customer_router.message(Command("cancel"))
async def cancel_command(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Cancelled. Use /start to create a new ticket.",
                         reply_markup=ReplyKeyboardRemove())


# ─── ADMIN HANDLERS ──────────────────────────
@admin_router.callback_query(F.data.startswith("status_"))
async def admin_status_change(callback: CallbackQuery) -> None:
    # callback.data = "status_<ticket_id>_<new_status>"
    _, ticket_id_str, new_status = callback.data.split("_", 2)
    ticket_id = int(ticket_id_str)

    ticket = await get_ticket(ticket_id)
    if not ticket:
        await callback.answer("Ticket not found", show_alert=True)
        return

    await update_ticket_status(ticket_id, new_status)

    status_labels = {
        "in_progress": "🛠 In work",
        "done": "✅ Done",
        "rejected": "❌ Rejected",
    }
    label = status_labels.get(new_status, new_status)

    # Notify customer
    await callback.bot.send_message(
        ticket["user_id"],
        f"🔔 Your ticket <b>#{ticket_id}</b> is now <b>{label}</b>.",
        parse_mode="HTML",
    )

    # Confirm to admin (edit the card to remove buttons or mark it)
    await callback.message.edit_text(
        f"{callback.message.text}\n\n— Status: {label} —",
        parse_mode="HTML",
    )
    await callback.answer(f"Marked as {label}")


@admin_router.callback_query(F.data.startswith("reply_"))
async def admin_reply_start(callback: CallbackQuery, state: FSMContext) -> None:
    ticket_id = int(callback.data.split("_")[1])
    await state.update_data(reply_ticket_id=ticket_id)
    await state.set_state("admin_reply")
    await callback.message.answer(
        f"💬 Send the reply for ticket #{ticket_id} (it will be forwarded to the customer):"
    )
    await callback.answer()


@admin_router.message(StateFilter("admin_reply"), F.text)
async def admin_reply_send(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    ticket_id = data["reply_ticket_id"]
    ticket = await get_ticket(ticket_id)
    await state.clear()
    if not ticket:
        await message.answer("Ticket not found.")
        return
    await message.bot.send_message(
        ticket["user_id"],
        f"💬 <b>Support reply for ticket #{ticket_id}:</b>\n\n{message.text}",
        parse_mode="HTML",
    )
    await message.answer(f"✅ Reply sent to the customer of ticket #{ticket_id}.")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
async def main() -> None:
    await init_db()
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    dp.include_router(customer_router)
    dp.include_router(admin_router)

    logging.info("Bot started")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
