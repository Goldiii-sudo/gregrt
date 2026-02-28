import asyncio
import base64
import json
import logging
import uuid
import zipfile
from io import BytesIO
from os import getenv
from pathlib import Path

import aiohttp
import httpx
import requests
from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, BufferedInputFile, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton, BotCommand
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types.menu_button_commands import MenuButtonCommands
from dotenv import load_dotenv
from googletrans import Translator
from openai import OpenAI

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Константы
BOT_TOKEN = getenv("BOT_TOKEN")
NVIDIA_API_KEY = getenv("NVIDIA_API_KEY")

# NVIDIA Whisper API
PARAKEET_API_URL = "https://ai.api.nvidia.com/v1/audio/transcription"

# OpenAI клиент для NVIDIA LLM
try:
    llm_client = OpenAI(
        base_url="https://integrate.api.nvidia.com/v1",
        api_key=NVIDIA_API_KEY,
        http_client=None
    )
except TypeError:
    # Для Python 3.14+ используем другой способ
    import httpx
    llm_client = OpenAI(
        base_url="https://integrate.api.nvidia.com/v1",
        api_key=NVIDIA_API_KEY,
        http_client=httpx.Client()
    )

# Инициализация бота и роутера
bot = Bot(token=BOT_TOKEN)
router = Router()
translator = Translator()

# Хранилище текущей модели для каждого пользователя
user_models = {}

# Файл для хранения данных пользователей
USER_DATA_FILE = Path("user_data.json")

# Пакеты премиума
PREMIUM_TIERS = {
    "basic": {
        "name": "🟦 Basic",
        "price": "199 руб",
        "limits": {
            "text": 30,
            "gemini": 25,
            "deepseek": 20,
            "claude": 15,
            "claude_sonnet": 18,
            "claude_haiku": 25,
            "claude_opus": 10,
            "qwen": 22,
            "llama": 28,
            "schnell": 5,
            "dev": 2,
            "kontext": 1
        }
    },
    "pro": {
        "name": "🟩 Pro",
        "price": "499 руб",
        "limits": {
            "text": 100,
            "gemini": 80,
            "deepseek": 60,
            "claude": 50,
            "claude_sonnet": 60,
            "claude_haiku": 80,
            "claude_opus": 40,
            "qwen": 70,
            "llama": 90,
            "schnell": 15,
            "dev": 8,
            "kontext": 5
        }
    },
    "ultra": {
        "name": "🟥 Ultra",
        "price": "999 руб",
        "limits": {
            "text": 250,
            "gemini": 200,
            "deepseek": 150,
            "claude": 120,
            "claude_sonnet": 150,
            "claude_haiku": 200,
            "claude_opus": 100,
            "qwen": 180,
            "llama": 220,
            "schnell": 40,
            "dev": 20,
            "kontext": 15
        }
    }
}


def load_user_data():
    """Загружает данные пользователей из файла"""
    if USER_DATA_FILE.exists():
        with open(USER_DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"users": {}, "promocodes": {}}


def save_user_data(data):
    """Сохраняет данные пользователей в файл"""
    with open(USER_DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_user_limits(user_id: int):
    """Получает лимиты пользователя"""
    data = load_user_data()
    user_id_str = str(user_id)
    
    if user_id_str not in data["users"]:
        # Новый пользователь - бесплатный доступ
        data["users"][user_id_str] = {
            "tier": "free",
            "limits": {
                "text": 5,
                "gemini": 3,
                "deepseek": 2,
                "claude": 2,
                "claude_sonnet": 2,
                "claude_haiku": 3,
                "claude_opus": 1,
                "qwen": 3,
                "llama": 4,
                "schnell": 2,
                "dev": 0,
                "kontext": 0
            }
        }
        save_user_data(data)
    
    return data["users"][user_id_str]


def decrease_limit(user_id: int, model_key: str):
    """Уменьшает лимит пользователя"""
    data = load_user_data()
    user_id_str = str(user_id)
    
    if user_id_str in data["users"]:
        if model_key in data["users"][user_id_str]["limits"]:
            data["users"][user_id_str]["limits"][model_key] -= 1
            save_user_data(data)
            return True
    return False


def check_limit(user_id: int, model_key: str) -> bool:
    """Проверяет, есть ли у пользователя лимит"""
    user_data = get_user_limits(user_id)
    return user_data["limits"].get(model_key, 0) > 0


def get_user_history(user_id: int, model_key: str) -> list:
    """Получает историю сообщений пользователя для конкретной модели"""
    data = load_user_data()
    user_id_str = str(user_id)
    
    if user_id_str in data["users"]:
        if "history" not in data["users"][user_id_str]:
            data["users"][user_id_str]["history"] = {}
            save_user_data(data)
        
        return data["users"][user_id_str]["history"].get(model_key, [])
    
    return []


def add_to_history(user_id: int, model_key: str, user_message: str, assistant_message: str):
    """Добавляет сообщение в историю пользователя (максимум 20 сообщений)"""
    data = load_user_data()
    user_id_str = str(user_id)
    
    if user_id_str in data["users"]:
        if "history" not in data["users"][user_id_str]:
            data["users"][user_id_str]["history"] = {}
        
        if model_key not in data["users"][user_id_str]["history"]:
            data["users"][user_id_str]["history"][model_key] = []
        
        # Добавляем новые сообщения
        data["users"][user_id_str]["history"][model_key].append({
            "role": "user",
            "content": user_message
        })
        data["users"][user_id_str]["history"][model_key].append({
            "role": "assistant",
            "content": assistant_message
        })
        
        # Ограничиваем историю последними 20 сообщениями (10 пар вопрос-ответ)
        if len(data["users"][user_id_str]["history"][model_key]) > 20:
            data["users"][user_id_str]["history"][model_key] = data["users"][user_id_str]["history"][model_key][-20:]
        
        save_user_data(data)


def clear_user_history(user_id: int, model_key: str = None):
    """Очищает историю пользователя для конкретной модели или всех моделей"""
    data = load_user_data()
    user_id_str = str(user_id)
    
    if user_id_str in data["users"]:
        if model_key:
            # Очищаем историю конкретной модели
            if "history" in data["users"][user_id_str] and model_key in data["users"][user_id_str]["history"]:
                data["users"][user_id_str]["history"][model_key] = []
        else:
            # Очищаем всю историю
            data["users"][user_id_str]["history"] = {}
        
        save_user_data(data)


# Модели NVIDIA
MODELS = {
    "text": {
        "provider": "OpenAI",
        "name": "Chat GPT 5",
        "description": "Генерация текста",
        "system_prompt": "You are ChatGPT-5, an advanced AI assistant created by OpenAI. You are a highly intelligent, helpful, and harmless AI that provides accurate, thoughtful, and comprehensive responses to user queries. You have extensive knowledge across all domains and can engage in complex reasoning, creative tasks, and problem-solving. Always respond in the language the user uses."
    },
    "gemini": {
        "provider": "Google",
        "name": "Gemini 2.0",
        "description": "Генерация текста",
        "system_prompt": "You are Gemini 2.0, an advanced AI assistant created by Google. You are known for your multimodal capabilities, reasoning skills, and ability to understand complex contexts. You provide thoughtful, accurate, and comprehensive responses. Always respond in the language the user uses."
    },
    "deepseek": {
        "provider": "DeepSeek",
        "name": "DeepSeek R1",
        "description": "Генерация текста",
        "system_prompt": "You are DeepSeek R1, an advanced reasoning AI assistant created by DeepSeek. You excel at logical reasoning, problem-solving, and providing detailed explanations. You think step-by-step and provide thorough analysis. Always respond in the language the user uses."
    },
    "claude": {
        "provider": "Anthropic",
        "name": "Claude 3.5",
        "description": "Генерация текста",
        "system_prompt": "You are Claude 3.5, an advanced AI assistant created by Anthropic. You are known for your thoughtful analysis, nuanced understanding, and ethical reasoning. You provide balanced, insightful responses while being honest about limitations. Always respond in the language the user uses."
    },
    "claude_sonnet": {
        "provider": "Anthropic",
        "name": "Claude Sonnet 4.5",
        "description": "Генерация текста",
        "system_prompt": "You are Claude Sonnet 4.5, an advanced AI assistant created by Anthropic. You are optimized for speed and efficiency while maintaining high quality reasoning. You excel at creative tasks and provide nuanced, thoughtful responses. Always respond in the language the user uses."
    },
    "claude_haiku": {
        "provider": "Anthropic",
        "name": "Claude Haiku 4.5",
        "description": "Генерация текста",
        "system_prompt": "You are Claude Haiku 4.5, a lightweight yet capable AI assistant created by Anthropic. You are designed for quick, efficient responses while maintaining quality. You are helpful, harmless, and honest. Always respond in the language the user uses."
    },
    "claude_opus": {
        "provider": "Anthropic",
        "name": "Claude Opus 4.6",
        "description": "Генерация текста",
        "system_prompt": "You are Claude Opus 4.6, the most advanced AI assistant created by Anthropic. You excel at complex reasoning, deep analysis, and nuanced understanding. You provide comprehensive, thoughtful responses to even the most challenging questions. Always respond in the language the user uses."
    },
    "qwen": {
        "provider": "Alibaba",
        "name": "Qwen 2.5",
        "description": "Генерация текста",
        "system_prompt": "You are Qwen 2.5, an advanced AI assistant created by Alibaba. You are multilingual and excel at understanding diverse contexts and providing practical solutions. You are helpful, harmless, and honest. Always respond in the language the user uses."
    },
    "llama": {
        "provider": "Meta",
        "name": "Llama 3.1",
        "description": "Генерация текста",
        "system_prompt": "You are Llama 3.1, an advanced AI assistant created by Meta. You are open-source and designed to be helpful, harmless, and honest. You provide clear, direct responses and excel at following instructions. Always respond in the language the user uses."
    },
    "schnell": {
        "provider": "Gemini",
        "url": "https://ai.api.nvidia.com/v1/genai/black-forest-labs/flux.1-schnell",
        "name": "NanoBanana 1",
        "description": "Быстрая генерация (4 шага)",
        "params": {
            "width": 1024,
            "height": 1024,
            "seed": 0,
            "steps": 4
        }
    },
    "dev": {
        "provider": "Gemini",
        "url": "https://ai.api.nvidia.com/v1/genai/black-forest-labs/flux.1-dev",
        "name": "NanoBanana 2",
        "description": "Качественная генерация (50 шагов)",
        "params": {
            "width": 1024,
            "height": 1024,
            "seed": 0,
            "steps": 50,
            "cfg_scale": 3.5,
            "mode": "base"
        }
    },
    "kontext": {
        "provider": "Gemini",
        "url": "https://ai.api.nvidia.com/v1/genai/black-forest-labs/flux.1-kontext-dev",
        "name": "NanoBanana Edit",
        "description": "Контекстная генерация (требует фото)",
        "params": {
            "aspect_ratio": "match_input_image",
            "steps": 30,
            "cfg_scale": 3.5,
            "seed": 0
        }
    }
}

# Состояния FSM
class GenerationStates(StatesGroup):
    waiting_for_prompt = State()
    waiting_for_image = State()
    waiting_for_context_prompt = State()
    waiting_for_search_query = State()


def enhance_prompt(prompt: str) -> str:
    """Улучшает промпт, добавляя детали качества"""
    enhanced = f"{prompt}, high quality, detailed, professional, sharp focus, 8k resolution"
    return enhanced


def get_main_menu() -> ReplyKeyboardMarkup:
    """Создает главное меню с цветными кнопками"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🤖 Что умеет бот", style="primary")],
            [KeyboardButton(text="📝 Выбрать модель", style="success"), KeyboardButton(text="🎨 Создать картинку", style="primary")],
            [KeyboardButton(text="🔍 Интернет-поиск", style="danger"), KeyboardButton(text="🚀 Премиум", style="danger")],
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    return keyboard



async def generate_text(prompt: str, model_key: str = "text", user_id: int = None) -> str:
    """Генерирует текст через NVIDIA LLM с учетом истории сообщений"""
    try:
        logger.info(f"Генерирую текст для промпта: {prompt[:100]}")

        model = MODELS.get(model_key, MODELS["text"])
        system_prompt = model.get("system_prompt", "You are a helpful AI assistant.")

        # Формируем список сообщений с историей
        messages = [{"role": "system", "content": system_prompt}]

        # Добавляем историю если есть user_id
        if user_id:
            history = get_user_history(user_id, model_key)
            messages.extend(history)

        # Добавляем текущий запрос пользователя
        messages.append({"role": "user", "content": prompt})

        completion = llm_client.chat.completions.create(
            model="minimaxai/minimax-m2.5",
            messages=messages,
            temperature=1,
            top_p=0.95,
            max_tokens=8192,
            stream=False
        )

        generated_text = completion.choices[0].message.content

        # Удаляем теги <think>...</think>
        import re
        generated_text = re.sub(r'<think>.*?</think>', '', generated_text, flags=re.DOTALL).strip()

        # Удаляем markdown форматирование (**, ##, ||, и т.д.)
        generated_text = re.sub(r'\*\*', '', generated_text)  # Удаляем **
        generated_text = re.sub(r'##+ ', '', generated_text)  # Удаляем заголовки
        generated_text = re.sub(r'\|\s*-+\s*\|', '', generated_text)  # Удаляем разделители таблиц
        generated_text = re.sub(r'^\s*\|\s*$', '', generated_text, flags=re.MULTILINE)  # Удаляем пустые строки с |

        # Сохраняем в историю если есть user_id
        if user_id:
            add_to_history(user_id, model_key, prompt, generated_text)

        logger.info(f"Текст сгенерирован: {generated_text[:100]}")
        return generated_text

    except Exception as e:
        logger.error(f"Ошибка при генерации текста: {e}")
        raise Exception(f"Ошибка LLM: {str(e)}")




async def translate_to_english(text: str) -> str:
    """Переводит текст на английский язык"""
    try:
        result = await translator.translate(text, src_lang='auto', dest_lang='en')
        translated = result['text']
        logger.info(f"Перевод: '{text}' -> '{translated}'")
        return translated
    except Exception as e:
        logger.warning(f"Ошибка при переводе: {e}. Используем исходный текст.")
        return text


async def web_search(query: str) -> str:
    """Поиск в интернете без API ключей через DuckDuckGo"""
    try:
        logger.info(f"Ищу: {query}")
        
        # Используем DuckDuckGo через httpx
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://html.duckduckgo.com/html",
                params={"q": query},
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                },
                timeout=10
            )
            
            if response.status_code != 200:
                raise Exception(f"DuckDuckGo вернул статус {response.status_code}")
            
            # Простой парсинг результатов
            import re
            results = []
            
            # Ищем результаты поиска
            pattern = r'<a rel="nofollow" class="result__a" href="([^"]+)">([^<]+)</a>'
            matches = re.findall(pattern, response.text)
            
            for url, title in matches[:5]:  # Берем первые 5 результатов
                results.append(f"🔗 {title}\n{url}")
            
            if results:
                return "\n\n".join(results)
            else:
                return "❌ Результаты не найдены"
                
    except Exception as e:
        logger.error(f"Ошибка при поиске: {e}")
        return f"❌ Ошибка поиска: {str(e)}"


def _upload_asset(input_data: bytes, description: str) -> str:
    """Загружает изображение в NVCF API и возвращает asset ID"""
    try:
        header_auth = f"Bearer {NVIDIA_API_KEY}"
        
        authorize = requests.post(
            "https://api.nvcf.nvidia.com/v2/nvcf/assets",
            headers={
                "Authorization": header_auth,
                "Content-Type": "application/json",
                "accept": "application/json",
            },
            json={"contentType": "image/jpeg", "description": description},
            timeout=30,
        )
        authorize.raise_for_status()
        
        upload_url = authorize.json()["uploadUrl"]
        asset_id = authorize.json()["assetId"]
        
        response = requests.put(
            upload_url,
            data=input_data,
            headers={
                "x-amz-meta-nvcf-asset-description": description,
                "content-type": "image/jpeg",
            },
            timeout=300,
        )
        response.raise_for_status()
        
        logger.info(f"Изображение загружено с ID: {asset_id}")
        return asset_id
    except Exception as e:
        logger.error(f"Ошибка при загрузке изображения: {e}")
        raise Exception(f"Ошибка загрузки: {str(e)}")


async def compare_images_changenet(reference_image: bytes, test_image: bytes) -> bytes:
    """Сравнивает два изображения с помощью Visual ChangeNet"""
    try:
        logger.info("Загружаю изображения для сравнения...")
        
        # Загружаем оба изображения
        asset_id1 = _upload_asset(reference_image, "Reference Image")
        asset_id2 = _upload_asset(test_image, "Test Image")
        
        logger.info(f"Asset IDs: {asset_id1}, {asset_id2}")
        
        # Подготавливаем запрос
        nvai_url = "https://ai.api.nvidia.com/v1/cv/nvidia/visual-changenet"
        header_auth = f"Bearer {NVIDIA_API_KEY}"
        
        inputs = {
            "reference_image": str(asset_id1),
            "test_image": str(asset_id2)
        }
        
        asset_list = f"{asset_id1},{asset_id2}"
        
        headers = {
            "Content-Type": "application/json",
            "NVCF-INPUT-ASSET-REFERENCES": asset_list,
            "NVCF-FUNCTION-ASSET-IDS": asset_list,
            "Authorization": header_auth,
        }
        
        logger.info("Отправляю запрос к Visual ChangeNet...")
        
        response = requests.post(nvai_url, headers=headers, json=inputs, timeout=300)
        response.raise_for_status()
        
        logger.info("Ответ получен, распаковываю результаты...")
        
        # Сохраняем zip в памяти
        zip_buffer = BytesIO(response.content)
        
        # Распаковываем и ищем результат
        with zipfile.ZipFile(zip_buffer, 'r') as z:
            files = z.namelist()
            logger.info(f"Файлы в архиве: {files}")
            
            # Ищем файл результата (обычно это PNG или JPG)
            result_file = None
            for f in files:
                if f.endswith(('.png', '.jpg', '.jpeg')):
                    result_file = f
                    break
            
            if result_file:
                result_bytes = z.read(result_file)
                logger.info(f"Результат получен: {result_file}")
                return result_bytes
            else:
                raise Exception("Не найден файл результата в архиве")
        
    except Exception as e:
        logger.error(f"Ошибка при сравнении изображений: {e}")
        raise Exception(f"Ошибка сравнения: {str(e)}")


async def generate_image(prompt: str, model_key: str, image_data: str = None) -> tuple[bytes, dict]:
    """Генерирует изображение через NVIDIA API"""
    model = MODELS.get(model_key, MODELS["schnell"])
    
    enhanced_prompt = enhance_prompt(prompt)
    
    logger.info(f"Модель: {model['name']}")
    logger.info(f"Исходный промпт: {prompt}")
    logger.info(f"Улучшенный промпт: {enhanced_prompt}")
    
    headers = {
        "Authorization": f"Bearer {NVIDIA_API_KEY}",
        "Accept": "application/json",
    }
    
    payload = {
        "prompt": enhanced_prompt,
        **model["params"]
    }
    
    if model_key == "kontext" and image_data:
        payload["image"] = image_data
    
    logger.info(f"Отправляю запрос к {model['url']}")
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                model["url"],
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=180)
            ) as response:
                response_text = await response.text()
                logger.info(f"Статус ответа: {response.status}")
                logger.info(f"Ответ API: {response_text[:500]}")
                
                request_info = {
                    "request_id": response.headers.get("Nvcf-Reqid", "N/A"),
                    "status": response.headers.get("Nvcf-Status", "N/A"),
                    "model": model["name"],
                }
                
                logger.info(f"Request ID: {request_info['request_id']}, Status: {request_info['status']}")
                
                if response.status != 200:
                    raise Exception(f"API вернул ошибку: {response.status}\n{response_text[:200]}")
                
                result = await response.json()
                
                if "artifacts" in result and len(result["artifacts"]) > 0:
                    image_b64 = result["artifacts"][0].get("base64", "")
                elif "image" in result:
                    image_b64 = result["image"]
                elif "data" in result and len(result["data"]) > 0:
                    image_b64 = result["data"][0].get("b64_json", "")
                else:
                    raise Exception("Не удалось найти изображение в ответе API")
                
                image_bytes = base64.b64decode(image_b64)
                return image_bytes, request_info
                
        except asyncio.TimeoutError:
            logger.error("Timeout при запросе к NVIDIA API")
            raise Exception("Превышено время ожидания ответа от API")
        except aiohttp.ClientError as e:
            logger.error(f"Ошибка соединения: {e}")
            raise Exception("Ошибка соединения с API")


@router.message(CommandStart())
async def cmd_start(message: Message):
    """Обработчик команды /start"""
    await message.answer(
        "👋 Привет! Я бот для генерации текста и изображений с помощью NVIDIA.\n\n"
        "Выбери, что тебе нужно:",
        reply_markup=get_main_menu()
    )


@router.message(Command("ask"))
async def cmd_ask(message: Message):
    """Обработчик команды /ask - генерация текста"""
    if not message.text or message.text == "/ask":
        await message.answer("Используй: /ask <твой вопрос>\n\nНапример: /ask Что такое искусственный интеллект?")
        return
    
    prompt = message.text.replace("/ask ", "", 1)
    user_id = message.from_user.id
    model_key = user_models.get(user_id, "text")
    status_msg = await message.answer("🤖 Генерирую ответ...")
    
    try:
        response_text = await generate_text(prompt, model_key, user_id)
        
        if len(response_text) > 4096:
            for i in range(0, len(response_text), 4096):
                await message.answer(response_text[i:i+4096])
        else:
            await message.answer(response_text)
        
        await status_msg.delete()
        
    except Exception as e:
        logger.error(f"Ошибка при генерации текста: {e}")
        await status_msg.edit_text(
            f"❌ Произошла ошибка при генерации текста:\n{str(e)}\n\n"
            "Попробуйте ещё раз."
        )


@router.message(F.text == "🤖 Что умеет бот")
async def btn_about_bot(message: Message):
    """Обработчик кнопки 'Что умеет бот'"""
    await message.answer(
        "🤖 Я умею:\n\n"
        "📝 Генерировать текст - отвечу на любой вопрос\n"
        "🎨 Создавать картинки - по твоему описанию\n"
        "🔍 Искать в интернете - найду нужную информацию\n\n"
        "Выбери, что тебе нужно!",
        reply_markup=get_main_menu()
    )


@router.message(F.text == "📝 Выбрать модель")
async def btn_select_model(message: Message, state: FSMContext):
    """Обработчик кнопки 'Выбрать модель'"""
    await cmd_model(message, state)


@router.message(F.text == "🎨 Создать картинку")
async def btn_create_image(message: Message, state: FSMContext):
    """Обработчик кнопки 'Создать картинку'"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚡ Быстрая (4 шага)", callback_data="model_schnell", style="success")],
        [InlineKeyboardButton(text="🎨 Качественная (50 шагов)", callback_data="model_dev", style="success")],
        [InlineKeyboardButton(text="🖼️ Редактирование фото", callback_data="model_kontext", style="success")],
    ])
    await message.answer("🎨 Выбери модель для генерации картинки:", reply_markup=keyboard)


@router.message(F.text == "🔍 Интернет-поиск")
async def btn_web_search(message: Message, state: FSMContext):
    """Обработчик кнопки 'Интернет-поиск'"""
    await message.answer("🔍 Введи, что ты хочешь найти:")
    await state.set_state(GenerationStates.waiting_for_search_query)


@router.message(F.text == "🚀 Премиум")
async def btn_premium(message: Message):
    """Обработчик кнопки 'Премиум'"""
    user_id = message.from_user.id
    user_data = get_user_limits(user_id)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🟦 Basic - 199 руб", callback_data="premium_basic", style="primary")],
        [InlineKeyboardButton(text="🟩 Pro - 499 руб", callback_data="premium_pro", style="success")],
        [InlineKeyboardButton(text="🟥 Ultra - 999 руб", callback_data="premium_ultra", style="danger")],
        [InlineKeyboardButton(text="💬 Связаться с админом", url="https://t.me/korzina_dar")],
    ])

    current_tier = user_data.get("tier", "free")
    tier_name = PREMIUM_TIERS.get(current_tier, {}).get("name", "Бесплатный")

    await message.answer(
        f"🚀 Премиум подписка\n\n"
        f"Текущий пакет: {tier_name}\n\n"
        f"Выбери пакет для просмотра деталей:",
        reply_markup=keyboard
    )


@router.callback_query(F.data.startswith("premium_"))
async def show_premium_tier(query: CallbackQuery):
    """Показывает детали премиум пакета"""
    tier = query.data.split("_")[1]
    tier_data = PREMIUM_TIERS[tier]
    
    limits_text = "\n".join([
        f"• Chat GPT 5: {tier_data['limits']['text']} запросов",
        f"• Gemini 2.0: {tier_data['limits']['gemini']} запросов",
        f"• DeepSeek R1: {tier_data['limits']['deepseek']} запросов",
        f"• Claude 3.5: {tier_data['limits']['claude']} запросов",
        f"• Qwen 2.5: {tier_data['limits']['qwen']} запросов",
        f"• Llama 3.1: {tier_data['limits']['llama']} запросов",
        f"• Быстрая генерация: {tier_data['limits']['schnell']} изображений",
        f"• Качественная генерация: {tier_data['limits']['dev']} изображений",
        f"• Редактирование фото: {tier_data['limits']['kontext']} изображений"
    ])
    
    await query.message.edit_text(
        f"{tier_data['name']}\n"
        f"Стоимость: {tier_data['price']}\n\n"
        f"Лимиты:\n{limits_text}\n\n"
        f"Для покупки промокода свяжитесь с админом: @korzina_dar\n"
        f"После получения промокода используйте: /promo КОД",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💬 Связаться с админом", url="https://t.me/korzina_dar")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="premium_back")]
        ])
    )
    await query.answer()


@router.callback_query(F.data == "premium_back")
async def premium_back(query: CallbackQuery):
    """Возврат к выбору пакетов"""
    user_id = query.from_user.id
    user_data = get_user_limits(user_id)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🟦 Basic - 199 руб", callback_data="premium_basic", style="primary")],
        [InlineKeyboardButton(text="🟩 Pro - 499 руб", callback_data="premium_pro", style="success")],
        [InlineKeyboardButton(text="🟥 Ultra - 999 руб", callback_data="premium_ultra", style="danger")],
        [InlineKeyboardButton(text="💬 Связаться с админом", url="https://t.me/korzina_dar")],
    ])
    
    current_tier = user_data.get("tier", "free")
    tier_name = PREMIUM_TIERS.get(current_tier, {}).get("name", "Бесплатный")
    
    await query.message.edit_text(
        f"🚀 Премиум подписка\n\n"
        f"Текущий пакет: {tier_name}\n\n"
        f"Выбери пакет для просмотра деталей:",
        reply_markup=keyboard
    )
    await query.answer()


@router.message(Command("promo"))
async def cmd_promo(message: Message):
    """Обработчик команды /promo - активация промокода"""
    if not message.text or len(message.text.split()) < 2:
        await message.answer(
            "❌ Используй: /promo КОД\n\n"
            "Например: /promo BASIC10A\n\n"
            "Промокоды можно купить у админа: @korzina_dar"
        )
        return
    
    promo_code = message.text.split()[1].upper()
    user_id = message.from_user.id
    
    data = load_user_data()
    
    # Проверяем существование промокода
    if promo_code not in data["promocodes"]:
        await message.answer("❌ Промокод не найден!")
        return
    
    # Проверяем, использован ли промокод
    if data["promocodes"][promo_code]["used"]:
        await message.answer("❌ Этот промокод уже использован!")
        return
    
    # Активируем промокод
    tier = data["promocodes"][promo_code]["tier"]
    tier_data = PREMIUM_TIERS[tier]
    
    user_id_str = str(user_id)
    data["users"][user_id_str] = {
        "tier": tier,
        "limits": tier_data["limits"].copy()
    }
    data["promocodes"][promo_code]["used"] = True
    data["promocodes"][promo_code]["used_by"] = user_id
    
    save_user_data(data)
    
    await message.answer(
        f"✅ Промокод активирован!\n\n"
        f"Пакет: {tier_data['name']}\n\n"
        f"Твои лимиты обновлены. Используй /limits чтобы посмотреть остатки."
    )


@router.message(Command("limits"))
async def cmd_limits(message: Message):
    """Показывает оставшиеся лимиты пользователя"""
    user_id = message.from_user.id
    user_data = get_user_limits(user_id)
    
    tier_name = PREMIUM_TIERS.get(user_data["tier"], {}).get("name", "Бесплатный")
    limits = user_data["limits"]
    
    limits_text = "\n".join([
        f"• Chat GPT 5: {limits.get('text', 0)} запросов",
        f"• Gemini 2.0: {limits.get('gemini', 0)} запросов",
        f"• DeepSeek R1: {limits.get('deepseek', 0)} запросов",
        f"• Claude 3.5: {limits.get('claude', 0)} запросов",
        f"• Qwen 2.5: {limits.get('qwen', 0)} запросов",
        f"• Llama 3.1: {limits.get('llama', 0)} запросов",
        f"• Быстрая генерация: {limits.get('schnell', 0)} изображений",
        f"• Качественная генерация: {limits.get('dev', 0)} изображений",
        f"• Редактирование фото: {limits.get('kontext', 0)} изображений"
    ])
    
    await message.answer(
        f"📊 Твои лимиты\n\n"
        f"Пакет: {tier_name}\n\n"
        f"{limits_text}\n\n"
        f"Для пополнения используй /promo или купи новый пакет через 🚀 Премиум"
    )


@router.message(Command("model"))
async def cmd_model(message: Message, state: FSMContext):
    """Обработчик команды /model - выбор модели"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Chat GPT 5", callback_data="model_text", style="primary")],
        [InlineKeyboardButton(text="🔵 Gemini 2.0", callback_data="model_gemini", style="primary")],
        [InlineKeyboardButton(text="🟣 DeepSeek R1", callback_data="model_deepseek", style="primary")],
        [InlineKeyboardButton(text="🟠 Claude 3.5", callback_data="model_claude", style="primary")],
        [InlineKeyboardButton(text="🟠 Claude Sonnet 4.5", callback_data="model_claude_sonnet", style="primary")],
        [InlineKeyboardButton(text="🟠 Claude Haiku 4.5", callback_data="model_claude_haiku", style="primary")],
        [InlineKeyboardButton(text="🟠 Claude Opus 4.6", callback_data="model_claude_opus", style="primary")],
        [InlineKeyboardButton(text="🟡 Qwen 2.5", callback_data="model_qwen", style="primary")],
        [InlineKeyboardButton(text="🔴 Llama 3.1", callback_data="model_llama", style="primary")],
        [InlineKeyboardButton(text="⚡ Быстрая генерация", callback_data="model_schnell", style="success")],
        [InlineKeyboardButton(text="🎨 Качественная генерация", callback_data="model_dev", style="success")],
        [InlineKeyboardButton(text="🖼️ Редактирование фото", callback_data="model_kontext", style="success")],
    ])
    
    await message.answer("🎯 Выбери модель:", reply_markup=keyboard)


@router.callback_query(F.data.startswith("model_"))
async def select_model(query: CallbackQuery, state: FSMContext):
    """Обработчик выбора модели"""
    model_key = query.data.split("_", 1)[1]
    user_models[query.from_user.id] = model_key
    model = MODELS[model_key]
    
    await query.answer()
    
    # Текстовые модели
    if model_key in ["text", "gemini", "deepseek", "claude", "claude_sonnet", "claude_haiku", "claude_opus", "qwen", "llama"]:
        await query.message.edit_text(
            f"✅ Выбрана модель: {model['name']}\n\n"
            f"Теперь отправь вопрос или текст для генерации."
        )
        await state.set_state(GenerationStates.waiting_for_prompt)
    elif model_key == "kontext":
        await query.message.edit_text(
            f"✅ Выбрана модель: {model['name']}\n\n"
            f"Отправь фото, которое нужно изменить, и описание изменений."
        )
        await state.set_state(GenerationStates.waiting_for_image)
    else:
        # Модели изображений
        await query.message.edit_text(
            f"✅ Выбрана модель: {model['name']}\n\n"
            f"Теперь отправь текстовое описание для генерации изображения."
        )
        await state.set_state(GenerationStates.waiting_for_prompt)


@router.message(F.photo)
async def handle_photo(message: Message, state: FSMContext):
    """Обработчик загрузки фото для контекстной генерации"""
    user_id = message.from_user.id
    
    if user_models.get(user_id) != "kontext":
        await message.answer("Сначала выбери модель /model (FLUX.1-kontext-dev для работы с фото)")
        return
    
    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    file_bytes = await bot.download_file(file.file_path)
    
    image_b64 = base64.b64encode(file_bytes.getvalue()).decode()
    image_data = f"data:image/jpeg;base64,{image_b64}"
    
    await state.update_data(image_data=image_data)
    
    await message.answer("📸 Фото получено! Теперь отправь описание, что нужно изменить.")
    await state.set_state(GenerationStates.waiting_for_context_prompt)


@router.message(GenerationStates.waiting_for_context_prompt)
async def handle_context_prompt(message: Message, state: FSMContext):
    """Обработчик промпта для контекстной генерации"""
    prompt = message.text
    user_id = message.from_user.id
    model_key = user_models.get(user_id, "schnell")
    
    status_msg = await message.answer("🎨 Генерирую изображение, подождите...")
    
    try:
        data = await state.get_data()
        image_data = data.get("image_data")
        
        image_bytes, request_info = await generate_image(prompt, model_key, image_data)
        
        image_file = BufferedInputFile(file=image_bytes, filename="generated_image.png")
        
        caption = f"✨ Готово!\n\nМодель: {request_info['model']}\nПромпт: {prompt}"
        if request_info["request_id"] != "N/A":
            caption += f"\n\n🔑 ID запроса: {request_info['request_id']}"
        
        await message.answer_photo(photo=image_file, caption=caption)
        await status_msg.delete()
        await state.clear()
        
    except Exception as e:
        logger.error(f"Ошибка при генерации изображения: {e}")
        await status_msg.edit_text(
            f"❌ Произошла ошибка при генерации изображения:\n{str(e)}\n\n"
            "Попробуйте ещё раз или измените описание."
        )
        await state.clear()


@router.message(GenerationStates.waiting_for_search_query)
async def handle_search_query(message: Message, state: FSMContext):
    """Обработчик поискового запроса"""
    query = message.text
    status_msg = await message.answer("🔍 Ищу результаты...")
    
    try:
        results = await web_search(query)
        
        if len(results) > 4096:
            for i in range(0, len(results), 4096):
                await message.answer(results[i:i+4096])
        else:
            await message.answer(results)
        
        await status_msg.delete()
        await state.clear()
        
    except Exception as e:
        logger.error(f"Ошибка при поиске: {e}")
        await status_msg.edit_text(
            f"❌ Произошла ошибка при поиске:\n{str(e)}\n\n"
            "Попробуйте ещё раз."
        )
        await state.clear()


@router.message(GenerationStates.waiting_for_prompt)
async def handle_prompt(message: Message, state: FSMContext):
    """Обработчик промпта"""
    prompt = message.text
    user_id = message.from_user.id
    model_key = user_models.get(user_id, "text")
    
    # Проверяем лимит
    if not check_limit(user_id, model_key):
        await message.answer(
            f"❌ У тебя закончились запросы для этой модели!\n\n"
            f"Используй /limits чтобы посмотреть остатки или купи новый пакет через 🚀 Премиум"
        )
        await state.clear()
        return
    
    model = MODELS.get(model_key, MODELS["text"])
    
    # Если выбрана текстовая модель
    if model_key in ["text", "gemini", "deepseek", "claude", "claude_sonnet", "claude_haiku", "claude_opus", "qwen", "llama"]:
        status_msg = await message.answer("🤖 Генерирую ответ...")
        try:
            response_text = await generate_text(prompt, model_key, user_id)
            
            # Уменьшаем лимит после успешной генерации
            decrease_limit(user_id, model_key)
            
            if len(response_text) > 4096:
                for i in range(0, len(response_text), 4096):
                    await message.answer(response_text[i:i+4096])
            else:
                await message.answer(response_text)
            
            await status_msg.delete()
            
            # Показываем остаток
            user_data = get_user_limits(user_id)
            remaining = user_data["limits"].get(model_key, 0)
            await message.answer(f"📊 Осталось запросов: {remaining}")
            
        except Exception as e:
            logger.error(f"Ошибка при генерации текста: {e}")
            await status_msg.edit_text(
                f"❌ Произошла ошибка при генерации текста:\n{str(e)}\n\n"
                "Попробуйте ещё раз."
            )
    else:
        # Генерация изображения
        status_msg = await message.answer("🎨 Генерирую изображение, подождите...")
        
        try:
            image_bytes, request_info = await generate_image(prompt, model_key)
            
            # Уменьшаем лимит после успешной генерации
            decrease_limit(user_id, model_key)
            
            image_file = BufferedInputFile(file=image_bytes, filename="generated_image.png")
            
            user_data = get_user_limits(user_id)
            remaining = user_data["limits"].get(model_key, 0)
            
            caption = f"✨ Готово!\n\nМодель: {request_info['model']}\nПромпт: {prompt}\n\n📊 Осталось: {remaining}"
            if request_info["request_id"] != "N/A":
                caption += f"\n🔑 ID: {request_info['request_id']}"
            
            await message.answer_photo(photo=image_file, caption=caption)
            await status_msg.delete()
            
        except Exception as e:
            logger.error(f"Ошибка при генерации изображения: {e}")
            await status_msg.edit_text(
                f"❌ Произошла ошибка при генерации изображения:\n{str(e)}\n\n"
                "Попробуйте ещё раз или измените описание."
            )
    
    await state.clear()


@router.message(F.text.startswith("/"))
async def handle_unknown_command(message: Message):
    """Обработчик неизвестных команд"""
    command = message.text.split()[0]
    
    commands_list = """❌ Неизвестная команда: {}\n\n📋 Доступные команды:\n\n/start - Главное меню\n/ask - Задать вопрос\n/model - Выбрать модель\n/help - Справка""".format(command)
    
    await message.answer(commands_list, reply_markup=get_main_menu())


@router.message(F.text)
async def handle_text(message: Message, state: FSMContext):
    """Обработчик текстовых сообщений"""
    prompt = message.text
    
    # Проверяем, не находимся ли мы в каком-то состоянии
    current_state = await state.get_state()
    if current_state is not None:
        # Если в состоянии, пропускаем - обработает специфичный обработчик
        return
    
    # Игнорируем тексты кнопок меню
    menu_buttons = [
        "🤖 Что умеет бот",
        "📝 Выбрать модель",
        "🎨 Создать картинку",
        "🔍 Интернет-поиск",
        "🚀 Премиум"
    ]
    
    if prompt in menu_buttons:
        return
    
    user_id = message.from_user.id
    model_key = user_models.get(user_id, "text")
    
    # Проверяем лимит
    if not check_limit(user_id, model_key):
        await message.answer(
            f"❌ У тебя закончились запросы для этой модели!\n\n"
            f"Используй /limits чтобы посмотреть остатки или купи новый пакет через 🚀 Премиум"
        )
        return
    
    model = MODELS.get(model_key, MODELS["text"])
    
    # Если выбрана текстовая модель
    if model_key in ["text", "gemini", "deepseek", "claude", "claude_sonnet", "claude_haiku", "claude_opus", "qwen", "llama"]:
        status_msg = await message.answer("🤖 Генерирую ответ...")
        try:
            response_text = await generate_text(prompt, model_key, user_id)
            
            # Уменьшаем лимит после успешной генерации
            decrease_limit(user_id, model_key)
            
            if len(response_text) > 4096:
                for i in range(0, len(response_text), 4096):
                    await message.answer(response_text[i:i+4096])
            else:
                await message.answer(response_text)
            
            await status_msg.delete()
            
            # Показываем остаток
            user_data = get_user_limits(user_id)
            remaining = user_data["limits"].get(model_key, 0)
            await message.answer(f"📊 Осталось запросов: {remaining}")
            
        except Exception as e:
            logger.error(f"Ошибка при генерации текста: {e}")
            await status_msg.edit_text(
                f"❌ Произошла ошибка при генерации текста:\n{str(e)}\n\n"
                "Попробуйте ещё раз."
            )
    else:
        # Генерация изображения
        status_msg = await message.answer("🎨 Генерирую изображение, подождите...")
        
        try:
            image_bytes, request_info = await generate_image(prompt, model_key)
            
            # Уменьшаем лимит после успешной генерации
            decrease_limit(user_id, model_key)
            
            image_file = BufferedInputFile(file=image_bytes, filename="generated_image.png")
            
            user_data = get_user_limits(user_id)
            remaining = user_data["limits"].get(model_key, 0)
            
            caption = f"✨ Готово!\n\nМодель: {request_info['model']}\nПромпт: {prompt}\n\n📊 Осталось: {remaining}"
            if request_info["request_id"] != "N/A":
                caption += f"\n🔑 ID: {request_info['request_id']}"
            
            await message.answer_photo(photo=image_file, caption=caption)
            await status_msg.delete()
            
        except Exception as e:
            logger.error(f"Ошибка при генерации изображения: {e}")
            await status_msg.edit_text(
                f"❌ Произошла ошибка при генерации изображения:\n{str(e)}\n\n"
                "Попробуйте ещё раз или измените описание."
            )


async def setup_bot_commands(bot: Bot):
    """Устанавливает список команд для бота"""
    commands = [
        BotCommand(command="start", description="🤖 Главное меню"),
        BotCommand(command="ask", description="📝 Задать вопрос"),
        BotCommand(command="model", description="🎨 Выбрать модель"),
        BotCommand(command="promo", description="🎁 Активировать промокод"),
        BotCommand(command="limits", description="📊 Мои лимиты"),
        BotCommand(command="help", description="❓ Справка"),
    ]
    
    await bot.set_my_commands(commands)
    
    # Устанавливаем кнопку меню
    menu_button = MenuButtonCommands()
    await bot.set_chat_menu_button(menu_button=menu_button)
    
    logger.info("Команды бота установлены")


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Обработчик команды /help"""
    await message.answer(
        "❓ Справка\n\n"
        "Доступные команды:\n\n"
        "/start - Открыть главное меню\n"
        "/ask <вопрос> - Задать вопрос боту\n"
        "/model - Выбрать модель для генерации\n"
        "/help - Показать эту справку\n\n"
        "Или используй кнопки меню ниже!",
        reply_markup=get_main_menu()
    )


async def main():
    """Главная функция запуска бота"""
    dp = Dispatcher()
    dp.include_router(router)
    
    # Устанавливаем команды при запуске
    await setup_bot_commands(bot)
    
    logger.info("Бот запущен!")
    
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())


