import sys
import os
import logging
import time
import json
import csv
from datetime import datetime, timedelta
import random
import requests
from pathlib import Path
import pandas as pd
from typing import List, Dict

# Add project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from storage.database import get_db, init_db
from storage.models import Vacancy
from parsers.hh_parser import HHParser

# Configure logging
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_dir / f"data_collector_{datetime.now().strftime('%Y%m%d')}.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class DataCollector:
    def __init__(self):
        self.session = requests.Session()
        self.parsers = {
            'hh.ru': HHParser()
        }
        # Добавим случайные задержки между запросами для защиты от банов
        self.min_delay = 2  # минимальная задержка в секундах
        self.max_delay = 5  # максимальная задержка в секундах
        
    def random_delay(self):
        """Случайная задержка между запросами"""
        delay = random.uniform(self.min_delay, self.max_delay)
        time.sleep(delay)
        
    def collect_data(self) -> Dict:
        """Сбор данных со всех источников"""
        start_time = time.time()
        results = {
            'total_vacancies': 0,
            'sources': {}
        }
        
        for source, parser in self.parsers.items():
            try:
                source_start_time = time.time()
                logger.info(f"Starting collection from {source}")
                
                vacancies = parser.get_all_vacancies()
                
                source_time = time.time() - source_start_time
                results['sources'][source] = {
                    'count': len(vacancies),
                    'time_taken': round(source_time, 2)
                }
                results['total_vacancies'] += len(vacancies)
                
                logger.info(f"Collected {len(vacancies)} vacancies from {source} in {round(source_time, 2)} seconds")
                self.random_delay()
                
            except Exception as e:
                logger.error(f"Error collecting data from {source}: {str(e)}")
                results['sources'][source] = {
                    'error': str(e),
                    'count': 0,
                    'time_taken': 0
                }
        
        total_time = time.time() - start_time
        results['total_time'] = round(total_time, 2)
        logger.info(f"Total collection time: {round(total_time, 2)} seconds")
        
        return results

    def export_data(self, days: int = 3, format: str = 'json') -> str:
        """Экспорт данных за последние N дней"""
        db = next(get_db())
        start_date = datetime.now() - timedelta(days=days)
        
        try:
            # Получаем вакансии за последние N дней
            vacancies = db.query(Vacancy).filter(
                Vacancy.created_at >= start_date
            ).all()
            
            # Преобразуем в список словарей
            data = []
            for v in vacancies:
                vacancy_dict = {
                    'id': v.id,
                    'title': v.title,
                    'company': v.company,
                    'city': v.city,
                    'tech_stack': v.tech_stack,
                    'salary_from': v.salary_from,
                    'salary_to': v.salary_to,
                    'currency': v.currency,
                    'url': v.url,
                    'source': v.source,
                    'created_at': v.created_at.isoformat() if v.created_at else None,
                    'updated_at': v.updated_at.isoformat() if v.updated_at else None
                }
                data.append(vacancy_dict)
            
            # Создаем директорию для экспорта
            export_dir = Path("exports")
            export_dir.mkdir(exist_ok=True)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            if format == 'json':
                filename = export_dir / f"vacancies_{timestamp}.json"
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            else:  # csv
                filename = export_dir / f"vacancies_{timestamp}.csv"
                df = pd.DataFrame(data)
                df.to_csv(filename, index=False, encoding='utf-8')
            
            logger.info(f"Exported {len(data)} vacancies to {filename}")
            return str(filename)
            
        except Exception as e:
            logger.error(f"Error exporting data: {str(e)}")
            raise
        finally:
            db.close()

def main():
    try:
        # Инициализируем базу данных
        init_db()
        
        collector = DataCollector()
        
        # Собираем новые данные
        logger.info("Starting data collection")
        results = collector.collect_data()
        logger.info(f"Collection results: {json.dumps(results, indent=2)}")
        
        # Экспортируем данные за последние 3 дня
        logger.info("Exporting recent data")
        json_file = collector.export_data(days=3, format='json')
        csv_file = collector.export_data(days=3, format='csv')
        
        logger.info(f"Data exported to JSON: {json_file}")
        logger.info(f"Data exported to CSV: {csv_file}")
        
    except Exception as e:
        logger.error(f"Error in main execution: {str(e)}")
        raise

if __name__ == "__main__":
    main() 