import asyncio
import httpx
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart

TOKEN = "8816362123:AAG9IVp091g23SdaiO_sQl9LrOIZzdz9jH8"  # Токен от @BotFather
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "artemiy-ai:latest"

bot = Bot(token=TOKEN)
dp = Dispatcher()


# Функция для запроса к Ollama
async def ask_ollama(prompt: str) -> str:
    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False  # Отключаем потоковый ответ, чтобы получить сразу весь текст
    }
    
    # Таймаут увеличен, так как генерация текста локальной нейросетью занимает время
    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            response = await client.post(OLLAMA_URL, json=payload)
            response.raise_for_status()
            data = response.json()
            return data.get("response", "Не удалось получить ответ от нейросети.")
        except Exception as e:
            return f"Ошибка при обращении к Ollama: {e}"


# Обработчик команды /start
@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.answer("Привет! Напиши мне что-нибудь, и я передам это нейросети Qwen.")


# Обработчик любых текстовых сообщений
@dp.message()
async def handle_message(message: types.Message):
    # Уведомляем пользователя, что бот думает (показывает статус "печатает...")
    await bot.send_chat_action(chat_id=message.chat.id, action="typing")
    
    # Запрашиваем ответ у нейросети
    ai_response = await ask_ollama(message.text)
    
    # Отправляем ответ пользователю
    await message.answer(ai_response)


async def main():
    print("Бот запущен и готов к работе с Ollama!")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
