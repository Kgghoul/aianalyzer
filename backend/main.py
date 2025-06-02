from fastapi import FastAPI, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from typing import List, Dict, Optional, Union
import sys
import os
import logging
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
from enum import Enum
from fastapi.responses import FileResponse
import json
import pandas as pd
from pathlib import Path
from tempfile import NamedTemporaryFile

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from storage.database import get_db, init_db
from storage.models import Vacancy
from parsers.hh_parser import HHParser
from analytics.deepseek_analyzer import DeepseekAnalyzer

# Модели для документации API
class VacancyBase(BaseModel):
    title: str = Field(..., description="Название вакансии")
    company: str = Field(..., description="Название компании")
    city: str | None = Field(None, description="Город")
    tech_stack: str | None = Field(None, description="Технологии (через запятую)")
    salary_from: float | None = Field(None, description="Минимальная зарплата")
    salary_to: float | None = Field(None, description="Максимальная зарплата")
    currency: str | None = Field(None, description="Валюта зарплаты")
    url: str = Field(..., description="URL вакансии")
    source: str = Field(..., description="Источник вакансии (например, hh.ru)")

class VacancyResponse(VacancyBase):
    id: int = Field(..., description="ID вакансии")
    created_at: str = Field(..., description="Дата создания")
    updated_at: str = Field(..., description="Дата обновления")

class CityStats(BaseModel):
    city: Optional[str] = Field(None, description="Название города")
    count: int = Field(..., description="Количество вакансий")

class AverageSalary(BaseModel):
    from_: Optional[float] = Field(None, alias="from", description="Средняя минимальная зарплата")
    to: Optional[float] = Field(None, description="Средняя максимальная зарплата")

class VacancyStats(BaseModel):
    total_vacancies: int = Field(..., description="Общее количество вакансий")
    cities: List[CityStats] = Field(..., description="Статистика по городам")
    tech_stack: Dict[str, int] = Field(..., description="Статистика по технологиям")
    average_salary: AverageSalary = Field(..., description="Средние зарплаты")

class RefreshResponse(BaseModel):
    message: str = Field(..., description="Сообщение о результате")
    new_vacancies: int = Field(..., description="Количество новых вакансий")
    updated_vacancies: int = Field(..., description="Количество обновленных вакансий")
    skipped_vacancies: int = Field(..., description="Количество пропущенных вакансий")
    total_processed: int = Field(..., description="Всего обработано вакансий")

class CleanupResponse(BaseModel):
    message: str = Field(..., description="Сообщение о результате")
    deleted_count: int = Field(..., description="Количество удаленных вакансий")

class ExportFormat(str, Enum):
    JSON = "json"
    CSV = "csv"

class ExportResponse(BaseModel):
    message: str = Field(..., description="Сообщение о результате")
    file_path: str = Field(..., description="Путь к экспортированному файлу")
    format: ExportFormat = Field(..., description="Формат экспорта")
    records_count: int = Field(..., description="Количество экспортированных записей")

class AnalyticsResponse(BaseModel):
    analysis: str = Field(..., description="Аналитический отчет от DeepSeek")

app = FastAPI(
    title="Job Market Monitor API",
    description="""
    API для мониторинга рынка вакансий. Собирает и анализирует вакансии с различных платформ.
    
    ## Возможности
    
    * Получение списка вакансий с пагинацией
    * Статистика по городам, технологиям и зарплатам
    * Обновление базы вакансий
    * Очистка устаревших данных
    
    ## Источники данных
    
    * hh.ru
    * (планируется) djinni
    * (планируется) Upwork
    * (планируется) Product Hunt
    """,
    version="1.0.0",
    contact={
        "name": "Job Market Monitor Team",
        "url": "https://github.com/yourusername/jobmonitor",
    },
)

@app.on_event("startup")
async def startup_event():
    try:
        init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {str(e)}")
        raise

@app.get("/")
async def root():
    """
    Корневой эндпоинт, возвращает приветственное сообщение
    """
    return {"message": "Job Market Monitor API"}

@app.get("/vacancies/", response_model=List[VacancyResponse], tags=["vacancies"])
async def get_vacancies(
    skip: int = Query(0, description="Количество пропускаемых записей"),
    limit: int = Query(100, description="Максимальное количество возвращаемых записей"),
    db: Session = Depends(get_db)
):
    """
    Получить список вакансий с пагинацией.
    
    - **skip**: количество пропускаемых записей для пагинации
    - **limit**: максимальное количество возвращаемых записей
    
    Возвращает список вакансий с полной информацией.
    """
    try:
        vacancies = db.query(Vacancy).offset(skip).limit(limit).all()
        return [
            {
                "id": v.id,
                "title": v.title,
                "company": v.company,
                "city": v.city,
                "tech_stack": v.tech_stack,
                "salary_from": v.salary_from,
                "salary_to": v.salary_to,
                "currency": v.currency,
                "url": v.url,
                "source": v.source,
                "created_at": v.created_at.isoformat() if v.created_at else None,
                "updated_at": v.updated_at.isoformat() if v.updated_at else None
            }
            for v in vacancies
        ]
    except Exception as e:
        logger.error(f"Error fetching vacancies: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/vacancies/stats", response_model=VacancyStats, tags=["analytics"])
async def get_vacancy_stats(db: Session = Depends(get_db)):
    """
    Получить статистику по вакансиям.
    
    Возвращает:
    - Общее количество вакансий
    - Распределение по городам
    - Статистику по технологиям
    - Средние зарплаты
    """
    try:
        total_vacancies = db.query(func.count(Vacancy.id)).scalar()
        
        cities = db.query(
            Vacancy.city,
            func.count(Vacancy.id).label('count')
        ).group_by(Vacancy.city).all()
        
        tech_stats = {}
        vacancies = db.query(Vacancy.tech_stack).all()
        for vacancy in vacancies:
            if vacancy.tech_stack:
                for tech in vacancy.tech_stack.split(','):
                    tech = tech.strip()
                    if tech:
                        tech_stats[tech] = tech_stats.get(tech, 0) + 1
        
        avg_salary = db.query(
            func.avg(Vacancy.salary_from).label('avg_from'),
            func.avg(Vacancy.salary_to).label('avg_to')
        ).first()
        
        return {
            "total_vacancies": total_vacancies,
            "cities": [{"city": city, "count": count} for city, count in cities],
            "tech_stack": tech_stats,
            "average_salary": {
                "from": round(avg_salary.avg_from, 2) if avg_salary.avg_from else None,
                "to": round(avg_salary.avg_to, 2) if avg_salary.avg_to else None
            }
        }
    except Exception as e:
        logger.error(f"Error fetching stats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/vacancies/refresh", response_model=RefreshResponse, tags=["maintenance"])
async def refresh_vacancies(db: Session = Depends(get_db)):
    """
    Обновить базу вакансий.
    
    - Собирает новые вакансии с поддерживаемых платформ
    - Обновляет существующие вакансии
    - Возвращает статистику по обработанным вакансиям
    """
    try:
        parser = HHParser()
        logger.info("Starting to fetch vacancies from HH.ru")
        vacancies = parser.get_all_vacancies()
        logger.info(f"Fetched {len(vacancies)} vacancies from HH.ru")
        
        new_vacancies = 0
        updated_vacancies = 0
        skipped_vacancies = 0
        
        for vacancy_data in vacancies:
            try:
                existing = db.query(Vacancy).filter(Vacancy.url == vacancy_data["url"]).first()
                
                if existing:
                    has_changes = False
                    for key, value in vacancy_data.items():
                        if key not in ['created_at', 'updated_at'] and getattr(existing, key) != value:
                            setattr(existing, key, value)
                            has_changes = True
                    
                    if has_changes:
                        existing.updated_at = datetime.now()
                        updated_vacancies += 1
                    else:
                        skipped_vacancies += 1
                else:
                    vacancy = Vacancy(**vacancy_data)
                    db.add(vacancy)
                    new_vacancies += 1
                    
                if (new_vacancies + updated_vacancies) % 100 == 0:
                    db.commit()
                    
            except IntegrityError as e:
                logger.warning(f"Duplicate vacancy found: {vacancy_data.get('url')}")
                db.rollback()
                skipped_vacancies += 1
                continue
            except Exception as e:
                logger.error(f"Error processing vacancy {vacancy_data.get('url')}: {str(e)}")
                db.rollback()
                continue
        
        db.commit()
        
        logger.info(
            f"Successfully added {new_vacancies} new vacancies, "
            f"updated {updated_vacancies} existing vacancies, "
            f"skipped {skipped_vacancies} unchanged vacancies"
        )
        
        return {
            "message": f"Added {new_vacancies} new vacancies, updated {updated_vacancies} existing ones",
            "new_vacancies": new_vacancies,
            "updated_vacancies": updated_vacancies,
            "skipped_vacancies": skipped_vacancies,
            "total_processed": len(vacancies)
        }
    except Exception as e:
        logger.error(f"Error refreshing vacancies: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/vacancies/cleanup", response_model=CleanupResponse, tags=["maintenance"])
async def cleanup_old_vacancies(
    days: int = Query(30, description="Удалить вакансии старше указанного количества дней"),
    db: Session = Depends(get_db)
):
    """
    Удалить старые вакансии из базы данных.
    
    - **days**: количество дней, старше которых вакансии будут удалены (по умолчанию 30)
    
    Возвращает количество удаленных вакансий.
    """
    try:
        cutoff_date = datetime.now() - timedelta(days=days)
        deleted_count = db.query(Vacancy).filter(
            Vacancy.updated_at < cutoff_date
        ).delete(synchronize_session=False)
        
        db.commit()
        logger.info(f"Deleted {deleted_count} old vacancies")
        return {
            "message": f"Successfully deleted {deleted_count} vacancies older than {days} days",
            "deleted_count": deleted_count
        }
    except Exception as e:
        logger.error(f"Error cleaning up old vacancies: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/vacancies/collect", response_model=RefreshResponse, tags=["data"])
async def collect_vacancies(db: Session = Depends(get_db)):
    """
    Запустить однократный сбор вакансий со всех источников
    """
    try:
        parser = HHParser()
        new_count = 0
        updated_count = 0
        skipped_count = 0
        total_count = 0

        vacancies = parser.get_all_vacancies()
        
        for vacancy_data in vacancies:
            total_count += 1
            existing = db.query(Vacancy).filter(Vacancy.url == vacancy_data['url']).first()
            
            if not existing:
                vacancy = Vacancy(
                    title=vacancy_data['title'],
                    company=vacancy_data['company'],
                    city=vacancy_data.get('city'),
                    tech_stack=vacancy_data.get('tech_stack'),
                    salary_from=vacancy_data.get('salary_from'),
                    salary_to=vacancy_data.get('salary_to'),
                    currency=vacancy_data.get('currency'),
                    url=vacancy_data['url'],
                    source=vacancy_data['source']
                )
                db.add(vacancy)
                new_count += 1
            else:
                # Обновляем существующую вакансию если есть изменения
                was_updated = False
                for field in ['title', 'company', 'city', 'tech_stack', 'salary_from', 'salary_to', 'currency']:
                    if getattr(existing, field) != vacancy_data.get(field):
                        setattr(existing, field, vacancy_data.get(field))
                        was_updated = True
                
                if was_updated:
                    existing.updated_at = datetime.now()
                    updated_count += 1
                else:
                    skipped_count += 1
        
        db.commit()
        
        return {
            "message": "Сбор вакансий успешно завершен",
            "new_vacancies": new_count,
            "updated_vacancies": updated_count,
            "skipped_vacancies": skipped_count,
            "total_processed": total_count
        }
    except Exception as e:
        logger.error(f"Error collecting vacancies: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/vacancies/export", response_model=ExportResponse, tags=["data"])
async def export_vacancies(
    format: ExportFormat = Query(ExportFormat.JSON, description="Формат экспорта (json или csv)"),
    days: int = Query(3, description="Количество дней для выгрузки"),
    db: Session = Depends(get_db)
):
    """
    Экспортировать вакансии в JSON или CSV формат
    """
    try:
        # Создаем директорию для экспорта если её нет
        export_dir = Path("exports")
        export_dir.mkdir(exist_ok=True)
        
        # Получаем вакансии за указанный период
        cutoff_date = datetime.now() - timedelta(days=days)
        vacancies = db.query(Vacancy).filter(
            Vacancy.created_at >= cutoff_date
        ).all()
        
        # Преобразуем вакансии в список словарей
        vacancy_data = []
        for v in vacancies:
            vacancy_dict = {
                "id": v.id,
                "title": v.title,
                "company": v.company,
                "city": v.city,
                "tech_stack": v.tech_stack,
                "salary_from": v.salary_from,
                "salary_to": v.salary_to,
                "currency": v.currency,
                "url": v.url,
                "source": v.source,
                "created_at": v.created_at.isoformat() if v.created_at else None,
                "updated_at": v.updated_at.isoformat() if v.updated_at else None
            }
            vacancy_data.append(vacancy_dict)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if format == ExportFormat.JSON:
            file_path = export_dir / f"vacancies_{timestamp}.json"
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(vacancy_data, f, ensure_ascii=False, indent=2)
        else:  # CSV
            file_path = export_dir / f"vacancies_{timestamp}.csv"
            df = pd.DataFrame(vacancy_data)
            df.to_csv(file_path, index=False, encoding="utf-8")
        
        return {
            "message": f"Данные успешно экспортированы в {format.value} формат",
            "file_path": str(file_path),
            "format": format,
            "records_count": len(vacancy_data)
        }
    except Exception as e:
        logger.error(f"Error exporting vacancies: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/analytics/market-insights", response_model=AnalyticsResponse, tags=["analytics"])
async def get_market_insights(db: Session = Depends(get_db)):
    """
    Получить аналитический отчет о рынке вакансий за последнюю неделю.
    
    Возвращает:
    - Анализ трендов в технологиях
    - Региональный анализ спроса
    - Изменения по сравнению с прошлой неделей
    - Рекомендации для разработчиков разного уровня
    """
    try:
        analyzer = DeepseekAnalyzer()
        analysis = analyzer.analyze_vacancies(db)
        return {"analysis": analysis}
    except Exception as e:
        logger.error(f"Error getting market insights: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 