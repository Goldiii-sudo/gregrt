"""Поиск в интернете"""
import logging
import httpx

logger = logging.getLogger(__name__)


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
