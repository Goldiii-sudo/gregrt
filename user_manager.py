"""Управление данными пользователей"""
import json
from config import USER_DATA_FILE, PREMIUM_TIERS


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
