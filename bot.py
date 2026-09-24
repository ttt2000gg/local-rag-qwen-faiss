import asyncio
import httpx
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
import json
import random
from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
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


async def generate_image(prompt: str) -> bytes:
    comfy_url = "http://127.0.0.1:8188"
    workflow_path = Path(__file__).parent / "sdxl_api.json"

    # Загружаем наш workflow
    with open(workflow_path, "r", encoding="utf-8") as f:
        workflow = json.load(f)

    # Positive prompt
    workflow["73"]["inputs"]["text_g"] = prompt
    workflow["73"]["inputs"]["text_l"] = prompt

    # Negative prompt
    negative_prompt = (
        "low quality, blurry, distorted, deformed, bad anatomy, "
        "extra wheels, extra limbs, text, watermark"
    )

    workflow["74"]["inputs"]["text_g"] = negative_prompt
    workflow["74"]["inputs"]["text_l"] = negative_prompt

    # Случайный seed, чтобы каждый раз получать другой результат
    workflow["76"]["inputs"]["seed"] = random.randint(0, 2**63 - 1)

    # На всякий случай сохраняем 1024x1024
    workflow["75"]["inputs"]["width"] = 1024
    workflow["75"]["inputs"]["height"] = 1024

    async with httpx.AsyncClient(timeout=None) as client:

        # Отправляем workflow в ComfyUI
        response = await client.post(
            f"{comfy_url}/prompt",
            json={"prompt": workflow}
        )
        response.raise_for_status()

        data = response.json()
        prompt_id = data["prompt_id"]

        print(f"ComfyUI: задача запущена: {prompt_id}")

        # Ждём окончания генерации
        while True:
            await asyncio.sleep(1)

            response = await client.get(
                f"{comfy_url}/history/{prompt_id}"
            )
            response.raise_for_status()

            history = response.json()

            if prompt_id not in history:
                continue

            result = history[prompt_id]

            # Проверяем ошибку выполнения
            if result.get("status", {}).get("status_str") == "error":
                raise RuntimeError(
                    f"ComfyUI вернул ошибку: {result}"
                )

            # Ищем сохранённое изображение
            outputs = result.get("outputs", {})

            for node_output in outputs.values():
                images = node_output.get("images", [])

                for image_info in images:
                    filename = image_info["filename"]
                    subfolder = image_info.get("subfolder", "")
                    folder_type = image_info.get("type", "output")

                    # Получаем PNG через API ComfyUI
                    image_response = await client.get(
                        f"{comfy_url}/view",
                        params={
                            "filename": filename,
                            "subfolder": subfolder,
                            "type": folder_type
                        }
                    )

                    image_response.raise_for_status()

                    print(f"ComfyUI: изображение готово: {filename}")

                    return image_response.content

# Обработчик команды /start
@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.answer("Дарова епта, я нейронка легенды доты и всего мира Артемия, напиши что я умею и ты охуеешь :0")


# Обработчик любых текстовых сообщений
@dp.message()
async def handle_message(message: types.Message):
    text = message.text or ""

    # Генерация изображения через ComfyUI
    if text.startswith("/gen"):
        prompt = text[4:].strip()

        if not prompt:
            await message.answer(
                "Напиши промпт после /gen\n\n"
                "Например:\n"
                "/gen чёрный Nissan Laurel C35 на японской заправке ночью"
            )
            return

        await bot.send_chat_action(
            chat_id=message.chat.id,
            action="upload_photo"
        )

        try:
            await message.answer("Генерирую изображение...")

            image_bytes = await generate_image(prompt)

            await message.answer_photo(
                types.BufferedInputFile(
                    image_bytes,
                    filename="generated.png"
                )
            )

        except Exception as e:
            print(f"Ошибка ComfyUI: {e}")

            await message.answer(
                f"Ошибка при генерации изображения:\n{e}"
            )

        return

    # Обычный текст → Qwen
    await bot.send_chat_action(
        chat_id=message.chat.id,
        action="typing"
    )

    ai_response = await ask_ollama(text)

    await message.answer(ai_response)

async def main():
    print("Бот запущен и готов к работе с Ollama!")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
