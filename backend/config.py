import os

DEEPSEEK_API_KEY = "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"
DEEPSEEK_MODEL = "deepseek/deepseek-r1-0528-qwen3-8b:free"
DEEPSEEK_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN = os.getenv("7792858670:AAFxeSXQejyU8kaGVFpN4IXb2jIryeVu4go", "7792858670:AAFxeSXQejyU8kaGVFpN4IXb2jIryeVu4go")  # Get from @BotFather
ADMIN_USER_IDS = [int(id) for id in os.getenv("6148278186", "6148278186").split(",") if id]  # Admin Telegram IDs

# Аналитический промпт для обработки вакансий
ANALYTICS_PROMPT = """
Проанализируй следующие вакансии и предоставь инсайты:

1. Какие технологии сейчас в тренде?
2. В каких регионах/странах растет спрос на разработчиков?
3. Как изменились требования и зарплаты по сравнению с прошлой неделей?
4. Рекомендации для junior и senior разработчиков

Вакансии:
{vacancies}

Статистика по технологиям:
{tech_stats}

Региональное распределение:
{regional_stats}

Динамика изменений:
{changes}
""" 