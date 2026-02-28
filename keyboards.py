"""Клавиатуры для бота"""
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton


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


def get_model_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру выбора модели"""
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
        [InlineKeyboardButton(text="🌟 Stable Diffusion 3", callback_data="model_sd3", style="success")],
        [InlineKeyboardButton(text="🖼️ Редактирование фото ❌", callback_data="model_kontext", style="success")],
    ])
    return keyboard


def get_image_model_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру выбора модели для изображений"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚡ Быстрая (4 шага)", callback_data="model_schnell", style="success")],
        [InlineKeyboardButton(text="🎨 Качественная (50 шагов)", callback_data="model_dev", style="success")],
        [InlineKeyboardButton(text="🌟 Stable Diffusion 3", callback_data="model_sd3", style="success")],
        [InlineKeyboardButton(text="🖼️ Редактирование фото ❌", callback_data="model_kontext", style="success")],
    ])
    return keyboard


def get_premium_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру премиум пакетов"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🟦 Basic - 199 руб", callback_data="premium_basic", style="primary")],
        [InlineKeyboardButton(text="🟩 Pro - 499 руб", callback_data="premium_pro", style="success")],
        [InlineKeyboardButton(text="🟥 Ultra - 999 руб", callback_data="premium_ultra", style="danger")],
        [InlineKeyboardButton(text="💬 Связаться с админом", url="https://t.me/korzina_dar")],
    ])
    return keyboard
