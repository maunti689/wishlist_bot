from aiogram import Bot
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
import asyncio
import logging

logger = logging.getLogger(__name__)

async def clear_chat(message: Message, bot: Bot, delay: int = 2):
    """Delete the last bot/user messages after a short delay."""
    await asyncio.sleep(delay)
    try:
        await bot.delete_message(message.chat.id, message.message_id)
        if message.reply_to_message:
            await bot.delete_message(message.chat.id, message.reply_to_message.message_id)
    except:
        pass

async def delete_previous_message(state: FSMContext, message: Message):
    try:
        data = await state.get_data()
        last_message_id = data.get('last_bot_message')
        
        if last_message_id:
            try:
                await message.bot.delete_message(message.chat.id, last_message_id)
            except:
                pass
    except Exception as e:
        logger.error(f"Error while deleting a message: {e}")

async def replace_message(message: Message, new_text: str, reply_markup=None, state: FSMContext=None):
    try:
        if state:
            await delete_previous_message(state, message)
        
        new_msg = await message.answer(
            new_text,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        
        if state:
            await state.update_data(last_bot_message=new_msg.message_id)
        
        return new_msg
    except Exception as e:
        logger.error(f"Error while replacing a message: {e}")
        return None
