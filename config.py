"""Конфигурация бота"""
from os import getenv
from pathlib import Path
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Константы
BOT_TOKEN = getenv("BOT_TOKEN")
NVIDIA_API_KEY = getenv("NVIDIA_API_KEY")

# NVIDIA Whisper API
PARAKEET_API_URL = "https://ai.api.nvidia.com/v1/audio/transcription"

# Файл для хранения данных пользователей
USER_DATA_FILE = Path("user_data.json")

# Пакеты премиума
PREMIUM_TIERS = {
    "unlimited": {
        "name": "♾️ Безлимит",
        "price": "Бесплатно",
        "limits": {
            "text": 999999,
            "gemini": 999999,
            "deepseek": 999999,
            "claude": 999999,
            "claude_sonnet": 999999,
            "claude_haiku": 999999,
            "claude_opus": 999999,
            "qwen": 999999,
            "llama": 999999,
            "schnell": 999999,
            "dev": 999999,
            "sd3": 999999,
            "kontext": 999999
        }
    },
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
            "sd3": 3,
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
            "sd3": 10,
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
            "sd3": 25,
            "kontext": 15
        }
    }
}

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
    "sd3": {
        "provider": "Stability AI",
        "url": "https://ai.api.nvidia.com/v1/genai/stabilityai/stable-diffusion-3-medium",
        "name": "Stable Diffusion 3",
        "description": "Качественная генерация от Stability AI",
        "params": {
            "cfg_scale": 5,
            "aspect_ratio": "1:1",
            "seed": 0,
            "steps": 50,
            "negative_prompt": ""
        }
    },
    "kontext": {
        "provider": "Gemini",
        "url": "https://ai.api.nvidia.com/v1/genai/black-forest-labs/flux-1-kontext-dev",
        "name": "NanoBanana Edit",
        "description": "Контекстная генерация (требует фото)",
        "params": {
            "steps": 30,
            "guidance_scale": 3.5,
            "seed": 0
        }
    }
}
