"""Обработчики команд и сообщений"""
import logging
import base64
from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, BufferedInputFile, CallbackQuery, BotCommand
from aiogram.fsm.context import FSMContext
from aiogram.types.menu_button_commands import MenuButtonCommands

from config import MODELS, PREMIUM_TIERS
from states import GenerationStates
from keyboards import get_main_menu, get_model_keyboard, get_image_model_keyboard, get_premium_keyboard
from ai_generator import generate_text, generate_image
from web_search import web_search
from user_manager import (
    get_user_limits, check_limit, decrease_limit,
    load_user_data, save_user_data
)

logger = logging.getLogger(__name__)
router = Router()

# Хранилище текущей модели для каждого пользователя
user_models = {}


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


@router.message(Command("model"))
async def cmd_model(message: Message, state: FSMContext):
    """Обработчик команды /model - выбор модели"""
    await message.answer("🎯 Выбери модель:", reply_markup=get_model_keyboard())


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
        f"• Stable Diffusion 3: {limits.get('sd3', 0)} изображений"
    ])
    
    await message.answer(
        f"📊 Твои лимиты\n\n"
        f"Пакет: {tier_name}\n\n"
        f"{limits_text}\n\n"
        f"Для пополнения используй /promo или купи новый пакет через 🚀 Премиум"
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
    await message.answer(
        "🎨 Выбери модель для генерации картинки:\n\n"
        "⚠️ Примечание: Модель редактирования фото (NanoBanana Edit) требует локального развертывания через Docker и недоступна через облачный API.",
        reply_markup=get_image_model_keyboard()
    )


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

    current_tier = user_data.get("tier", "free")
    tier_name = PREMIUM_TIERS.get(current_tier, {}).get("name", "Бесплатный")

    await message.answer(
        f"🚀 Премиум подписка\n\n"
        f"Текущий пакет: {tier_name}\n\n"
        f"Выбери пакет для просмотра деталей:",
        reply_markup=get_premium_keyboard()
    )


@router.callback_query(F.data.startswith("premium_"))
async def show_premium_tier(query: CallbackQuery):
    """Показывает детали премиум пакета"""
    if query.data == "premium_back":
        user_id = query.from_user.id
        user_data = get_user_limits(user_id)
        
        current_tier = user_data.get("tier", "free")
        tier_name = PREMIUM_TIERS.get(current_tier, {}).get("name", "Бесплатный")
        
        await query.message.edit_text(
            f"🚀 Премиум подписка\n\n"
            f"Текущий пакет: {tier_name}\n\n"
            f"Выбери пакет для просмотра деталей:",
            reply_markup=get_premium_keyboard()
        )
        await query.answer()
        return
    
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
        f"• Stable Diffusion 3: {tier_data['limits']['sd3']} изображений"
    ])
    
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
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


@router.callback_query(F.data.startswith("model_"))
async def select_model(query: CallbackQuery, state: FSMContext):
    """Обработчик выбора модели"""
    model_key = query.data.split("_", 1)[1]
    
    # Kontext требует локального развертывания через Docker
    if model_key == "kontext":
        await query.answer()
        await query.message.edit_text(
            "❌ Модель редактирования изображений недоступна\n\n"
            "FLUX.1-Kontext-dev требует локального развертывания через Docker (NVIDIA NIM) "
            "и не поддерживается через облачный API.\n\n"
            "Доступные альтернативы для генерации изображений:\n"
            "• NanoBanana 1 - быстрая генерация (4 шага)\n"
            "• NanoBanana 2 - качественная генерация (50 шагов)\n\n"
            "Используй /model чтобы выбрать другую модель."
        )
        return
    
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
    from main import bot
    user_id = message.from_user.id
    
    if user_models.get(user_id) != "kontext":
        await message.answer("Сначала выбери модель /model (FLUX.1-kontext-dev для работы с фото)")
        return
    
    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    file_bytes = await bot.download_file(file.file_path)
    
    # Сохраняем только base64 без префикса
    image_b64 = base64.b64encode(file_bytes.getvalue()).decode()
    
    await state.update_data(image_data=image_b64)
    
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
        
        caption = f"✨ Готово!\n\nМодель: {request_info['model']}"
        if request_info["request_id"] != "N/A":
            caption += f"\n🔑 ID запроса: {request_info['request_id']}"
        
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
            
            caption = f"✨ Готово!\n\nМодель: {request_info['model']}\n\n📊 Осталось: {remaining}"
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
            
            caption = f"✨ Готово!\n\nМодель: {request_info['model']}\n\n📊 Осталось: {remaining}"
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


async def setup_bot_commands(bot):
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
