import asyncio
import logging
import json
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command, CommandObject
from aiogram.types import FSInputFile
from aiogram.utils.markdown import hbold, hcode, hlink
from pathlib import Path
import sys
import os

# Add the root directory to PYTHONPATH
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(root_dir)
sys.path.append(backend_dir)

# Import project modules
from storage.database import get_db, engine  # This will now find the root storage first
from storage.models import Base, Vacancy
from config import TELEGRAM_BOT_TOKEN, ADMIN_USER_IDS
from analytics.deepseek_analyzer import DeepseekAnalyzer
from parsers.hh_parser import HHParser

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize database
Base.metadata.create_all(bind=engine)

# Initialize bot and dispatcher
bot = Bot(token=TELEGRAM_BOT_TOKEN, parse_mode="HTML")
dp = Dispatcher()

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """Обработчик команды /start"""
    await message.answer(
        f"👋 Привет, {hbold(message.from_user.full_name)}!\n\n"
        "Я бот для аналитики рынка вакансий. Вот что я умею:\n\n"
        "/collect - Собрать свежие вакансии\n"
        "/analyze - Получить аналитику по последним вакансиям\n"
        "/export - Выгрузить данные в JSON/CSV\n"
        "/stats - Показать текущую статистику\n"
        "/help - Показать справку"
    )

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    """Обработчик команды /help"""
    help_text = (
        "🤖 <b>Доступные команды:</b>\n\n"
        "/collect - Собрать новые вакансии\n"
        "  Пример: /collect python developer\n\n"
        "/analyze - Получить аналитику\n"
        "  Пример: /analyze за неделю\n\n"
        "/export [format] - Выгрузить данные\n"
        "  Пример: /export json\n\n"
        "/stats - Текущая статистика\n"
        "  Используйте для проверки базы\n\n"
        "❓ По всем вопросам: @your_support_username"
    )
    await message.answer(help_text)

@dp.message(Command("collect"))
async def cmd_collect(message: types.Message, command: CommandObject):
    """Сбор новых вакансий"""
    if message.from_user.id not in ADMIN_USER_IDS:
        await message.answer("⛔️ У вас нет прав для выполнения этой команды")
        return

    search_query = command.args if command.args else "python developer"
    status_message = await message.answer("🔍 Начинаю сбор вакансий...")

    try:
        parser = HHParser()
        vacancies = parser.get_all_vacancies(search_query)
        
        if not vacancies:
            await status_message.edit_text("❌ Не удалось найти вакансии")
            return

        # Сохраняем вакансии в JSON
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = Path("parseddata") / f"vacancies_{timestamp}.json"
        output_file.parent.mkdir(exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(vacancies, f, ensure_ascii=False, indent=2)

        # Сохраняем вакансии в базу данных
        db = next(get_db())
        saved_count = 0
        skipped_count = 0
        
        for vacancy_data in vacancies:
            try:
                # Проверяем, существует ли вакансия с таким URL
                existing = db.query(Vacancy).filter(Vacancy.url == vacancy_data['url']).first()
                if existing:
                    skipped_count += 1
                    continue
                    
                # Создаем новую вакансию
                vacancy = Vacancy(
                    title=vacancy_data['title'],
                    company=vacancy_data['company'],
                    city=vacancy_data['city'],
                    tech_stack=vacancy_data['tech_stack'],
                    salary_from=vacancy_data['salary_from'],
                    salary_to=vacancy_data['salary_to'],
                    currency=vacancy_data['currency'],
                    url=vacancy_data['url'],
                    source=vacancy_data['source']
                )
                db.add(vacancy)
                saved_count += 1
            except Exception as e:
                logger.error(f"Error saving vacancy: {e}")
                continue
        
        db.commit()

        await status_message.edit_text(
            f"✅ Обработано {len(vacancies)} вакансий\n"
            f"📥 Сохранено в БД: {saved_count}\n"
            f"⏭ Пропущено: {skipped_count}\n"
            f"📁 JSON файл: {output_file.name}"
        )
    except Exception as e:
        logger.error(f"Error collecting vacancies: {e}")
        await status_message.edit_text(f"❌ Ошибка при сборе вакансий: {str(e)}")

@dp.message(Command("analyze"))
async def cmd_analyze(message: types.Message):
    """Получение аналитики по вакансиям"""
    status_message = await message.answer("🔄 Анализирую данные...")

    try:
        db = next(get_db())
        analyzer = DeepseekAnalyzer()
        analysis = analyzer.analyze_vacancies(db)

        if not analysis:
            await status_message.edit_text("❌ Нет данных для анализа")
            return

        # Форматируем ответ
        response = (
            "📊 <b>Аналитика рынка вакансий:</b>\n\n"
            f"{analysis}"
        )

        # Разбиваем на части, если текст слишком длинный
        if len(response) > 4096:
            for x in range(0, len(response), 4096):
                await message.answer(response[x:x+4096])
            await status_message.delete()
        else:
            await status_message.edit_text(response)

    except Exception as e:
        logger.error(f"Error analyzing vacancies: {e}")
        await status_message.edit_text(f"❌ Ошибка при анализе: {str(e)}")

@dp.message(Command("export"))
async def cmd_export(message: types.Message, command: CommandObject):
    """Экспорт данных в файл"""
    if message.from_user.id not in ADMIN_USER_IDS:
        await message.answer("⛔️ У вас нет прав для выполнения этой команды")
        return

    format_type = command.args.lower() if command.args else "json"
    if format_type not in ["json", "csv"]:
        await message.answer("❌ Поддерживаются форматы: json, csv")
        return

    status_message = await message.answer("📤 Подготовка файла...")

    try:
        # Получаем последний обработанный файл из exports
        exports_dir = Path("exports")
        files = list(exports_dir.glob(f"processed_*.{format_type}"))
        if not files:
            await status_message.edit_text("❌ Нет данных для экспорта")
            return

        latest_file = max(files, key=lambda x: x.stat().st_mtime)
        
        # Отправляем файл
        doc = FSInputFile(latest_file)
        await message.answer_document(
            doc,
            caption=f"📊 Данные по вакансиям\n📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        )
        await status_message.delete()

    except Exception as e:
        logger.error(f"Error exporting data: {e}")
        await status_message.edit_text(f"❌ Ошибка при экспорте: {str(e)}")

@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    """Показать текущую статистику"""
    try:
        db = next(get_db())
        total_vacancies = db.query(Vacancy).count()
        latest_vacancy = db.query(Vacancy).order_by(Vacancy.created_at.desc()).first()
        
        stats = (
            "📈 <b>Текущая статистика:</b>\n\n"
            f"Всего вакансий: {hcode(total_vacancies)}\n"
            f"Последнее обновление: {hcode(latest_vacancy.created_at.strftime('%Y-%m-%d %H:%M'))}\n"
            f"Источники данных: {hcode('hh.ru')}"
        )
        
        await message.answer(stats)
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        await message.answer("❌ Ошибка при получении статистики")

async def main():
    """Запуск бота"""
    try:
        logger.info("Starting bot...")
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main()) 