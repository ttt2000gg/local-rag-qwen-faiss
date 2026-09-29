import asyncio
import httpx
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
import json
import random
from pathlib import Path
import os
from datetime import datetime
from dotenv import load_dotenv
from aiogram.types import BotCommand
import argostranslate.translate


load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "artemiy-ai:latest"

bot = Bot(token=TOKEN)
dp = Dispatcher()


# ============================================================
# PATHS / LOGS
# ============================================================

BASE_DIR = Path(__file__).parent

LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

GENERATION_LOG = LOG_DIR / "generations.jsonl"


# ============================================================
# STYLE PROMPTS
# ============================================================

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

    "il": (
        "masterpiece, best quality, highly detailed, detailed eyes, "
        "beautiful face, detailed background"
    ),
    
    "lora1": (
        "masterpiece, best quality, highly detailed, detailed eyes, "
        "beautiful face, detailed background"
    ),
}


# ============================================================
# NEGATIVE PROMPTS
# ============================================================

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

    "il": (
        "worst quality, low quality, lowres, blurry, "
        "bad anatomy, bad hands, extra fingers, extra limbs, "
        "duplicate, text, watermark, signature"
    ),

    "lora1": (
    "worst quality, low quality, lowres, blurry, "
    "bad anatomy, bad hands, extra fingers, extra limbs, "
    "duplicate, text, watermark, signature"
    ),
}


# ============================================================
# PRESETS
# ============================================================

PRESETS = {
    "fast": "sdxl_fast.json",
    "photorealistic": "sdxl_photorealistic.json",
    "pro": "sdxl_pro.json",
    "artistic": "sdxl_artistic.json",
    "anime": "sdxl_anime.json",
    "il": "sdxl_il.json",
    "lora1": "sdxl_lora1.json",
    }


# ============================================================
# GENERATION LOG
# ============================================================

def log_generation(
    preset,
    seed,
    prompt,
    translated_prompt,
    final_prompt,
    status,
    prompt_id=None,
    error=None
):
    """
    Записывает информацию о генерации
    в logs/generations.jsonl
    """

    entry = {
        "time": datetime.now().isoformat(
            timespec="seconds"
        ),
        "preset": preset,
        "seed": seed,
        "prompt": prompt,
        "translated_prompt": translated_prompt,
        "final_prompt": final_prompt,
        "status": status,
    }

    if prompt_id is not None:
        entry["prompt_id"] = prompt_id

    if error is not None:
        entry["error"] = str(error)

    with open(
        GENERATION_LOG,
        "a",
        encoding="utf-8"
    ) as f:

        f.write(
            json.dumps(
                entry,
                ensure_ascii=False
            ) + "\n"
        )


# ============================================================
# OLLAMA
# ============================================================

async def ask_ollama(prompt: str) -> str:

    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False
    }

    async with httpx.AsyncClient(
        timeout=120.0
    ) as client:

        try:

            response = await client.post(
                OLLAMA_URL,
                json=payload
            )

            response.raise_for_status()

            data = response.json()

            return data.get(
                "response",
                "Не удалось получить ответ от нейросети."
            )

        except Exception as e:

            return (
                f"Ошибка при обращении к Ollama: {e}"
            )


# ============================================================
# ARGOS TRANSLATE
# ============================================================

def translate_prompt(prompt: str) -> str:

    try:

        translated = (
            argostranslate.translate.translate(
                prompt,
                "ru",
                "en"
            )
        )

        return translated.strip()

    except Exception as e:

        print(
            f"Ошибка перевода Argos: {e}"
        )

        return prompt


# ============================================================
# COMFYUI IMAGE GENERATION
# ============================================================

async def generate_image(
    prompt: str,
    preset: str = "fast"
):
    """
    Генерирует изображение через ComfyUI.

    Возвращает:

        image_bytes
        seed
        translated_prompt
        final_prompt
        prompt_id
    """

    if preset not in PRESETS:

        raise ValueError(
            f"Неизвестный preset: {preset}"
        )

    comfy_url = "http://127.0.0.1:8188"

    workflow_path = (
        BASE_DIR /
        PRESETS[preset]
    )

    # ---------------------------------------------------------
    # Загружаем workflow
    # ---------------------------------------------------------

    with open(
        workflow_path,
        "r",
        encoding="utf-8"
    ) as f:

        workflow = json.load(f)

    # ---------------------------------------------------------
    # Перевод prompt
    # ---------------------------------------------------------

    translated_prompt = translate_prompt(
        prompt
    )

    print(
        f"Оригинальный prompt: {prompt}"
    )

    print(
        f"Переведённый prompt: "
        f"{translated_prompt}"
    )

    # ---------------------------------------------------------
    # Добавляем стиль
    # ---------------------------------------------------------

    style_prompt = STYLE_PROMPTS[preset]

    if style_prompt:

        final_prompt = (
            f"{translated_prompt}, "
            f"{style_prompt}"
        )

    else:

        final_prompt = translated_prompt

    print(
        f"Итоговый prompt: {final_prompt}"
    )

    # ---------------------------------------------------------
    # CLIP
    #
    # 73 = Positive CLIP
    # 74 = Negative CLIP
    # 76 = KSampler
    # ---------------------------------------------------------

    workflow["73"]["inputs"]["text_g"] = (
        final_prompt
    )

    workflow["73"]["inputs"]["text_l"] = (
        final_prompt
    )

    negative_prompt = (
        NEGATIVE_PROMPTS[preset]
    )

    workflow["74"]["inputs"]["text_g"] = (
        negative_prompt
    )

    workflow["74"]["inputs"]["text_l"] = (
        negative_prompt
    )

    # ---------------------------------------------------------
    # Random seed
    # ---------------------------------------------------------

    seed = random.randint(
        0,
        2**63 - 1
    )

    workflow["76"]["inputs"]["seed"] = seed

    print(
        f"Seed: {seed}"
    )

    # ---------------------------------------------------------
    # PRO может иметь дополнительный KSampler
    # ---------------------------------------------------------

    if preset == "pro":

        workflow["84"]["inputs"]["seed"] = (
            seed
        )

    # ---------------------------------------------------------
    # Отправляем workflow в ComfyUI
    # ---------------------------------------------------------

    async with httpx.AsyncClient(
        timeout=None
    ) as client:

        response = await client.post(
            f"{comfy_url}/prompt",
            json={
                "prompt": workflow
            }
        )

        response.raise_for_status()

        data = response.json()

        prompt_id = data["prompt_id"]

        print(
            f"ComfyUI: запущена генерация "
            f"preset={preset}, "
            f"seed={seed}, "
            f"id={prompt_id}"
        )

        # -----------------------------------------------------
        # Ждём окончания генерации
        # -----------------------------------------------------

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

            status = result.get(
                "status",
                {}
            )

            if status.get(
                "status_str"
            ) == "error":

                error_text = (
                    f"ComfyUI вернул ошибку: "
                    f"{result}"
                )

                log_generation(
                    preset=preset,
                    seed=seed,
                    prompt=prompt,
                    translated_prompt=translated_prompt,
                    final_prompt=final_prompt,
                    status="error",
                    prompt_id=prompt_id,
                    error=error_text
                )

                raise RuntimeError(
                    error_text
                )

            outputs = result.get(
                "outputs",
                {}
            )

            for node_output in outputs.values():

                images = node_output.get(
                    "images",
                    []
                )

                for image_info in images:

                    filename = image_info[
                        "filename"
                    ]

                    subfolder = image_info.get(
                        "subfolder",
                        ""
                    )

                    folder_type = image_info.get(
                        "type",
                        "output"
                    )

                    image_response = (
                        await client.get(
                            f"{comfy_url}/view",
                            params={
                                "filename": filename,
                                "subfolder": subfolder,
                                "type": folder_type,
                            },
                        )
                    )

                    image_response.raise_for_status()

                    # -------------------------------------------------
                    # Записываем успешную генерацию в лог
                    # -------------------------------------------------

                    log_generation(
                        preset=preset,
                        seed=seed,
                        prompt=prompt,
                        translated_prompt=translated_prompt,
                        final_prompt=final_prompt,
                        status="success",
                        prompt_id=prompt_id
                    )

                    print(
                        f"ComfyUI: изображение готово: "
                        f"{filename}"
                    )

                    return (
                        image_response.content,
                        seed,
                        translated_prompt,
                        final_prompt,
                        prompt_id
                    )


# ============================================================
# /start
# ============================================================

@dp.message(CommandStart())
async def cmd_start(
    message: types.Message
):

    await message.answer(
        "Дарова епта, я нейронка легенды доты и всего мира "
        "Артемия, напиши что я умею и ты охуеешь :0"
    )


# ============================================================
# ОБРАБОТКА СООБЩЕНИЙ
# ============================================================

@dp.message()
async def handle_message(
    message: types.Message
):

    await bot.send_chat_action(
        chat_id=message.chat.id,
        action="typing"
    )

    text = message.text.strip()

    # ---------------------------------------------------------
    # /lora1
    # ---------------------------------------------------------

    if text.startswith("/lora1 "):

        preset = "lora1"

        prompt = text[
            len("/lora1 "):
        ].strip()

    # -----------

    # ---------------------------------------------------------
    # /genil
    # ---------------------------------------------------------

    elif text.startswith("/genil "):

        preset = "il"

        prompt = text[
            len("/genil "):
        ].strip()

    # ---------------------------------------------------------
    # /genpro
    # ---------------------------------------------------------

    elif text.startswith("/genpro "):

        preset = "pro"

        prompt = text[
            len("/genpro "):
        ].strip()

    # ---------------------------------------------------------
    # /genhd
    # ---------------------------------------------------------

    elif text.startswith("/genhd "):

        preset = "photorealistic"

        prompt = text[
            len("/genhd "):
        ].strip()

    # ---------------------------------------------------------
    # /genart
    # ---------------------------------------------------------

    elif text.startswith("/genart "):

        preset = "artistic"

        prompt = text[
            len("/genart "):
        ].strip()

    # ---------------------------------------------------------
    # /genanime
    # ---------------------------------------------------------

    elif text.startswith("/genanime "):

        preset = "anime"

        prompt = text[
            len("/genanime "):
        ].strip()

    # ---------------------------------------------------------
    # /gen
    # ---------------------------------------------------------

    elif text.startswith("/gen "):

        preset = "fast"

        prompt = text[
            len("/gen "):
        ].strip()

    # ---------------------------------------------------------
    # Обычное сообщение
    # ---------------------------------------------------------

    else:

        ai_response = await ask_ollama(
            message.text
        )

        await message.answer(
            ai_response
        )

        return

    # ---------------------------------------------------------
    # Проверяем prompt
    # ---------------------------------------------------------

    if not prompt:

        await message.answer(
            "Напиши prompt после команды.\n"
            "Например: /genil красивая девушка "
            "с длинными белыми волосами"
        )

        return

    # ---------------------------------------------------------
    # Определяем название preset для Telegram
    # ---------------------------------------------------------

    preset_names = {
        "fast": "Fast",
        "photorealistic": "Photorealistic",
        "pro": "PRO",
        "artistic": "Artistic",
        "anime": "Anime",
        "il": "Illustrious XL",
        "lora1": "Illustrious XL + 90s Anime LoRA"
    }

    preset_name = preset_names.get(
        preset,
        preset
    )

    # ---------------------------------------------------------
    # Отправляем сообщение о начале генерации
    # ---------------------------------------------------------

    status_message = await message.answer(
        "🎨 Генерирую изображение...\n\n"
        f"Preset: {preset_name}"
    )

    # ---------------------------------------------------------
    # Генерация
    # ---------------------------------------------------------

    try:

        (
            image_bytes,
            seed,
            translated_prompt,
            final_prompt,
            prompt_id
        ) = await generate_image(
            prompt=prompt,
            preset=preset
        )

        # -----------------------------------------------------
        # Обновляем статус после генерации
        # -----------------------------------------------------

        await status_message.edit_text(
            "✅ Изображение готово!\n\n"
            f"Preset: {preset_name}\n"
            f"Seed: `{seed}`",
            parse_mode="Markdown"
        )

        # -----------------------------------------------------
        # Отправляем изображение
        # -----------------------------------------------------

        await message.answer_photo(
            types.BufferedInputFile(
                image_bytes,
                filename="generated.png"
            ),
            parse_mode="Markdown"
        )

    except Exception as e:

        print(
            f"Ошибка генерации: {e}"
        )

        # -----------------------------------------------------
        # Обновляем сообщение об ошибке
        # -----------------------------------------------------

        try:

            await status_message.edit_text(
                "❌ Ошибка при генерации:\n\n"
                f"{e}"
            )

        except Exception:

            await message.answer(
                "❌ Ошибка при генерации изображения:\n"
                f"{e}"
            )


# ============================================================
# TELEGRAM COMMANDS
# ============================================================

async def set_commands():

    commands = [

        BotCommand(
            command="start",
            description="Запустить бота"
        ),

        BotCommand(
            command="gen",
            description="Быстрая генерация изображения"
        ),

        BotCommand(
            command="genhd",
            description="Фотореалистичное изображение"
        ),

        BotCommand(
            command="genil",
            description="Генерация Illustrious XL"
        ),

        BotCommand(
            command="genpro",
            description="PRO генерация"
        ),

        BotCommand(
            command="genart",
            description="Художественная генерация"
        ),

        BotCommand(
            command="genanime",
            description="Генерация в стиле аниме"
        ),

        BotCommand(
            command="lora1",
            description="Illustrious XL + 90s Anime LoRA"
        ),
    ]

    await bot.set_my_commands(
        commands
    )


# ============================================================
# MAIN
# ============================================================

async def main():

    print(
        "Бот запущен и готов к работе!"
    )

    await bot.delete_webhook(
        drop_pending_updates=True
    )

    await set_commands()

    await dp.start_polling(
        bot
    )


if __name__ == "__main__":

    asyncio.run(main())
