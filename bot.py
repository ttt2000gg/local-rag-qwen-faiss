import asyncio
import httpx
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
import json
import random
from pathlib import Path
import os
from dotenv import load_dotenv
from aiogram.types import BotCommand

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "artemiy-ai:latest"

bot = Bot(token=TOKEN)
dp = Dispatcher()

STYLE_PROMPTS = {
    "fast": "",

    "photorealistic": (
        "photorealistic photography, realistic materials, realistic lighting, "
        "realistic textures, natural proportions, highly detailed"
    ),

    "pro": (
        "photorealistic photography, realistic materials, realistic lighting, "
        "realistic textures, natural proportions, highly detailed"
    ),

    "artistic": (
        "highly detailed digital artwork, dramatic composition, expressive colors, "
        "beautiful lighting, detailed environment, polished illustration"
    ),

    "anime": (
        "anime illustration, Japanese anime style, detailed anime artwork, "
        "expressive character design, clean lineart, detailed background, "
        "cinematic composition"
    ),
}

NEGATIVE_PROMPTS = {
    "fast": (
        "low quality, blurry, distorted, deformed, bad anatomy, "
        "extra limbs, duplicate objects, text, watermark"
    ),

    "photorealistic": (
        "cartoon, anime, illustration, drawing, painting, sketch, "
        "3d render, CGI, unrealistic, low quality, blurry, distorted, "
        "deformed, bad anatomy, extra limbs, duplicate objects, "
        "text, watermark"
    ),

    "pro": (
        "cartoon, anime, illustration, drawing, painting, sketch, "
        "3d render, CGI, unrealistic, low quality, blurry, distorted, "
        "deformed, bad anatomy, extra limbs, duplicate objects, "
        "text, watermark"
    ),

    "artistic": (
        "low quality, blurry, distorted, deformed, bad anatomy, "
        "extra limbs, duplicate objects, text, watermark"
    ),

    "anime": (
        "photorealistic, realistic photography, 3d render, CGI, "
        "low quality, blurry, distorted, deformed, bad anatomy, "
        "extra limbs, duplicate objects, text, watermark"
    ),
}

PRESETS = {
    "fast": "sdxl_fast.json",
    "photorealistic": "sdxl_photorealistic.json",
    "pro": "sdxl_pro.json",
    "artistic": "sdxl_artistic.json",
    "anime": "sdxl_anime.json",
}

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


async def generate_image(prompt: str, preset: str = "fast") -> bytes:
    if preset not in PRESETS:
        raise ValueError(f"Неизвестный preset: {preset}")

    comfy_url = "http://127.0.0.1:8188"

    workflow_path = Path(__file__).parent / PRESETS[preset]

    # Загружаем нужный JSON workflow
    with open(workflow_path, "r", encoding="utf-8") as f:
        workflow = json.load(f)

    # Добавляем специальный стиль
    style_prompt = STYLE_PROMPTS[preset]

    if style_prompt:
        final_prompt = f"{prompt}, {style_prompt}"
    else:
        final_prompt = prompt

    # -------------------------------------------------
    # ВАЖНО:
    # 73 = Positive CLIP
    # 74 = Negative CLIP
    # 76 = первый KSampler
    # -------------------------------------------------

    workflow["73"]["inputs"]["text_g"] = final_prompt
    workflow["73"]["inputs"]["text_l"] = final_prompt

    negative_prompt = NEGATIVE_PROMPTS[preset]

    workflow["74"]["inputs"]["text_g"] = negative_prompt
    workflow["74"]["inputs"]["text_l"] = negative_prompt

    # Случайный seed
    seed = random.randint(0, 2**63 - 1)

    workflow["76"]["inputs"]["seed"] = seed

    if preset == "pro":
        workflow["84"]["inputs"]["seed"] = seed

    async with httpx.AsyncClient(timeout=None) as client:

        # Отправляем workflow в ComfyUI
        response = await client.post(
            f"{comfy_url}/prompt",
            json={"prompt": workflow}
        )

        response.raise_for_status()

        data = response.json()
        prompt_id = data["prompt_id"]

        print(
            f"ComfyUI: запущена генерация "
            f"preset={preset}, id={prompt_id}"
        )

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

            status = result.get("status", {})

            if status.get("status_str") == "error":
                raise RuntimeError(
                    f"ComfyUI вернул ошибку: {result}"
                )

            outputs = result.get("outputs", {})

            for node_output in outputs.values():

                images = node_output.get("images", [])

                for image_info in images:

                    filename = image_info["filename"]
                    subfolder = image_info.get("subfolder", "")
                    folder_type = image_info.get("type", "output")

                    image_response = await client.get(
                        f"{comfy_url}/view",
                        params={
                            "filename": filename,
                            "subfolder": subfolder,
                            "type": folder_type,
                        },
                    )

                    image_response.raise_for_status()

                    print(
                        f"ComfyUI: изображение готово: {filename}"
                    )

                    return image_response.content

# Обработчик команды /start
@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.answer("Дарова епта, я нейронка легенды доты и всего мира Артемия, напиши что я умею и ты охуеешь :0")

@dp.message()
async def handle_message(message: types.Message):
    await bot.send_chat_action(
        chat_id=message.chat.id,
        action="typing"
    )

    text = message.text.strip()

    if text.startswith("/genpro "):
        preset = "pro"
        prompt = text[len("/genpro "):].strip()

    elif text.startswith("/genhd "):
        preset = "photorealistic"
        prompt = text[len("/genhd "):].strip()

    elif text.startswith("/genart "):
        preset = "artistic"
        prompt = text[len("/genart "):].strip()

    elif text.startswith("/genanime "):
        preset = "anime"
        prompt = text[len("/genanime "):].strip()

    elif text.startswith("/gen "):
        preset = "fast"
        prompt = text[len("/gen "):].strip()

    else:
        ai_response = await ask_ollama(message.text)
        await message.answer(ai_response)
        return

    if not prompt:
        await message.answer(
            "Напиши prompt после команды.\n"
            "Например: /gen черный Nissan Laurel C35 ночью"
        )
        return

    try:
        image_bytes = await generate_image(
            prompt=prompt,
            preset=preset
        )

        await message.answer_photo(
            types.BufferedInputFile(
                image_bytes,
                filename="generated.png"
            )
        )

    except Exception as e:
        print(f"Ошибка генерации: {e}")

        await message.answer(
            f"Ошибка при генерации изображения:\n{e}"
        )

async def set_commands():
    commands = [
        BotCommand(command="start", description="Запустить бота"),
        BotCommand(command="gen", description="Быстрая генерация изображения"),
        BotCommand(command="genhd", description="Фотореалистичное изображение"),
        BotCommand(command="genpro", description="PRO генерация 1536×1536"),
        BotCommand(command="genart", description="Художественная генерация"),
        BotCommand(command="genanime", description="Генерация в стиле аниме"),
    ]

    await bot.set_my_commands(commands)

# Обработчик любых текстовых сообщений
async def main():
    print("Бот запущен и готов к работе с Ollama!")
    await bot.delete_webhook(drop_pending_updates=True)
    await set_commands()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
