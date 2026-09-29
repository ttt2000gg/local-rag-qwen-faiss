import asyncio
import httpx
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
import json
import random
from pathlib import Path
import os
import re
import shlex
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

# Папка с LoRA
LORA_DIR = BASE_DIR / "ComfyUI" / "models" / "loras"


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

    "lora": (
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

    "lora": (
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
    "lora": "sdxl_lora.json",
}


# ============================================================
# LORA
# ============================================================

def get_lora_files():
    """
    Возвращает все .safetensors из папки LoRA.
    """

    if not LORA_DIR.exists():
        return []

    return sorted(
        [
            file
            for file in LORA_DIR.iterdir()
            if file.is_file()
            and file.suffix.lower() == ".safetensors"
        ],
        key=lambda x: x.name.lower()
    )


def find_lora(name: str):
    """
    Ищет LoRA по имени.

    Можно писать:

        /lora my_style prompt

    если файл:

        my_style.safetensors

    Также можно указывать полное имя:

        /lora my_style.safetensors prompt

    Поиск регистронезависимый.
    """

    name = name.strip()

    if not name:
        return None

    # Если пользователь написал расширение
    if name.lower().endswith(".safetensors"):
        target = name[:-12]
    else:
        target = name

    target = target.lower()

    for file in get_lora_files():

        # Имя без .safetensors
        stem = file.stem.lower()

        if stem == target:
            return file

        # На случай, если сравнивается полное имя
        if file.name.lower() == name.lower():
            return file

    return None


def get_lora_list_text():
    """
    Формирует список доступных LoRA для Telegram.
    """

    files = get_lora_files()

    if not files:
        return (
            "В папке LoRA пока нет .safetensors файлов.\n\n"
            f"Папка:\n{LORA_DIR}"
        )

    lines = [
        "Доступные Illustrious XL LoRA:\n"
    ]

    for i, file in enumerate(files, start=1):
        lines.append(
            f"{i}. `{file.stem}`"
        )

    lines.append(
        "\nИспользование:\n"
        "/lora название prompt"
    )

    return "\n".join(lines)


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
    error=None,
    lora_name=None
):

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

    if lora_name is not None:
        entry["lora"] = lora_name

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
    preset: str = "fast",
    seed: int | None = None,
    lora_file: Path | None = None
):

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
    # LoRA
    # ---------------------------------------------------------

    if preset == "lora":

        if lora_file is None:
            raise ValueError(
                "LoRA не указана."
            )

        if not lora_file.exists():
            raise FileNotFoundError(
                f"LoRA не найдена: {lora_file}"
            )

        # Node 84 = Load LoRA
        workflow["84"]["inputs"]["lora_name"] = (
            lora_file.name
        )

        print(
            f"Используется LoRA: {lora_file.name}"
        )

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
    # SEED
    # ---------------------------------------------------------

    if seed is None:

        seed = random.randint(
            0,
            2**63 - 1
        )

        print(
            f"Seed не указан, случайный seed: {seed}"
        )

    else:

        print(
            f"Используется ручной seed: {seed}"
        )

    workflow["76"]["inputs"]["seed"] = seed

    # ---------------------------------------------------------
    # PRO может иметь дополнительный KSampler
    # ---------------------------------------------------------

    if preset == "pro":

        workflow["84"]["inputs"]["seed"] = seed

    # ---------------------------------------------------------
    # Отправляем workflow
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
                    error=error_text,
                    lora_name=(
                        lora_file.name
                        if lora_file
                        else None
                    )
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

                    log_generation(
                        preset=preset,
                        seed=seed,
                        prompt=prompt,
                        translated_prompt=translated_prompt,
                        final_prompt=final_prompt,
                        status="success",
                        prompt_id=prompt_id,
                        lora_name=(
                            lora_file.name
                            if lora_file
                            else None
                        )
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

    # ========================================================
    # /lora
    # ========================================================

    if text == "/lora":

        await message.answer(
            get_lora_list_text(),
            parse_mode="Markdown"
        )

        return

    if text.startswith("/lora "):

        raw_args = text[
            len("/lora "):
        ].strip()

        # -----------------------------------------------------
        # Разбираем аргументы через shlex
        #
        # /lora my_style девушка
        #
        # или:
        #
        # /lora "my style" девушка
        # -----------------------------------------------------

        try:

            args = shlex.split(
                raw_args
            )

        except ValueError as e:

            await message.answer(
                f"❌ Ошибка разбора команды: {e}\n\n"
                "Пример:\n"
                "/lora my_style девушка с белыми волосами"
            )

            return

        if len(args) < 2:

            await message.answer(
                "❌ Нужно указать LoRA и prompt.\n\n"
                "Пример:\n"
                "/lora my_style девушка с белыми волосами"
            )

            return

        lora_name = args[0]

        # Остальные аргументы = prompt
        prompt = " ".join(
            args[1:]
        )

        # -----------------------------------------------------
        # Ищем LoRA
        # -----------------------------------------------------

        lora_file = find_lora(
            lora_name
        )

        if lora_file is None:

            available = get_lora_files()

            if available:

                names = "\n".join(
                    f"• `{file.stem}`"
                    for file in available
                )

                await message.answer(
                    "❌ LoRA не найдена.\n\n"
                    f"Ты указал:\n`{lora_name}`\n\n"
                    "Доступные LoRA:\n"
                    f"{names}",
                    parse_mode="Markdown"
                )

            else:

                await message.answer(
                    "❌ В папке LoRA нет файлов `.safetensors`.\n\n"
                    f"Папка:\n{LORA_DIR}"
                )

            return

        preset = "lora"

    # ========================================================
    # Остальные команды
    # ========================================================

    elif text.startswith("/genil "):

        preset = "il"

        prompt = text[
            len("/genil "):
        ].strip()

        lora_file = None

    elif text.startswith("/genpro "):

        preset = "pro"

        prompt = text[
            len("/genpro "):
        ].strip()

        lora_file = None

    elif text.startswith("/genhd "):

        preset = "photorealistic"

        prompt = text[
            len("/genhd "):
        ].strip()

        lora_file = None

    elif text.startswith("/genart "):

        preset = "artistic"

        prompt = text[
            len("/genart "):
        ].strip()

        lora_file = None

    elif text.startswith("/genanime "):

        preset = "anime"

        prompt = text[
            len("/genanime "):
        ].strip()

        lora_file = None

    elif text.startswith("/gen "):

        preset = "fast"

        prompt = text[
            len("/gen "):
        ].strip()

        lora_file = None

    else:

        ai_response = await ask_ollama(
            message.text
        )

        await message.answer(
            ai_response
        )

        return

    # ========================================================
    # SEED
    # ========================================================

    seed = None

    seed_match = re.search(
        r"\s+--seed\s+(\d+)\s*$",
        prompt,
        re.IGNORECASE
    )

    if seed_match:

        seed = int(
            seed_match.group(1)
        )

        prompt = prompt[
            :seed_match.start()
        ].strip()

        print(
            f"Найден ручной seed: {seed}"
        )

    # ========================================================
    # Проверяем seed
    # ========================================================

    if seed is not None:

        if seed < 0 or seed > 2**63 - 1:

            await message.answer(
                "❌ Seed должен быть числом "
                "от 0 до 9223372036854775807."
            )

            return

    # ========================================================
    # Проверяем prompt
    # ========================================================

    if not prompt:

        await message.answer(
            "Напиши prompt после команды.\n\n"
            "Например:\n"
            "/genil красивая девушка\n\n"
            "С LoRA:\n"
            "/lora my_style красивая девушка\n\n"
            "С seed:\n"
            "/lora my_style красивая девушка "
            "--seed 416407258944610701"
        )

        return

    # ========================================================
    # НАЗВАНИЕ PRESET
    # ========================================================

    if preset == "lora":

        preset_name = (
            f"Illustrious XL + {lora_file.stem}"
        )

    else:

        preset_names = {
            "fast": "Fast",
            "photorealistic": "Photorealistic",
            "pro": "PRO",
            "artistic": "Artistic",
            "anime": "Anime",
            "il": "Illustrious XL",
        }

        preset_name = preset_names.get(
            preset,
            preset
        )

    # ========================================================
    # STATUS
    # ========================================================

    if seed is not None:

        status_text = (
            "🎨 Генерирую изображение...\n\n"
            f"Preset: {preset_name}\n"
            f"LoRA: `{lora_file.stem}`\n"
            f"Seed: `{seed}`"
            if preset == "lora"
            else
            "🎨 Генерирую изображение...\n\n"
            f"Preset: {preset_name}\n"
            f"Seed: `{seed}`"
        )

    else:

        status_text = (
            "🎨 Генерирую изображение...\n\n"
            f"Preset: {preset_name}\n"
            f"LoRA: `{lora_file.stem}`\n"
            "Seed: случайный"
            if preset == "lora"
            else
            "🎨 Генерирую изображение...\n\n"
            f"Preset: {preset_name}\n"
            "Seed: случайный"
        )

    status_message = await message.answer(
        status_text,
        parse_mode="Markdown"
    )

    # ========================================================
    # GENERATION
    # ========================================================

    try:

        (
            image_bytes,
            seed,
            translated_prompt,
            final_prompt,
            prompt_id
        ) = await generate_image(
            prompt=prompt,
            preset=preset,
            seed=seed,
            lora_file=lora_file
        )

        await status_message.edit_text(
            (
                "✅ Изображение готово!\n\n"
                f"Preset: {preset_name}\n"
                f"LoRA: `{lora_file.stem}`\n"
                f"Seed: `{seed}`"
                if preset == "lora"
                else
                "✅ Изображение готово!\n\n"
                f"Preset: {preset_name}\n"
                f"Seed: `{seed}`"
            ),
            parse_mode="Markdown"
        )

        await message.answer_photo(
            types.BufferedInputFile(
                image_bytes,
                filename="generated.png"
            )
        )

    except Exception as e:

        print(
            f"Ошибка генерации: {e}"
        )

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
            description="Быстрая генерация"
        ),

        BotCommand(
            command="genhd",
            description="Фотореалистичная генерация"
        ),

        BotCommand(
            command="genil",
            description="Illustrious XL"
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
            description="Anime генерация"
        ),

        BotCommand(
            command="lora",
            description="Illustrious XL + выбранная LoRA"
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
