from aiogram import Bot
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
import asyncio
import logging

logger = logging.getLogger(__name__)

async def clear_chat(message: Message, bot: Bot, delay: int = 2):
    """
    Удаляет предыдущие сообщения в чате после задержки
    """
    await asyncio.sleep(delay)
    try:
        # Удаляем сообщение пользователя и ответ бота
        await bot.delete_message(message.chat.id, message.message_id)
        if message.reply_to_message:
            await bot.delete_message(message.chat.id, message.reply_to_message.message_id)
    except:
        pass

async def delete_previous_message(state: FSMContext, message: Message):
    """Удаление предыдущего сообщения бота"""
    try:
        data = await state.get_data()
        last_message_id = data.get('last_bot_message')
        
        if last_message_id:
            try:
                await message.bot.delete_message(message.chat.id, last_message_id)
            except:
                pass
    except Exception as e:
        logger.error(f"Ошибка при удалении сообщения: {e}")

async def replace_message(message: Message, new_text: str, reply_markup=None, state: FSMContext=None):
    """Замена старого сообщения новым"""
    try:
        # Удаляем старое сообщение
        if state:
            await delete_previous_message(state, message)
        
        # Отправляем новое
        new_msg = await message.answer(
            new_text,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        
        # Сохраняем ID нового сообщения
        if state:
            await state.update_data(last_bot_message=new_msg.message_id)
        
        return new_msg
    except Exception as e:
        logger.error(f"Ошибка при замене сообщения: {e}")
        return None
