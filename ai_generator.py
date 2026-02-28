"""Генерация текста и изображений через NVIDIA API"""
import logging
import base64
import re
import aiohttp
import httpx
from openai import OpenAI
from config import NVIDIA_API_KEY, MODELS
from user_manager import get_user_history, add_to_history

logger = logging.getLogger(__name__)

# OpenAI клиент для NVIDIA LLM
try:
    llm_client = OpenAI(
        base_url="https://integrate.api.nvidia.com/v1",
        api_key=NVIDIA_API_KEY,
        http_client=None
    )
except TypeError:
    # Для Python 3.14+ используем другой способ
    llm_client = OpenAI(
        base_url="https://integrate.api.nvidia.com/v1",
        api_key=NVIDIA_API_KEY,
        http_client=httpx.Client()
    )


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
        generated_text = re.sub(r'<think>.*?</think>', '', generated_text, flags=re.DOTALL).strip()

        # Удаляем markdown форматирование (**, ##, ||, и т.д.)
        generated_text = re.sub(r'\*\*', '', generated_text)  # Удаляем **
        generated_text = re.sub(r'##+ ', '', generated_text)  # Удаляем заголовки
        generated_text = re.sub(r'\|\s*-+\s*\|', '', generated_text)  # Удаляем разделители таблиц
        generated_text = re.sub(r'^\s*\|\s*', '', generated_text, flags=re.MULTILINE)  # Удаляем пустые строки с |

        # Сохраняем в историю если есть user_id
        if user_id:
            add_to_history(user_id, model_key, prompt, generated_text)

        logger.info(f"Текст сгенерирован: {generated_text[:100]}")
        return generated_text

    except Exception as e:
        logger.error(f"Ошибка при генерации текста: {e}")
        raise Exception(f"Ошибка LLM: {str(e)}")


def enhance_prompt(prompt: str) -> str:
    """Улучшает промпт, добавляя детали качества"""
    enhanced = f"{prompt}, high quality, detailed, professional, sharp focus, 8k resolution"
    return enhanced


async def translate_to_english(prompt: str) -> str:
    """Переводит промпт на английский если он на русском"""
    try:
        # Проверяем, есть ли кириллица в промпте
        if not any('\u0400' <= char <= '\u04FF' for char in prompt):
            # Уже на английском
            return prompt
        
        logger.info(f"Перевожу промпт на английский: {prompt}")
        
        # Используем LLM для перевода
        messages = [
            {
                "role": "system",
                "content": "You are a translator for image generation prompts. "
                          "Translate Russian text to English concisely. "
                          "Output ONLY the English translation, nothing else. "
                          "No explanations, no thinking process, just the translation."
            },
            {
                "role": "user",
                "content": f"Translate to English for image generation: {prompt}"
            }
        ]
        
        completion = llm_client.chat.completions.create(
            model="minimaxai/minimax-m2.5",
            messages=messages,
            temperature=0.3,
            max_tokens=200,
            stream=False
        )
        
        translated = completion.choices[0].message.content.strip()
        
        # Удаляем теги <think>...</think> если есть
        translated = re.sub(r'<think>.*?</think>', '', translated, flags=re.DOTALL).strip()
        
        # Удаляем кавычки если есть
        translated = translated.strip('"\'')
        
        # Если перевод слишком длинный или содержит объяснения, берем только первую строку
        if '\n' in translated:
            translated = translated.split('\n')[0].strip()
        
        # Если все еще пусто или слишком длинно, возвращаем оригинал
        if not translated or len(translated) > 300:
            logger.warning(f"Перевод некорректный, использую оригинал")
            return prompt
        
        logger.info(f"Переведено: {translated}")
        return translated
        
    except Exception as e:
        logger.error(f"Ошибка при переводе: {e}")
        # Если перевод не удался, возвращаем оригинал
        return prompt


async def generate_image(prompt: str, model_key: str, image_data: str = None) -> tuple[bytes, dict]:
    """Генерирует изображение через NVIDIA API"""
    model = MODELS.get(model_key, MODELS["schnell"])
    
    # Переводим промпт на английский для лучшего качества
    translated_prompt = await translate_to_english(prompt)
    
    # Для kontext не улучшаем промпт, используем оригинальный
    if model_key == "kontext":
        final_prompt = translated_prompt
    else:
        final_prompt = enhance_prompt(translated_prompt)
    
    logger.info(f"Модель: {model['name']}")
    logger.info(f"Исходный промпт: {prompt}")
    logger.info(f"Переведенный промпт: {translated_prompt}")
    logger.info(f"Финальный промпт: {final_prompt}")
    
    headers = {
        "Authorization": f"Bearer {NVIDIA_API_KEY}",
        "Accept": "application/json",
    }
    
    payload = {
        "prompt": final_prompt,
        **model["params"]
    }
    
    # Для kontext добавляем изображение
    if model_key == "kontext" and image_data:
        # Убираем префикс если он есть
        if image_data.startswith("data:image"):
            image_data = image_data.split(",", 1)[1]
        # Просто base64 строка без префикса
        payload["image"] = image_data
        logger.info(f"Добавлено изображение для kontext (длина base64: {len(image_data)})")
    
    logger.info(f"Отправляю запрос к {model['url']}")
    logger.info(f"Payload keys: {list(payload.keys())}")
    logger.info(f"Payload (без image): {dict((k, v) for k, v in payload.items() if k != 'image')}")
    
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
                
                # Разные форматы ответа для разных моделей
                if "artifacts" in result and len(result["artifacts"]) > 0:
                    # Формат Stability AI (SD3)
                    image_b64 = result["artifacts"][0].get("base64", "")
                elif "image" in result:
                    # Формат FLUX
                    image_b64 = result["image"]
                elif "data" in result and len(result["data"]) > 0:
                    # Альтернативный формат
                    image_b64 = result["data"][0].get("b64_json", "")
                else:
                    raise Exception("Не удалось найти изображение в ответе API")
                
                image_bytes = base64.b64decode(image_b64)
                return image_bytes, request_info
                
        except Exception as e:
            logger.error(f"Ошибка при генерации изображения: {e}")
            raise
