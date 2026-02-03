import asyncio
from typing import List
from aiogram import Bot
from aiogram.fsm.context import FSMContext

EPHEMERAL_KEY = "ephemeral_messages"

async def add_ephemeral_message(state: FSMContext, message_id: int) -> None:
    data = await state.get_data()
    ids: List[int] = data.get(EPHEMERAL_KEY, []) or []
    if message_id not in ids:
        ids.append(message_id)
        await state.update_data(**{EPHEMERAL_KEY: ids})

async def cleanup_ephemeral_messages(bot: Bot, state: FSMContext, chat_id: int) -> None:
    data = await state.get_data()
    ids: List[int] = data.get(EPHEMERAL_KEY, []) or []
    if not ids:
        return
    for mid in ids:
        try:
            await bot.delete_message(chat_id, mid)
        except Exception:
            pass
    await state.update_data(**{EPHEMERAL_KEY: []})

def schedule_delete_message(bot: Bot, chat_id: int, message_id: int, delay: int = 8) -> None:
    async def _delayed():
        try:
            await asyncio.sleep(delay)
            await bot.delete_message(chat_id, message_id)
        except Exception:
            pass
    try:
        asyncio.create_task(_delayed())
    except Exception:
        pass

